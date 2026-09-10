#!/usr/bin/env python3
"""
COMPLETENESS, honestly.  op_search fits the fabric's affine readout A*f+B to a
target on the SAME 9 grid points that define a semantic class.  With |F| at the
400 000 cap and 2 free parameters, a small error is not evidence of
representation -- it is evidence of fitting.

Here the corpus is enumerated on 15 points: the original 9 plus 6 interleaved
HELD-OUT points.  A and B are fitted on the 9 and scored on the 6.
Same grammar, same caps, same dedup key, cap 150k classes (REDUCED vs 400k).
"""
import json, os, sys, time
import numpy as np
import phys_ops
import op_search as OS

np.seterr(all="ignore")
OUT = os.path.dirname(os.path.abspath(__file__))
T0 = time.time()
X9 = np.array([0.35, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.5, 6.5])
XH = np.array([0.42, 0.87, 1.22, 2.45, 3.8, 5.4])          # held out, interior
XE = np.concatenate([X9, XH]); NG = len(XE); NF = len(X9)
MAXC = 150000

T = {"exp(x)": np.exp(XE), "ln(x)": np.log(XE), "1/x": 1.0 / XE, "x^2": XE ** 2,
     "sqrt(x)": np.sqrt(XE), "x*ln(x)": XE * np.log(XE), "exp(-x)": np.exp(-XE),
     "x^x": XE ** XE, "1/(1+x^2)": 1.0 / (1.0 + XE ** 2), "sin(x)": np.sin(XE),
     "cos(x)": np.cos(XE), "tan(x)": np.tan(XE), "atan(x)": np.arctan(XE),
     "tanh(x)": np.tanh(XE)}
TN = list(T); TM = np.array([T[k] for k in TN])


def corpus(name):
    f, dfu, dfv, dom, _ = OS.OPS[name]
    V = np.array([np.ones(NG), XE])
    K = {k.tobytes(): 1 for k in OS.key_of(V)}
    prev = 0
    for d in range(1, 5):
        n = len(V)
        if n * n <= 4_000_000:
            ia, ib = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
            ia, ib = ia.ravel(), ib.ravel()
            m = ~((ia < prev) & (ib < prev)); ia, ib = ia[m], ib[m]
        else:
            r = np.random.default_rng(23 + d)
            ia = r.integers(0, n, 900000); ib = r.integers(0, n, 900000)
        acc = []
        for s in range(0, len(ia), 300000):
            A, B = V[ia[s:s + 300000]], V[ib[s:s + 300000]]
            ok = dom(A, B).all(1) & (np.abs(A) < OS.UCAP).all(1) & (np.abs(B) < OS.BIG).all(1)
            if not ok.any():
                continue
            Y = f(A[ok], B[ok])
            g = np.isfinite(Y).all(1) & (np.abs(Y) < OS.BIG).all(1)
            if g.any():
                acc.append(Y[g])
        if acc:
            Y = np.concatenate(acc); keep = []
            for i, kb in enumerate(OS.key_of(Y)):
                b = kb.tobytes()
                if b not in K:
                    K[b] = 1; keep.append(i)
                    if len(K) >= MAXC:
                        break
            if keep:
                V = np.concatenate([V, Y[keep]])
        prev = n
        if len(V) >= MAXC:
            break
    return V[np.isfinite(V).all(1) & (np.abs(V) < 1e120).all(1)]


NAMES = sys.argv[1].split(",") if len(sys.argv) > 1 else \
    ["lmj", "lmw", "rsj", "squ", "tun", "dfz", "nsp", "eml", "sna", "sag"]
res = {}
for nm in NAMES:
    F = corpus(nm)
    ins, out = {}, {}
    for t in range(len(TN)):
        y = TM[t]; yf, yh = y[:NF], y[NF:]
        nf, nh = np.abs(yf).max(), np.abs(yh).max()
        bi, bo = np.inf, np.inf
        for s in range(0, len(F), 30000):
            C = F[s:s + 30000]; Cf = C[:, :NF]
            cm = Cf.mean(1, keepdims=True); ym = yf.mean()
            cv = ((Cf - cm) * (yf - ym)).sum(1); vv = ((Cf - cm) ** 2).sum(1)
            a = np.where(vv > 1e-30, cv / np.maximum(vv, 1e-300), 0.0)[:, None]
            b = ym - a * cm
            ei = np.abs(a * Cf + b - yf).max(1) / nf
            eo = np.abs(a * C[:, NF:] + b - yh).max(1) / nh
            # rank by IN-sample error (that is all the designer can see), then
            # report the out-of-sample error of that same winner.
            ok = np.isfinite(ei) & np.isfinite(eo)
            if ok.any():
                j = int(np.nanargmin(np.where(ok, ei, np.inf)))
                if ei[j] < bi:
                    bi, bo = float(ei[j]), float(eo[j])
        ins[TN[t]], out[TN[t]] = bi, bo
    res[nm] = dict(n=len(F), ins=ins, out=out,
                   worst_in=max(ins.values()), worst_out=max(out.values()),
                   med_out=float(np.median(list(out.values()))))
    print("%-4s |F|=%-7d worst_in=%.2e worst_out=%.2e med_out=%.2e  %.0fs"
          % (nm, len(F), res[nm]["worst_in"], res[nm]["worst_out"],
             res[nm]["med_out"], time.time() - T0), flush=True)

json.dump(res, open(os.path.join(OUT, "holdout.json"), "w"), indent=1)
print("\n%-10s" % "target", " ".join("%-17s" % n for n in NAMES))
for t in TN:
    print("%-10s" % t, " ".join("%7.1e|%-9.1e" % (res[n]["ins"][t], res[n]["out"][t])
                                for n in NAMES))
print("\n(in-sample | HELD-OUT).  A gap of many orders = fitting, not representing.")
