"""Error budget: how much pointwise error can the closed loop absorb?

No fabric here.  The TRUE nonlinear term is perturbed by a controlled
amount -- a pure gain error (systematic, 1+eps) and an unbiased random
smooth ripple of the same RMS -- and the substituted system is integrated.
This calibrates the fit-error -> trajectory-error transfer, and separates
"systematic bias" from "zero-mean noise", which is the mechanism behind
the conserved-quantity result.

Also reports a least-squares POLYNOMIAL baseline for each nonlinear term
(same box, same samples), so a fabric NRMSE can be read against a cheap
alternative of comparable parameter count -- in particular for the
pendulum, where the EML grammar is closed to trigonometry.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ode_systems import SYSTEMS, nl_args                    # noqa
from run_ode import reference, training_box, make_data, med  # noqa

EPS = [0.0, 0.003, 0.01, 0.03, 0.1]


def poly_features(P, deg):
    n = P.shape[1]
    cols, pows = [np.ones(len(P))], [(0,) * n]
    if n == 1:
        for d in range(1, deg + 1):
            cols.append(P[:, 0] ** d)
            pows.append((d,))
    else:
        for i in range(deg + 1):
            for j in range(deg + 1 - i):
                if i + j == 0:
                    continue
                cols.append(P[:, 0] ** i * P[:, 1] ** j)
                pows.append((i, j))
    return np.stack(cols, 1)


def perturbed(sys_, name, te, refs, lo, hi, eps, kind, rng):
    """Integrate with N = true * (1+eps)  [bias]  or  true + zero-mean
    smooth ripple of RMS eps*RMS(true)  [ripple]."""
    Ptr = np.concatenate([nl_args(name, y) for y in refs], 0)
    yrms = float(np.sqrt(np.mean(sys_["nl"](Ptr) ** 2)))
    ph = rng.uniform(0, 2 * np.pi, size=(4, Ptr.shape[1]))
    kf = rng.uniform(0.5, 2.0, size=(4, Ptr.shape[1]))

    def N(P):
        P = np.asarray(P, dtype=float)
        v = sys_["nl"](P)
        if kind == "bias":
            return v * (1.0 + eps)
        r = np.zeros(len(P))
        for k in range(4):
            r = r + np.prod(np.sin(kf[k] * P + ph[k]), axis=1)
        r = r / np.sqrt(4 * 0.5 ** Ptr.shape[1])
        return v + eps * yrms * r

    rows = []
    for ic, ref in zip(sys_["ics"], refs):
        R = float(np.sqrt(np.mean(np.sum(ref ** 2, axis=0))))
        s = solve_ivp(lambda t, X: sys_["sub"](t, X, N), (0.0, sys_["T"]),
                      list(ic), t_eval=te, rtol=1e-7, atol=1e-9)
        Y = s.y
        n = Y.shape[1]
        err = np.sqrt(np.sum((Y - ref[:, :n]) ** 2, axis=0))
        bad = np.where(err > 0.1 * R)[0]
        row = dict(traj_nrmse=float(np.sqrt(np.mean(err ** 2)) / R),
                   t_div=float(te[bad[0]]) if len(bad) else float(te[n - 1]))
        if sys_["inv"] is not None:
            i0 = sys_["inv"](np.array(ic))
            row["inv_drift"] = float(
                np.max(np.abs(sys_["inv"](Y) - i0)) / max(abs(float(i0)), 1e-9))
        rows.append(row)
    return rows


def main():
    out = {"eps": EPS, "budget": [], "poly": []}
    t0 = time.time()
    print("=== polynomial baseline (NRMSE on the box; nterms = params) ===",
          flush=True)
    for name, sys_ in SYSTEMS.items():
        te, refs = reference(sys_)
        lo, hi = training_box(name, refs)
        xt, yt, xv, yv = make_data(sys_, name, lo, hi)
        sc = float(np.sqrt(np.mean(yv ** 2)))
        line = [name]
        for deg in (2, 3, 5):
            A, B = poly_features(xt, deg), poly_features(xv, deg)
            w = np.linalg.lstsq(A, yt, rcond=None)[0]
            e = float(np.sqrt(np.mean((B @ w - yv) ** 2)) / sc)
            out["poly"].append(dict(system=name, deg=deg, nterms=A.shape[1],
                                    test_nrmse=e))
            line.append(f"deg{deg}({A.shape[1]}) {e:.2e}")
        print("  " + "  ".join(line), flush=True)

    print("\n=== closed-loop error budget (median over 5 ICs) ===", flush=True)
    print(f"{'system':17s} {'kind':7s} {'eps':>6} {'trajNRMSE':>10} "
          f"{'t_div/T':>8} {'invdrift':>9}", flush=True)
    rng = np.random.default_rng(7)
    for name, sys_ in SYSTEMS.items():
        te, refs = reference(sys_)
        lo, hi = training_box(name, refs)
        for kind in ("bias", "ripple"):
            for eps in EPS:
                if eps == 0.0 and kind == "ripple":
                    continue
                rr = perturbed(sys_, name, te, refs, lo, hi, eps, kind, rng)
                idr = [q.get("inv_drift") for q in rr
                       if q.get("inv_drift") is not None]
                rec = dict(system=name, kind=kind, eps=eps, rows=rr,
                           traj_nrmse_med=med([q["traj_nrmse"] for q in rr]),
                           t_div_med=med([q["t_div"] for q in rr]),
                           inv_drift_med=med(idr) if idr else None)
                out["budget"].append(rec)
                print(f"{name:17s} {kind:7s} {eps:6.3f} "
                      f"{rec['traj_nrmse_med']:10.4f} "
                      f"{rec['t_div_med'] / sys_['T']:8.3f} "
                      f"{(rec['inv_drift_med'] if idr else float('nan')):9.4f}",
                      flush=True)
    Path("results").mkdir(parents=True, exist_ok=True)
    with open("results/ode_budget.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nSaved results/ode_budget.json ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
