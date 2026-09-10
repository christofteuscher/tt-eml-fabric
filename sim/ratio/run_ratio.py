"""RATIO x CONTRACTING hypothesis test for the analog EML fabric.

SIMULATION ONLY.  A trained EML fabric (or a matched MLP, or a polynomial)
is substituted for the NONLINEAR term of an ODE; the linear part and the
integration are done by scipy.  No analog integrator was designed or
simulated at circuit level and nothing was fabricated.

Hardware configs
  ideal     AnalogConfig()                  -- real-domain math
  pedestal  AnalogConfig(ln_pedestal=2.547) -- realised cell ln(v+s)
`atten_v` is deliberately LEFT OFF: lambda_v = 1.094/(1.741+2.547) = 0.2551
is DERIVED from the same pedestal, so enabling both double-counts the same
physics.  span_decades is off (it does not bind on these workloads).

Matched resources / matched tuning effort
  fabric   mesh depth3 width6 window3 = 18 cells, 163 params (1 input) /
           199 params (2 inputs); SEEDS seeds x ITERS Adam iters, best-of.
  MLP      1 hidden tanh layer sized to the SAME parameter count; the SAME
           number of seeds and the SAME number of Adam iters, best-of.
  poly     least-squares (closed form, i.e. globally optimal in its class),
           best of degrees 2..9; every degree used has FEWER parameters
           than the fabric, so the polynomial is if anything under-resourced.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from scipy.integrate import solve_ivp

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eml_fabric_sim import AnalogConfig, TrainConfig, train, evaluate  # noqa
from eml_fabric_topo import AnalogEMLFabric, FabricSpec                # noqa
from ratio_systems import SYSTEMS, nl_args                             # noqa

PEDESTAL = 2.547
HW = {"ideal": dict(), "pedestal": dict(ln_pedestal=PEDESTAL)}
CFGS = [("mesh", 2, 4, 3), ("mesh", 3, 6, 3)]     # 8 and 18 cells
RTOL, ATOL = 1e-8, 1e-10
NTRAIN = 768


# ---------------------------------------------------------------- reference
def reference(s, n_eval=1201):
    te = np.linspace(0.0, s["T"], n_eval)
    return te, [solve_ivp(s["rhs"], (0.0, s["T"]), list(ic), t_eval=te,
                          rtol=RTOL, atol=ATOL).y for ic in s["ics"]]


def training_box(name, refs, pad=0.15):
    P = np.concatenate([nl_args(name, y) for y in refs], axis=0)
    lo, hi = P.min(0), P.max(0)
    mid, half = 0.5 * (lo + hi), 0.5 * (hi - lo) * (1 + 2 * pad)
    return mid - half, mid + half


def make_data(s, lo, hi, n=NTRAIN, seed=1234):
    rng = np.random.default_rng(seed)
    xt = rng.uniform(lo, hi, size=(n, s["nvars"]))
    xv = rng.uniform(lo, hi, size=(n, s["nvars"]))
    return xt, s["nl"](xt), xv, s["nl"](xv)


def nrmse(pred, targ):
    return float(np.sqrt(np.mean((pred - targ) ** 2))
                 / max(np.sqrt(np.mean(targ ** 2)), 1e-12))


# ------------------------------------------------------------------- models
def fit_fabric(s, xt, yt, xv, yv, in_off, hw, seeds, iters, cfg):
    """One fabric per output component; best-of-seeds on train NRMSE."""
    topo, depth, width, window = cfg
    spec = FabricSpec(topology=topo, depth=depth, width=width, window=window,
                      n_vars=s["nvars"])
    acfg = AnalogConfig(**HW[hw])
    Xt = torch.tensor(xt + in_off, dtype=torch.float64)
    Xv = torch.tensor(xv + in_off, dtype=torch.float64)
    models, scales, npar = [], [], 0
    for k in range(s["n_out"]):
        sc = float(np.sqrt(np.mean(yt[:, k] ** 2))) or 1.0
        Tt = torch.tensor(yt[:, k] / sc, dtype=torch.float64)
        best = (float("inf"), None)
        for sd in range(seeds):
            m = AnalogEMLFabric(spec, acfg, seed=sd, var_mode="dense")
            m.init_readout_lstsq(Xt, Tt)
            torch.manual_seed(sd)
            train(m, Xt, Tt, TrainConfig(iters=iters))
            tr, _ = evaluate(m, Xt, Tt)
            if np.isfinite(tr) and tr < best[0]:
                best = (tr, m)
        models.append(best[1])
        scales.append(sc)
        npar += best[1].n_params() if best[1] is not None else 0
    off = torch.tensor(in_off, dtype=torch.float64)

    def F(P):
        with torch.no_grad():
            t = torch.tensor(np.asarray(P, float), dtype=torch.float64) + off
            cols = [np.nan_to_num(m(t, noisy=False).numpy(), nan=0.0,
                                  posinf=1e6, neginf=-1e6) * sc
                    for m, sc in zip(models, scales)]
        return np.stack(cols, 1)
    return F, dict(params=npar, cells=spec.n_cells() * s["n_out"])


class MLP(torch.nn.Module):
    def __init__(self, nin, h):
        super().__init__()
        self.net = torch.nn.Sequential(torch.nn.Linear(nin, h), torch.nn.Tanh(),
                                       torch.nn.Linear(h, 1))

    def forward(self, x):
        return self.net(x).squeeze(-1)


def fit_mlp(s, xt, yt, xv, yv, target_params, seeds, iters):
    nin = s["nvars"]
    h = max(2, int(round((target_params - 1) / (nin + 2))))
    Xt = torch.tensor(xt, dtype=torch.float64)
    models, scales, npar = [], [], 0
    for k in range(s["n_out"]):
        sc = float(np.sqrt(np.mean(yt[:, k] ** 2))) or 1.0
        Tt = torch.tensor(yt[:, k] / sc, dtype=torch.float64)
        best = (float("inf"), None)
        for sd in range(seeds):
            torch.manual_seed(sd)
            m = MLP(nin, h).double()
            opt = torch.optim.Adam(m.parameters(), lr=0.02)
            sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, iters,
                                                             eta_min=0.002)
            for _ in range(iters):
                opt.zero_grad()
                loss = torch.mean((m(Xt) - Tt) ** 2)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(m.parameters(), 1.0)
                opt.step()
                sch.step()
            with torch.no_grad():
                tr = float(torch.sqrt(torch.mean((m(Xt) - Tt) ** 2))
                           / torch.sqrt(torch.mean(Tt ** 2)))
            if np.isfinite(tr) and tr < best[0]:
                best = (tr, m)
        models.append(best[1])
        scales.append(sc)
        npar += sum(p.numel() for p in best[1].parameters())

    def F(P):
        with torch.no_grad():
            t = torch.tensor(np.asarray(P, float), dtype=torch.float64)
            return np.stack([m(t).numpy() * sc
                             for m, sc in zip(models, scales)], 1)
    return F, dict(params=npar, hidden=h)


def poly_feat(P, deg):
    P = np.asarray(P, float)
    n = P.shape[1]
    if n == 1:
        return np.stack([P[:, 0] ** d for d in range(deg + 1)], 1)
    cols = []
    for i in range(deg + 1):
        for j in range(deg + 1 - i):
            cols.append(P[:, 0] ** i * P[:, 1] ** j)
    return np.stack(cols, 1)


def fit_poly(s, xt, yt, xv, yv, max_params):
    degs = [d for d in (2, 3, 5, 7, 9)
            if poly_feat(xt[:1], d).shape[1] <= max_params]
    best = (float("inf"), None, None)
    for d in degs:
        A, B = poly_feat(xt, d), poly_feat(xv, d)
        W = np.linalg.lstsq(A, yt, rcond=None)[0]
        e = float(np.mean([nrmse(B @ W[:, k], yv[:, k])
                           for k in range(s["n_out"])]))
        if np.isfinite(e) and e < best[0]:
            best = (e, d, W)
    e, d, W = best

    def F(P):
        return poly_feat(P, d) @ W
    return F, dict(params=int(W.size), deg=d)


# --------------------------------------------------------------- closed loop
def integrate_sub(s, N, te, ic, blow, chunk=100, budget=10.0):
    class _B(Exception):
        pass
    t0c = time.time()

    def fun(t, X):
        if time.time() - t0c > budget:
            raise _B()
        return s["sub"](t, X, N)

    def ev(t, X):
        return blow - float(np.max(np.abs(X)))
    ev.terminal, ev.direction = True, -1.0
    ys, X0, t0 = [], list(ic), te[0]
    for a in range(0, len(te) - 1, chunk):
        if time.time() - t0c > budget:
            break
        seg = te[a:a + chunk + 1]
        try:
            r = solve_ivp(fun, (t0, seg[-1]), X0, t_eval=seg[seg >= t0],
                          rtol=1e-6, atol=1e-8, events=ev)
        except Exception:
            break
        if r.y.shape[1] == 0:
            break
        ys.append(r.y if not ys else r.y[:, 1:])
        X0, t0 = list(r.y[:, -1]), float(r.t[-1])
        if r.status != 0 or t0 < seg[-1] - 1e-9:
            break
    return np.concatenate(ys, 1) if ys else np.zeros((s["dim"], 0))


def closed_loop(s, name, N, te, refs, lo, hi):
    rows = []
    for ic, ref in zip(s["ics"], refs):
        R = float(np.sqrt(np.mean(np.sum(ref ** 2, 0))))
        Y = integrate_sub(s, N, te, ic, blow=50.0 * R)
        n = Y.shape[1]
        if n == 0:
            rows.append(dict(t_div=0.0, traj_nrmse=float("inf"),
                             ss_err=float("inf"), oob=1.0, inv=None))
            continue
        err = np.sqrt(np.sum((Y - ref[:, :n]) ** 2, 0))
        bad = np.where(err > 0.1 * R)[0]
        t_div = float(te[bad[0]]) if len(bad) else float(te[n - 1])
        if n < len(te):
            t_div = min(t_div, float(te[n - 1]))
        P = nl_args(name, Y)
        row = dict(t_div=t_div,
                   traj_nrmse=float(np.sqrt(np.mean(err ** 2)) / R),
                   ss_err=(float(err[-1] / R) if n == len(te)
                           else float("inf")),
                   oob=float(np.mean(np.any((P < lo) | (P > hi), 1))))
        if s["inv"] is not None:
            i0 = s["inv"](np.array(ic))
            row["inv"] = float(np.max(np.abs(s["inv"](Y) - i0))
                               / max(abs(float(i0)), 1e-9))
        rows.append(row)
    return rows


def med(v):
    v = sorted(x for x in v if x is not None and np.isfinite(x))
    if not v:
        return float("inf")
    n = len(v)
    return v[n // 2] if n % 2 else 0.5 * (v[n // 2 - 1] + v[n // 2])


def summarise(rows):
    return dict(traj_nrmse=med([r["traj_nrmse"] for r in rows]),
                t_div=med([r["t_div"] for r in rows]),
                ss_err=med([r["ss_err"] for r in rows]),
                oob=med([r["oob"] for r in rows]),
                inv=med([r["inv"] for r in rows]) if rows[0].get("inv")
                is not None else None,
                per_ic=rows)


# --------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", default="")
    ap.add_argument("--seeds", type=int, default=2)
    ap.add_argument("--iters", type=int, default=1500)
    ap.add_argument("--out", default="results/ratio.json")
    a = ap.parse_args()
    names = a.systems.split(",") if a.systems else list(SYSTEMS)

    out = {"note": "SIMULATION ONLY: surrogate substituted for the nonlinear "
                   "term inside a scipy-integrated ODE.",
           "hw": {k: (v or "AnalogConfig() ideal") for k, v in HW.items()},
           "cfgs": [list(c) for c in CFGS], "seeds": a.seeds,
           "iters": a.iters,
           "ntrain": NTRAIN, "rows": []}
    t0 = time.time()
    hdr = (f"{'system':20s} {'cls':15s} {'model':10s} {'testN':>7s} "
           f"{'otrajN':>7s} {'trajN':>8s} {'tdiv/T':>7s} {'ss_err':>8s} "
           f"{'oob':>5s} {'par':>4s}")
    print(hdr, flush=True)

    for name in names:
        s = SYSTEMS[name]
        te, refs = reference(s)
        lo, hi = training_box(name, refs)
        in_off = np.where(lo < 0.5, 0.5 - lo, 0.0)
        xt, yt, xv, yv = make_data(s, lo, hi)
        Ptr = np.concatenate([nl_args(name, y) for y in refs], 0)
        ytr = s["nl"](Ptr)

        fits, tps = {}, []
        for hw in HW:
            for cfg in CFGS:
                nc = sum(FabricSpec(topology=cfg[0], depth=cfg[1],
                                    width=cfg[2]).layer_sizes())
                F, info = fit_fabric(s, xt, yt, xv, yv, in_off, hw,
                                     a.seeds, a.iters, cfg)
                info["cfg"] = list(cfg)
                fits[f"fabric_{hw}_c{nc}"] = (F, info)
                if hw == "ideal":
                    tps.append(info["params"] // s["n_out"])
        # MLP gets the SAME seeds/iters at BOTH matched parameter counts
        for tp in tps:
            F, info = fit_mlp(s, xt, yt, xv, yv, tp, a.seeds, a.iters)
            fits[f"mlp_h{info['hidden']}"] = (F, info)
        fits["poly"] = fit_poly(s, xt, yt, xv, yv, max(tps))

        for mname, (F, info) in fits.items():
            te_n = float(np.mean([nrmse(F(xv)[:, k], yv[:, k])
                                  for k in range(s["n_out"])]))
            ot_n = float(np.mean([nrmse(F(Ptr)[:, k], ytr[:, k])
                                  for k in range(s["n_out"])]))
            cl = summarise(closed_loop(s, name, F, te, refs, lo, hi))
            r = dict(system=name, cls=s["cls"], model=mname, test_nrmse=te_n,
                     on_traj_nrmse=ot_n, T=s["T"], info=info, **cl)
            out["rows"].append(r)
            print(f"{name:20s} {s['cls']:15s} {mname:10s} {te_n:7.4f} "
                  f"{ot_n:7.4f} {cl['traj_nrmse']:8.4f} "
                  f"{cl['t_div'] / s['T']:7.3f} {cl['ss_err']:8.4f} "
                  f"{cl['oob']:5.2f} {info['params']:4d} "
                  f"[{time.time() - t0:5.0f}s]", flush=True)
            Path(a.out).parent.mkdir(parents=True, exist_ok=True)
            json.dump(out, open(a.out, "w"), indent=2)
    print(f"\nSaved {a.out} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
