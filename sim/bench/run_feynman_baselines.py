"""
Baselines on a cross-section of the AI Feynman set, to show how the
accuracy-per-parameter of conventional approximators scales with the number
of input variables.  This is the setting where a fabric could plausibly win:
a LUT costs N**d entries, a polynomial C(p+d,d) coefficients.

Metric: nRMSE = RMSE / std(y) on a held-out test set, so equations with
different units are comparable.  1.0 = "explains nothing".
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import baselines as B      # noqa: E402
import feynman as F        # noqa: E402

SELECTION = ["I.6.2a", "I.12.5", "I.25.13", "II.11.28", "I.10.7", "I.16.6",
             "I.26.2", "I.30.3", "III.4.33", "I.41.16", "I.11.19", "I.9.18"]
MAX_LUT_PARAMS = 30000


def make_task(eid, n_train=4000, n_test=4000):
    eq = F.by_id(eid)
    s = F.sampler(eq)
    Xtr, ytr, _ = s(n_train, seed=1)
    Xte, yte, _ = s(n_test, seed=2)
    return eq, B.Task(name=eid, Xtr=Xtr, ytr=ytr, Xte=Xte, yte=yte, unit="")


def main():
    out = {}
    hdr = (f"{'eq':10s} {'d':>2s} {'ops':28s} {'trig':>5s} {'method':14s} "
           f"{'params':>7s} {'nRMSE_test':>11s}")
    print(hdr)
    print("-" * len(hdr))
    for eid in SELECTION:
        eq, task = make_task(eid)
        ops = F.ops_of(eq)
        sd = float(np.std(task.yte))
        res = []
        for deg in (1, 2, 3, 4, 6):
            if len(B._monomials(task.d, deg)) <= 3000:
                res.append(B.fit_poly(task, deg))
        for n in (3, 4, 6, 10, 20, 60):
            if n ** task.d <= MAX_LUT_PARAMS and n ** task.d <= len(task.ytr):
                res.append(B.fit_lut(task, n))
        for (w, h) in ((16, 2), (32, 2)):
            runs = [B.fit_mlp(task, w, h, seed=s, iters=2000) for s in (0, 1)]
            res.append(min(runs, key=lambda r: r.rmse_test))
        for r in res:
            r.extra["nrmse_test"] = r.rmse_test / sd
            r.extra["nrmse_train"] = r.rmse_train / sd
        best = {}
        for r in res:
            fam = r.method.split("-")[0].split("[")[0]
            fam = "poly" if fam.startswith("poly") else fam
            if fam not in best or r.extra["nrmse_test"] < best[fam].extra["nrmse_test"]:
                best[fam] = r
        for fam in ("poly", "lut", "mlp"):
            if fam in best:
                r = best[fam]
                print(f"{eid:10s} {task.d:2d} {','.join(ops):28s} "
                      f"{'YES' if F.is_trig_blocked(ops) else 'no':>5s} "
                      f"{r.method:14s} {r.params:7d} "
                      f"{r.extra['nrmse_test']:11.3g}")
        out[eid] = {"d": task.d, "ops": ops,
                    "trig_blocked": F.is_trig_blocked(ops),
                    "results": B.to_dicts(res)}
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "results_feynman_baselines.json")
    with open(p, "w") as fh:
        json.dump(out, fh, indent=1)
    print(f"\nwrote {p}")


if __name__ == "__main__":
    main()
