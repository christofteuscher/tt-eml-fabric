#!/usr/bin/env python3
"""
REDUCED / BIASED depth-5 probe.  Builds the depth<=4 corpus, takes the K classes
with the smallest peak magnitude (the physically realisable ones), pairs them all,
and streams the best affine-readout fit to each target.  This is a LOWER BOUND on
depth-5 coverage, not an exhaustive depth-5 enumeration.
"""
import numpy as np, json, sys, time, os
from op_search import OPS, TARGETS, TN, TM, X, NG, UCAP, BIG, key_of
np.seterr(all="ignore")
OUT = os.path.dirname(os.path.abspath(__file__))
T0 = time.time()
K     = int(sys.argv[1]) if len(sys.argv) > 1 else 2500
NAMES = sys.argv[2].split(",") if len(sys.argv) > 2 else ["eml","sha","eas","sna","sag"]
MAXC  = 150000

def best_fit(F, cur):
    """running min over classes of max-rel-error of the fabric readout A*f+B."""
    for t in range(len(TN)):
        y = TM[t]; ny = np.abs(y).max(); ym = y.mean()
        cm = F.mean(1, keepdims=True)
        cv = ((F-cm)*(y-ym)).sum(1); vv = ((F-cm)**2).sum(1)
        a = np.where(vv > 1e-30, cv/np.maximum(vv, 1e-300), 0.0)[:, None]
        e = np.abs(a*F + (ym - a*cm) - y).max(1) / ny
        e = e[np.isfinite(e)]
        if e.size: cur[t] = min(cur[t], float(e.min()))
    return cur

def corpus(name, dmax=4):
    f, dfu, dfv, dom, _ = OPS[name]
    V = np.array([np.ones(NG), X]); K_ = {k.tobytes(): 1 for k in key_of(V)}
    prev = 0
    for d in range(1, dmax+1):
        n = len(V)
        ia, ib = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
        ia, ib = ia.ravel(), ib.ravel()
        m = ~((ia < prev) & (ib < prev)); ia, ib = ia[m], ib[m]
        acc = []
        for s in range(0, len(ia), 300000):
            A, B = V[ia[s:s+300000]], V[ib[s:s+300000]]
            ok = dom(A, B).all(1) & (np.abs(A) < UCAP).all(1) & (np.abs(B) < BIG).all(1)
            if not ok.any(): continue
            A, B = A[ok], B[ok]; Y = f(A, B)
            g = np.isfinite(Y).all(1) & (np.abs(Y) < BIG).all(1)
            if g.any(): acc.append(Y[g])
        if acc:
            Y = np.concatenate(acc); keep = []
            for i, kb in enumerate(key_of(Y)):
                b = kb.tobytes()
                if b not in K_:
                    K_[b] = 1; keep.append(i)
                    if len(K_) >= MAXC: break
            if keep: V = np.concatenate([V, Y[keep]])
        prev = n
        if len(V) >= MAXC: break
    return V

res = {}
for name in NAMES:
    f, _, _, dom, blurb = OPS[name]
    V = corpus(name)
    e4 = best_fit(V, [np.inf]*len(TN))
    # biased subset: physically realisable (small peak), non-constant
    pk = np.abs(V).max(1); sw = V.max(1) - V.min(1)
    ok = np.isfinite(pk) & (sw > 1e-9*np.maximum(pk, 1e-12))
    idx = np.where(ok)[0]; idx = idx[np.argsort(pk[idx])][:K]
    S = V[idx]; nS = len(S)
    e5 = list(e4); npair = tot = rej = 0
    for s in range(0, nS, 200):
        A = np.repeat(S[s:s+200], nS, 0); B = np.tile(S, (min(200, nS-s), 1))
        tot += A.shape[0]
        g = dom(A, B).all(1) & (np.abs(A) < UCAP).all(1) & (np.abs(B) < BIG).all(1)
        if not g.any(): rej += A.shape[0]; continue
        Y = f(A[g], B[g])
        gg = np.isfinite(Y).all(1) & (np.abs(Y) < BIG).all(1)
        rej += A.shape[0] - int(gg.sum())
        if gg.any(): npair += int(gg.sum()); e5 = best_fit(Y[gg], e5)
    res[name] = dict(n4=len(V), nS=nS, pairs=tot, ood5=round(rej/max(tot,1), 4),
                     d4={TN[i]: e4[i] for i in range(len(TN))},
                     d5={TN[i]: e5[i] for i in range(len(TN))})
    print("%-5s |F(<=4)|=%-7d subset=%-5d pairs=%-9d ood=%.3f  %.1fs"
          % (name, len(V), nS, tot, res[name]["ood5"], time.time()-T0), flush=True)
json.dump(res, open(os.path.join(OUT, "deepen.json"), "w"), indent=1)
print("\n%-9s" % "target", " ".join("%-15s" % n for n in NAMES))
for t in TN:
    print("%-9s" % t, " ".join("%7.1e>%-7.1e" % (res[n]["d4"][t], res[n]["d5"][t]) for n in NAMES))
