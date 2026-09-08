"""Condition (ii) measured WITHOUT any fabric: error amplification.

The TRUE nonlinear term is perturbed by a controlled amount -- a systematic
gain error (1+eps) and an unbiased smooth ripple of the same RMS -- and the
substituted system is integrated.  The ratio

    A = closed-loop traj NRMSE / eps

is the system's error-amplification factor: A ~ 1 means a contracting
system that absorbs pointwise error, A >> 1 means it is amplified.  This
separates "the surrogate is accurate" (condition i) from "the dynamics
absorb the error" (condition ii), so the hypothesis can be tested on the
two axes independently.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ratio_systems import SYSTEMS, nl_args              # noqa
from run_ratio import reference, training_box, med      # noqa

EPS = [0.01, 0.03]


def perturbed(s, name, te, refs, eps, kind, rng):
    Ptr = np.concatenate([nl_args(name, y) for y in refs], 0)
    yrms = np.sqrt(np.mean(s["nl"](Ptr) ** 2, axis=0))
    ph = rng.uniform(0, 2 * np.pi, size=(4, Ptr.shape[1]))
    kf = rng.uniform(0.5, 2.0, size=(4, Ptr.shape[1]))

    def N(P):
        P = np.asarray(P, float)
        v = s["nl"](P)
        if kind == "bias":
            return v * (1.0 + eps)
        r = sum(np.prod(np.sin(kf[k] * P + ph[k]), axis=1) for k in range(4))
        r = r / np.sqrt(4 * 0.5 ** Ptr.shape[1])
        return v + eps * yrms[None, :] * r[:, None]

    rows = []
    for ic, ref in zip(s["ics"], refs):
        R = float(np.sqrt(np.mean(np.sum(ref ** 2, 0))))
        try:
            r = solve_ivp(lambda t, X: s["sub"](t, X, N), (0.0, s["T"]),
                          list(ic), t_eval=te, rtol=1e-7, atol=1e-9)
            Y = r.y
        except Exception:
            rows.append(dict(traj_nrmse=float("inf"), t_div=0.0))
            continue
        n = Y.shape[1]
        if n == 0:
            rows.append(dict(traj_nrmse=float("inf"), t_div=0.0))
            continue
        err = np.sqrt(np.sum((Y - ref[:, :n]) ** 2, 0))
        bad = np.where(err > 0.1 * R)[0]
        rows.append(dict(traj_nrmse=float(np.sqrt(np.mean(err ** 2)) / R),
                         t_div=float(te[bad[0]]) if len(bad)
                         else float(te[n - 1])))
    return rows


def main():
    out = {"eps": EPS, "rows": []}
    rng = np.random.default_rng(7)
    t0 = time.time()
    print(f"{'system':20s} {'cls':15s} {'kind':7s} {'eps':>5s} "
          f"{'trajN':>8s} {'A=trajN/eps':>12s} {'tdiv/T':>7s}", flush=True)
    for name, s in SYSTEMS.items():
        te, refs = reference(s)
        for kind in ("bias", "ripple"):
            for eps in EPS:
                rr = perturbed(s, name, te, refs, eps, kind, rng)
                tn = med([q["traj_nrmse"] for q in rr])
                td = med([q["t_div"] for q in rr])
                out["rows"].append(dict(system=name, cls=s["cls"], kind=kind,
                                        eps=eps, traj_nrmse=tn, t_div=td,
                                        amp=tn / eps, T=s["T"]))
                print(f"{name:20s} {s['cls']:15s} {kind:7s} {eps:5.3f} "
                      f"{tn:8.4f} {tn / eps:12.2f} {td / s['T']:7.3f}",
                      flush=True)
    Path("results").mkdir(exist_ok=True)
    json.dump(out, open("results/amp.json", "w"), indent=2)
    print(f"\nSaved results/amp.json ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
