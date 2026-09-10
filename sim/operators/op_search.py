#!/usr/bin/env python3
"""
Search for a binary primitive that is functionally rich for the elementary
functions BUT better conditioned for analog realisation than eml(u,v)=exp(u)-ln(v).

Grammar, identical for every candidate:   S -> 1 | x | op(S,S)
Same grid, same overflow caps, same dedup rule as fabric_sim/corpus_enum.

Metrics (all measured on the enumerated corpus unless stated):
  dom_box   fraction of a fixed (u,v) box on which op is defined & finite  [intrinsic]
  ood       fraction of enumerated pairs rejected (domain + overflow)      [corpus]
  decades   log10 span of the middle 99% of ALL internal node magnitudes   [corpus]
  gu, gv    geometric-mean |df/du|, |df/dv| at the operating points reached
  asym      |log10(gu/gv)|   -- port sensitivity asymmetry
  spr_u/v   log10(p99/p1) of each port gain -- how far bias must track
  |F(d)|    distinct semantic classes at depth <= d  (expressive richness)
  targets   best affine-readout (A*f+B, as the real fabric has) fit to each
            of a set of elementary targets, incl. sin/cos.
"""
import numpy as np, json, sys, time, os

np.seterr(all="ignore")
T0 = time.time()
OUT = os.path.dirname(os.path.abspath(__file__))

X = np.array([0.35, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.5, 6.5])  # fabric sweep range
NG = len(X)
UCAP = 600.0          # exp/sinh argument cap (corpus_enum uses 570)
BIG  = 1e250          # magnitude cap                (corpus_enum uses 1e250)
_A = sys.argv if os.path.basename(sys.argv[0]).startswith("op_search") else []  # importable
DMAX = int(_A[1]) if len(_A) > 1 else 4
NEX  = int(_A[2]) if len(_A) > 2 else 900     # exhaustive pairing limit
NSAMP= int(_A[3]) if len(_A) > 3 else 700000  # sampled pairs beyond that
MAXCLASS = 400000

def sech(z): return 1.0 / np.cosh(np.clip(z, -UCAP, UCAP))
def gd(z):   return np.arcsin(np.tanh(z))                 # Gudermannian

# name: (f, dfdu, dfdv, domain-mask, needs-exp-of-u?, blurb)
OPS = {
 # ---- baseline
 "eml":  (lambda u,v: np.exp(u) - np.log(v),
          lambda u,v: np.exp(u),            lambda u,v: -1.0/v,
          lambda u,v: v > 0.0,              "exp(u) - ln(v)          BASELINE (Odrzywolek)"),
 # ---- regularised / everywhere-defined relatives of eml
 "sha":  (lambda u,v: np.sinh(u) - np.arcsinh(v),
          lambda u,v: np.cosh(u),           lambda u,v: -1.0/np.sqrt(1.0+v*v),
          lambda u,v: np.ones_like(v, bool),"sinh(u) - asinh(v)      hyperbolic eml"),
 "eas":  (lambda u,v: np.exp(u) - np.arcsinh(v),
          lambda u,v: np.exp(u),            lambda u,v: -1.0/np.sqrt(1.0+v*v),
          lambda u,v: np.ones_like(v, bool),"exp(u) - asinh(v)       minimal repair of eml"),
 "eat":  (lambda u,v: np.exp(u) - np.arctan(v),
          lambda u,v: np.exp(u),            lambda u,v: -1.0/(1.0+v*v),
          lambda u,v: np.ones_like(v, bool),"exp(u) - atan(v)        bounded compressing port"),
 "sag":  (lambda u,v: np.sinh(u) - gd(v),
          lambda u,v: np.cosh(u),           lambda u,v: -sech(v),
          lambda u,v: np.ones_like(v, bool),"sinh(u) - gd(v)         Gudermannian bridge"),
 "emx":  (lambda u,v: np.exp(u) - np.exp(-v),
          lambda u,v: np.exp(u),            lambda u,v: np.exp(-v),
          lambda u,v: np.ones_like(v, bool),"exp(u) - exp(-v)        symmetric double-exp"),
 "emu":  (lambda u,v: v*np.exp(u),
          lambda u,v: v*np.exp(u),          lambda u,v: np.exp(u),
          lambda u,v: np.ones_like(v, bool),"v*exp(u)                translinear multiply"),
 # ---- bounded / contractive ports
 "tln":  (lambda u,v: np.tanh(u) - np.log(v),
          lambda u,v: sech(u)**2,           lambda u,v: -1.0/v,
          lambda u,v: v > 0.0,              "tanh(u) - ln(v)         bounded expanding port"),
 "lse":  (lambda u,v: np.logaddexp(u, v),
          lambda u,v: 1.0/(1.0+np.exp(np.clip(v-u,-UCAP,UCAP))),
          lambda u,v: 1.0/(1.0+np.exp(np.clip(u-v,-UCAP,UCAP))),
          lambda u,v: np.ones_like(v, bool),"ln(e^u + e^v)           log-sum-exp (contractive)"),
 # ---- oscillatory ingredient (trig-capable by construction)
 "sna":  (lambda u,v: np.sinh(u) - np.sin(v),
          lambda u,v: np.cosh(u),           lambda u,v: -np.cos(v),
          lambda u,v: np.ones_like(v, bool),"sinh(u) - sin(v)        oscillatory v port"),
 "snl":  (lambda u,v: np.sin(u) - np.log(v),
          lambda u,v: np.cos(u),            lambda u,v: -1.0/v,
          lambda u,v: v > 0.0,              "sin(u) - ln(v)          oscillatory u port"),
 # ---- controls: must FAIL richness, to show the criteria are not vacuous
 "rcp":  (lambda u,v: u - 1.0/v,
          lambda u,v: np.ones_like(u),      lambda u,v: 1.0/(v*v),
          lambda u,v: np.abs(v) > 1e-300,   "u - 1/v                 rational control"),
 "sqd":  (lambda u,v: u*u - v,
          lambda u,v: 2.0*u,                lambda u,v: -np.ones_like(v),
          lambda u,v: np.ones_like(v, bool),"u^2 - v                 polynomial control"),
}

