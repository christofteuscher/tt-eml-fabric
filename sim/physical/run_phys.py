#!/usr/bin/env python3
"""
Run the operators/op_search.py metric suite over the PHYSICS-NATIVE operators,
plus one new metric that the previous search did not have:

  contr  = fraction of enumerated operating points at which BOTH port gains
           satisfy |df/dp| <= 1, i.e. the composition step does not amplify the
           error already present on its inputs.  This is the *necessary*
           condition for the substrate to give any error restoration at all.
  contr5 = same with the stricter threshold 0.5.

Baselines from the previous search are re-run so the numbers are same-seed
comparable.
"""
import json, os, sys, time
import numpy as np
import phys_ops                                            # registers PHYS into OS.OPS
import op_search as OS

np.seterr(all="ignore")
OUT = os.path.dirname(os.path.abspath(__file__))
T0 = time.time()
MAXC = 150000


def contr(name, seed=11):
    """Corpus-weighted contraction statistics.  Same grammar/grid/caps as
    op_search (this is deepen.corpus's enumeration, inlined so operators/ is
    untouched)."""
    f, dfu, dfv, dom, _ = OS.OPS[name]
    V = np.array([np.ones(OS.NG), OS.X])
    K = {k.tobytes(): 1 for k in OS.key_of(V)}
    prev = 0
    n1 = n5 = ntot = 0
    for d in range(1, 5):
        n = len(V)
        if n * n <= 4_000_000:
            ia, ib = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
            ia, ib = ia.ravel(), ib.ravel()
            m = ~((ia < prev) & (ib < prev)); ia, ib = ia[m], ib[m]
        else:
            r = np.random.default_rng(seed + d)
            ia = r.integers(0, n, 400000); ib = r.integers(0, n, 400000)
        acc = []
        for s in range(0, len(ia), 300000):
            A, B = V[ia[s:s + 300000]], V[ib[s:s + 300000]]
            ok = dom(A, B).all(1) & (np.abs(A) < OS.UCAP).all(1) & (np.abs(B) < OS.BIG).all(1)
            if not ok.any():
                continue
            A, B = A[ok], B[ok]
            Y = f(A, B)
            g = np.isfinite(Y).all(1) & (np.abs(Y) < OS.BIG).all(1)
            if not g.any():
                continue
            A, B, Y = A[g], B[g], Y[g]
            a_, b_ = np.abs(dfu(A, B)), np.abs(dfv(A, B))
            fin = np.isfinite(a_).all(1) & np.isfinite(b_).all(1)
            mx = np.maximum(a_, b_).max(1)
            n1 += int((fin & (mx <= 1.0)).sum())
            n5 += int((fin & (mx <= 0.5)).sum())
            ntot += int(fin.sum())
            acc.append(Y)
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
    return (n1 / max(ntot, 1), n5 / max(ntot, 1))


NAMES = sys.argv[1].split(",") if len(sys.argv) > 1 else (
    list(phys_ops.PHYS) + ["eml", "sag", "sna", "lse"])

res = []
for nm in NAMES:
    r = OS.run(nm)
    c1, c5 = contr(nm)
    r["contr"], r["contr5"] = round(c1, 4), round(c5, 4)
    res.append(r)
    print("%-4s |F|=%-7d ood=%.3f dec=%7.2f asym=%6.2f dom=%.3f live=%.3f "
          "contr=%.3f sin=%.2e  %.1fs"
          % (nm, r["nclass"], r["ood"][-1], r["decades"], r["asym"], r["dom_box"],
             r["live"], r["contr"], r["targets"]["sin(x)"], time.time() - T0), flush=True)

json.dump(res, open(os.path.join(OUT, "phys_search.json"), "w"), indent=1)
print("wrote phys_search.json", flush=True)

# ---- the expressiveness / restoration trade-off, over BOTH searches --------
try:
    old = json.load(open(os.path.join(
        os.path.dirname(OUT), "operators", "op_search.json")))
except Exception:
    old = []
have = {r["op"] for r in res}
allr = res + [o for o in old if o["op"] not in have]
x = np.array([r["live"] for r in allr])
y = np.log10(np.array([max(r["nclass"], 1) for r in allr], float))
ok = np.isfinite(x) & np.isfinite(y)
print("\nEXPRESSIVENESS vs CONDITIONING over %d operators:" % ok.sum())
print("  corr(live, log10|F|)   = %+.3f" % np.corrcoef(x[ok], y[ok])[0, 1])
c = np.array([r.get("contr", np.nan) for r in allr])
ok2 = np.isfinite(c) & np.isfinite(y)
if ok2.sum() > 2:
    print("  corr(contr, log10|F|)  = %+.3f  (n=%d, physical set only)"
          % (np.corrcoef(c[ok2], y[ok2])[0, 1], ok2.sum()))
