"""Dynamical-systems / ODE application study for the analog EML fabric.

SIMULATION ONLY.  A trained EML fabric is substituted for the NONLINEAR
term of an ODE; the linear part and the integration are done by scipy
(i.e. an idealised conventional analog integrator/summer).  No analog
integrator was designed or simulated at circuit level and nothing was
fabricated.

Hardware configs
  ideal     AnalogConfig()                       -- real-domain math
  pedestal  AnalogConfig(ln_pedestal=2.547)      -- realised cell ln(v+s)
`atten_v` is deliberately LEFT OFF: lambda_v = 1.094/(1.741+2.547) = 0.2551
is DERIVED from the same pedestal, so enabling both double-counts the same
physics.  Finite span is also off (it does not bind on these workloads).

Usage:
  python3 run_ode.py --pilot
  python3 run_ode.py
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from scipy.integrate import solve_ivp

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eml_fabric_sim import AnalogConfig, TrainConfig, train, evaluate  # noqa
from eml_fabric_topo import AnalogEMLFabric, FabricSpec                # noqa

from ode_systems import SYSTEMS, nl_args                               # noqa

PEDESTAL = 2.547
HW = {"ideal": dict(), "pedestal": dict(ln_pedestal=PEDESTAL)}
CFGS = [("mesh", 2, 4, 3), ("mesh", 3, 6, 3), ("mesh", 4, 8, 3)]
RTOL, ATOL = 1e-7, 1e-9


# --------------------------------------------------------------------------
def reference(sys_, n_eval=2001):
    """Exact trajectories from every IC on a common time grid."""
    T = sys_["T"]
    te = np.linspace(0.0, T, n_eval)
    out = []
    for ic in sys_["ics"]:
        s = solve_ivp(sys_["rhs"], (0.0, T), list(ic), t_eval=te,
                      rtol=RTOL, atol=ATOL, method="RK45")
        out.append(s.y)
    return te, out


def training_box(name, refs, pad=0.15):
    P = np.concatenate([nl_args(name, y) for y in refs], axis=0)
    lo, hi = P.min(0), P.max(0)
    mid, half = 0.5 * (lo + hi), 0.5 * (hi - lo) * (1 + 2 * pad)
    return mid - half, mid + half


def make_data(sys_, name, lo, hi, n=768, seed=1234):
    rng = np.random.default_rng(seed)
    nv = sys_["nvars"]
    xt = rng.uniform(lo, hi, size=(n, nv))
    xv = rng.uniform(lo, hi, size=(n, nv))
    return xt, sys_["nl"](xt), xv, sys_["nl"](xv)


def fit(sys_, name, xt, yt, xv, yv, in_off, cfg, hw, seeds, iters):
    """Best-of-seeds fabric fit of the nonlinear term.  Returns model,
    y-scale and the fit metrics."""
    topo, depth, width, window = cfg
    spec = FabricSpec(topology=topo, depth=depth, width=width,
                      window=window, n_vars=sys_["nvars"])
    acfg = AnalogConfig(**HW[hw])
    scale = float(np.sqrt(np.mean(yt ** 2)))
    Xt = torch.tensor(xt + in_off, dtype=torch.float64)
    Tt = torch.tensor(yt / scale, dtype=torch.float64)
    Xv = torch.tensor(xv + in_off, dtype=torch.float64)
    Tv = torch.tensor(yv / scale, dtype=torch.float64)

    best = (float("inf"), None, None)
    for s in range(seeds):
        m = AnalogEMLFabric(spec, acfg, seed=s, var_mode="dense")
        m.init_readout_lstsq(Xt, Tt)
        torch.manual_seed(s)
        train(m, Xt, Tt, TrainConfig(iters=iters))
        tr, _ = evaluate(m, Xt, Tt)
        if tr < best[0] and np.isfinite(tr):
            te, _ = evaluate(m, Xv, Tv)
            best = (tr, te, m)
    return best[2], scale, dict(train_nrmse=best[0], test_nrmse=best[1],
                                cells=spec.n_cells(),
                                params=best[2].n_params() if best[2] else 0)


def fabric_fn(model, scale, in_off):
    off = torch.tensor(in_off, dtype=torch.float64)

    def N(pts):
        with torch.no_grad():
            t = torch.tensor(np.asarray(pts, dtype=float),
                             dtype=torch.float64) + off
            v = model(t, noisy=False)
            return np.nan_to_num(v.numpy(), nan=0.0,
                                 posinf=1e6, neginf=-1e6) * scale
    return N


# --------------------------------------------------------------------------
def integrate_sub(sys_, N, te, ic, blow, chunk=100, budget=8.0):
    """Segment-wise integration of the substituted system so a stiff or
    blowing-up surrogate costs bounded time; returns the part that was
    actually covered."""
    class _Budget(Exception):
        pass

    start = time.time()

    def fun(t, X):
        if time.time() - start > budget:
            raise _Budget()
        return sys_["sub"](t, X, N)

    def ev(t, X):
        return blow - float(np.max(np.abs(X)))
    ev.terminal, ev.direction = True, -1.0

    ys, X0, t0 = [], list(ic), te[0]
    for a in range(0, len(te) - 1, chunk):
        if time.time() - start > budget:
            break
        seg = te[a:a + chunk + 1]
        try:
            s = solve_ivp(fun, (t0, seg[-1]), X0, t_eval=seg[seg >= t0],
                          rtol=1e-6, atol=1e-8, method="RK45", events=ev)
        except Exception:
            break
        if s.y.shape[1] == 0:
            break
        ys.append(s.y if not ys else s.y[:, 1:])
        X0, t0 = list(s.y[:, -1]), float(s.t[-1])
        if s.status != 0 or t0 < seg[-1] - 1e-9:
            break
    return np.concatenate(ys, axis=1) if ys else np.zeros((sys_["dim"], 0))


def closed_loop(sys_, name, N, te, refs, lo, hi):
    """Integrate the fabric-substituted system from every IC."""
    rows = []
    for ic, ref in zip(sys_["ics"], refs):
        R = float(np.sqrt(np.mean(np.sum(ref ** 2, axis=0))))
        Y = integrate_sub(sys_, N, te, ic, blow=50.0 * R)
        n = Y.shape[1]
        if n == 0:
            rows.append(dict(ic=list(ic), t_div=0.0, traj_nrmse=float("inf"),
                             covered=0.0, oob_frac=1.0, inv_drift=None,
                             inv_drift_ref=None))
            continue
        err = np.sqrt(np.sum((Y - ref[:, :n]) ** 2, axis=0))
        tn = float(np.sqrt(np.mean(err ** 2)) / R)
        bad = np.where(err > 0.1 * R)[0]
        t_div = float(te[bad[0]]) if len(bad) else float(te[n - 1])
        if n < len(te):
            t_div = min(t_div, float(te[n - 1]))
        P = nl_args(name, Y)
        oob = float(np.mean(np.any((P < lo) | (P > hi), axis=1)))
        row = dict(ic=list(ic), t_div=t_div, traj_nrmse=tn,
                   covered=float(te[n - 1]), oob_frac=oob)
        if sys_["inv"] is not None:
            i0 = sys_["inv"](np.array(ic))
            iv = sys_["inv"](Y)
            ivr = sys_["inv"](ref[:, :n])
            sc = max(abs(float(i0)), 1e-9)
            row["inv_drift"] = float(np.max(np.abs(iv - i0)) / sc)
            row["inv_drift_ref"] = float(np.max(np.abs(ivr - i0)) / sc)
        rows.append(row)
    return rows


def med(v):
    v = sorted(x for x in v if np.isfinite(x))
    if not v:
        return float("inf")
    n = len(v)
    return v[n // 2] if n % 2 else 0.5 * (v[n // 2 - 1] + v[n // 2])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--iters", type=int, default=2500)
    ap.add_argument("--out", default="results/ode.json")
    a = ap.parse_args()
    names = list(SYSTEMS)[:1] if a.pilot else list(SYSTEMS)
    seeds = 1 if a.pilot else a.seeds
    iters = 300 if a.pilot else a.iters
    cfgs = CFGS[:1] if a.pilot else CFGS

    out = {"note": "SIMULATION ONLY: fabric substituted for the nonlinear "
                   "term inside a scipy-integrated ODE. No analog "
                   "integrator designed/simulated; nothing fabricated.",
           "hw": {k: (v or "AnalogConfig() ideal") for k, v in HW.items()},
           "seeds": seeds, "iters": iters, "rows": []}
    t0 = time.time()
    print(f"{'system':17s} {'hw':9s} {'cells':>5} {'fitNRMSE':>9} "
          f"{'testNRMSE':>9} {'trajNRMSE':>9} {'t_div/T':>9} {'oob':>5} "
          f"{'invdrift':>9}", flush=True)

    for name in names:
        sys_ = SYSTEMS[name]
        te, refs = reference(sys_)
        lo, hi = training_box(name, refs)
        in_off = np.where(lo < 0.5, 0.5 - lo, 0.0)
        xt, yt, xv, yv = make_data(sys_, name, lo, hi)
        for hw in HW:
            for cfg in cfgs:
                m, scale, fm = fit(sys_, name, xt, yt, xv, yv, in_off,
                                   cfg, hw, seeds, iters)
                N = fabric_fn(m, scale, in_off)
                # fit error restricted to the reference trajectories
                Ptr = np.concatenate([nl_args(name, y) for y in refs], 0)
                ytr = sys_["nl"](Ptr)
                on_traj = float(np.sqrt(np.mean((N(Ptr) - ytr) ** 2))
                                / np.sqrt(np.mean(ytr ** 2)))
                rows = closed_loop(sys_, name, N, te, refs, lo, hi)
                r = dict(system=name, hw=hw, cfg=list(cfg), box_lo=lo.tolist(),
                         box_hi=hi.tolist(), in_off=in_off.tolist(),
                         on_traj_nrmse=on_traj, traj=rows, **fm)
                r["traj_nrmse_med"] = med([q["traj_nrmse"] for q in rows])
                r["t_div_med"] = med([q["t_div"] for q in rows])
                r["oob_med"] = med([q["oob_frac"] for q in rows])
                idr = [q.get("inv_drift") for q in rows
                       if q.get("inv_drift") is not None]
                r["inv_drift_med"] = med(idr) if idr else None
                r["inv_drift_ref_med"] = med(
                    [q["inv_drift_ref"] for q in rows
                     if q.get("inv_drift_ref") is not None]) if idr else None
                out["rows"].append(r)
                print(f"{name:17s} {hw:9s} {fm['cells']:5d} "
                      f"{fm['train_nrmse']:9.4f} {fm['test_nrmse']:9.4f} "
                      f"{r['traj_nrmse_med']:9.4f} "
                      f"{r['t_div_med'] / sys_['T']:9.3f} "
                      f"{r['oob_med']:5.2f} "
                      f"{(r['inv_drift_med'] if idr else float('nan')):9.3f} "
                      f"[{time.time() - t0:5.0f}s]", flush=True)
                Path(a.out).parent.mkdir(parents=True, exist_ok=True)
                with open(a.out, "w") as f:
                    json.dump(out, f, indent=2)
    print(f"\nSaved {a.out} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