TARGETS = {
 "exp(x)": np.exp(X), "ln(x)": np.log(X), "1/x": 1.0/X, "x^2": X**2,
 "sqrt(x)": np.sqrt(X), "x*ln(x)": X*np.log(X), "exp(-x)": np.exp(-X),
 "x^x": X**X, "1/(1+x^2)": 1.0/(1.0+X**2),
 "sin(x)": np.sin(X), "cos(x)": np.cos(X), "tan(x)": np.tan(X),
 "sin(2x)": np.sin(2*X), "atan(x)": np.arctan(X), "tanh(x)": np.tanh(X),
}
TN = list(TARGETS); TM = np.array([TARGETS[k] for k in TN])         # (T, NG)

# ---------- intrinsic domain measure over a fixed box (operator-only, no corpus)
def dom_box(name, n=400000, half=8.0, seed=0):
    r = np.random.default_rng(seed)
    u = r.uniform(-half, half, n); v = r.uniform(-half, half, n)
    f, _, _, dom, _ = OPS[name]
    m = dom(u, v)
    y = np.where(m, f(np.clip(u,-UCAP,UCAP), np.where(m, v, 1.0)), np.nan)
    return float(np.mean(m & np.isfinite(y) & (np.abs(y) < BIG)))

# ---------- semantic enumeration ----------
def key_of(A):
    """~9 significant-digit dedup key, scale free (mantissa+exponent)."""
    m, e = np.frexp(A)
    q = np.round(m * 2.0**30).astype(np.int64)
    return np.ascontiguousarray(np.concatenate([q, e.astype(np.int64)], 1))

def run(name, rng_seed=7):
    f, dfu, dfv, dom, blurb = OPS[name]
    V = np.array([np.ones(NG), X])                 # class value table
    K = {}                                          # dedup keys
    for k in key_of(V): K[k.tobytes()] = 1
    lvl, ood, sampled, gu_all, gv_all, node_mag = [2], [], [], [], [], [np.ones(NG), np.abs(X)]
    live_n = [0, 0]
    prev_n = 0
    for d in range(1, DMAX+1):
        n = len(V)
        if n <= NEX:                                # exhaustive: all n^2 ordered pairs
            ia, ib = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
            ia, ib = ia.ravel(), ib.ravel()
            new = ~((ia < prev_n) & (ib < prev_n))  # skip pairs already done
            ia, ib = ia[new], ib[new]; samp = False
        else:                                       # REDUCED: uniform random pairs
            r = np.random.default_rng(rng_seed + d)
            ia = r.integers(0, n, NSAMP); ib = r.integers(0, n, NSAMP); samp = True
        sampled.append(samp)
        tot = rej = 0; acc = []
        for s in range(0, len(ia), 400000):
            A, B = V[ia[s:s+400000]], V[ib[s:s+400000]]
            tot += A.shape[0]
            ok = dom(A, B).all(1) & (np.abs(A) < UCAP).all(1) & (np.abs(B) < BIG).all(1)
            if not ok.any(): rej += A.shape[0]; continue
            A, B = A[ok], B[ok]
            with np.errstate(all="ignore"):
                Y = f(A, B)
            good = np.isfinite(Y).all(1) & (np.abs(Y) < BIG).all(1)
            rej += A.shape[0] - int(good.sum()) + int((~ok).sum())
            if not good.any(): continue
            A, B, Y = A[good], B[good], Y[good]
            with np.errstate(all="ignore"):
                a_ = np.abs(dfu(A, B)); b_ = np.abs(dfv(A, B))
                gu_all.append(a_.ravel()); gv_all.append(b_.ravel())
                # "live hop": BOTH ports sensitive enough to calibrate (>1e-3, cf. the
                # 0.266-unit 1-sigma cell mismatch) and not so hot they amplify it (<1e3)
                live_n[0] += int(((a_>1e-3)&(a_<1e3)&(b_>1e-3)&(b_<1e3)).all(1).sum())
                live_n[1] += A.shape[0]
            acc.append(Y)
        ood.append(rej / max(tot, 1))
        if acc:
            Y = np.concatenate(acc); node_mag.append(np.abs(Y).ravel())
            kb = key_of(Y); keep = []
            for i in range(len(kb)):
                b = kb[i].tobytes()
                if b not in K:
                    K[b] = 1; keep.append(i)
                    if len(K) >= MAXCLASS: break
            if keep: V = np.concatenate([V, Y[keep]])
        prev_n = n; lvl.append(len(V))
        if len(V) >= MAXCLASS: break

    # ---- port gains at the operating points actually reached
    gu = np.concatenate(gu_all) if gu_all else np.array([1.0])
    gv = np.concatenate(gv_all) if gv_all else np.array([1.0])
    gu = gu[np.isfinite(gu) & (gu > 0)]; gv = gv[np.isfinite(gv) & (gv > 0)]
    lg = lambda a: float(np.exp(np.mean(np.log(a)))) if a.size else float("nan")
    spr = lambda a: float(np.log10(np.percentile(a,99)/max(np.percentile(a,1),1e-300))) if a.size else float("nan")
    GU, GV = lg(gu), lg(gv)

    # ---- dynamic range of all internal node magnitudes (middle 99%)
    M = np.concatenate([np.asarray(m).ravel() for m in node_mag])
    M = M[np.isfinite(M) & (M > 0)]
    dec = float(np.log10(np.percentile(M, 99.5) / np.percentile(M, 0.5)))

    # ---- fraction of the closure that fits the MEASURED silicon span
    #      5.80e-6 .. 1366 units = 8.372 decades (corpus_enum SPAN_*)
    U_LO, U_HI = 5.80e-6, 1366.0
    Aa = np.abs(V); pk = Aa.max(1); fl = np.where(Aa > 0, Aa, np.inf).min(1)
    fit8 = float(np.mean((pk <= U_HI) & ((fl >= U_LO) | ~np.isfinite(fl))))

    # ---- target coverage with the fabric's affine readout  A*f + B
    F = V[np.isfinite(V).all(1) & (np.abs(V) < 1e120).all(1)]
    best = {}
    for t in range(len(TN)):
        y = TM[t]; ny = np.abs(y).max()
        bb = np.inf
        for s in range(0, len(F), 40000):
            C = F[s:s+40000]
            cm = C.mean(1, keepdims=True); ym = y.mean()
            cv = ((C-cm)*(y-ym)).sum(1); vv = ((C-cm)**2).sum(1)
            a = np.where(vv > 1e-30, cv/np.maximum(vv,1e-300), 0.0)[:,None]
            b = ym - a*cm
            e = np.abs(a*C + b - y).max(1) / ny
            bb = min(bb, float(np.nanmin(e)))
        best[TN[t]] = bb
    return dict(op=name, blurb=blurb, levels=lvl, sampled=sampled,
                ood=[round(o,4) for o in ood], decades=round(dec,2),
                gu=GU, gv=GV, asym=round(abs(np.log10(GU/GV)),2),
                spr_u=round(spr(gu),2), spr_v=round(spr(gv),2),
                supF=float(np.abs(F).max()), nclass=len(V),
                fit8=round(fit8,4), live=round(live_n[0]/max(live_n[1],1),4),
                targets={k: float(v) for k, v in best.items()},
                dom_box=round(dom_box(name),4))

if __name__ == "__main__":
    res = []
    for name in OPS:
        r = run(name); res.append(r)
        print("%-5s |F|=%-8d ood(last)=%.3f dec=%5.2f asym=%4.2f dom=%.3f  %.1fs"
              % (name, r["nclass"], r["ood"][-1], r["decades"], r["asym"],
                 r["dom_box"], time.time()-T0), flush=True)
    json.dump(res, open(os.path.join(OUT, "op_search.json"), "w"), indent=1)
    print("wrote", os.path.join(OUT, "op_search.json"))
