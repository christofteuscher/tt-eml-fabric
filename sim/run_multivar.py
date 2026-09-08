"""
Multivariate (AI Feynman) study for the analog EML fabric.

Two questions:

  A  Can the fabric fit f(x1..xn) at all, and does the leaf-to-variable
     assignment want to be LEARNED (dense coefficients on every rail, or
     softmax-selected rails) or SEARCHED (random hard assignments, keep the
     best probe)?  Reference points: the best constant predictor (NRMSE
     1.0 by construction, since the target is normalised to unit RMS) and
     ordinary least squares in the raw variables.

  B  Does the answer survive the measured silicon cell (the ln pedestal,
     on top of the corrected PDK chip)?  The v-port attenuation is NOT
     added: lambda_v = 1.094/(1.741+2.547) = 0.2551 is derived from the
     pedestal, so enabling both double-counts it (see silicon_config()).
     The 8.372-decade span is off because it does not bind here.

Usage:
  python3 run_multivar.py --pilot     # 2 targets, 1 seed
  python3 run_multivar.py
"""
import argparse
import json
import time
from pathlib import Path

import torch

from eml_fabric_sim import (AnalogConfig, TrainConfig, evaluate, train,
                            silicon_config)
from eml_fabric_topo import AnalogEMLFabric, FabricSpec, search_assignments
from eml_feynman import FEYNMAN, make_data_mv, n_vars
from run_scaling import PDK, median

ALL_TARGETS = list(FEYNMAN)
MODES = ["dense", "soft", "search"]


def ols_baseline(xt, tt, xv, tv):
    """NRMSE of ordinary least squares on the raw variables (+ constant)."""
    A = torch.cat([xt, torch.ones(xt.shape[0], 1, dtype=xt.dtype)], 1)
    B = torch.cat([xv, torch.ones(xv.shape[0], 1, dtype=xv.dtype)], 1)
    w = torch.linalg.lstsq(A, tt.unsqueeze(1)).solution
    f = lambda M, y: float(torch.sqrt(torch.mean((M @ w - y.unsqueeze(1)) ** 2)))
    return f(A, tt), f(B, tv)


def build(spec, acfg, seed, mode):
    return AnalogEMLFabric(spec, acfg, seed=seed,
                           var_mode=("fixed" if mode == "search" else mode))


def run_one(target, mode, acfg, seed, spec_kw, iters, probes, probe_iters):
    nv = n_vars(target)
    xt, tt, xv, tv, scale, unit = make_data_mv(target)
    spec = FabricSpec(n_vars=nv, **spec_kw)
    tcfg = TrainConfig(iters=iters)
    t0 = time.time()

    if mode == "search":
        m, _, probe_scores = search_assignments(
            spec, acfg, xt, tt, n_probe=probes, probe_iters=probe_iters,
            seed=seed)
        extra = {"probe_best": min(probe_scores),
                 "probe_median": median(probe_scores)}
    else:
        m = build(spec, acfg, seed, mode)
        m.init_readout_lstsq(xt, tt)
        extra = {}
    torch.manual_seed(seed)
    train(m, xt, tt, tcfg)
    tr, _ = evaluate(m, xt, tt)
    te, _ = evaluate(m, xv, tv)
    return dict(target=target, n_vars=nv, mode=mode, seed=seed,
                train_nrmse=tr, test_nrmse=te, params=m.n_params(),
                cells=m.n_cells, secs=round(time.time() - t0, 1), **extra)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--iters", type=int, default=2500)
    ap.add_argument("--probes", type=int, default=12)
    ap.add_argument("--probe-iters", type=int, default=250)
    ap.add_argument("--out", default="results/multivar.json")
    args = ap.parse_args()

    targets = ALL_TARGETS[:2] if args.pilot else ALL_TARGETS
    seeds = 1 if args.pilot else args.seeds
    iters = 400 if args.pilot else args.iters
    spec_kw = dict(topology="mesh", depth=4, width=8, window=3)
    out = {"spec": spec_kw, "iters": iters, "seeds": seeds,
           "probes": args.probes, "rows": [], "baseline": {}}
    t0 = time.time()

    print("=== baselines (NRMSE; 1.0 = predicts nothing) ===", flush=True)
    for tg in targets:
        xt, tt, xv, tv, sc, _ = make_data_mv(tg)
        a, b = ols_baseline(xt, tt, xv, tv)
        out["baseline"][tg] = {"ols_train": a, "ols_test": b,
                               "n_vars": n_vars(tg), "y_scale": sc}
        print(f"{tg:9s} nv={n_vars(tg)} OLS train {a:.4f} test {b:.4f}",
              flush=True)

    print("\n=== A: assignment mode, ideal hardware ===", flush=True)
    hw = [("ideal", AnalogConfig())]
    if not args.pilot:
        # silicon_config() = ln pedestal only (the physical cell).  Before
        # 2026-08 it also switched on atten_v and the span, which double-
        # counted the v-port loss; rows in results/multivar.json labelled
        # "silicon+pdk" are from that superseded configuration.
        hw.append(("pedestal+pdk", silicon_config(**PDK)))
    print(f"{'target':9s} {'nv':>3} {'hw':12s} {'mode':7s} "
          f"{'train med':>10} {'train best':>10} {'test med':>10}", flush=True)
    for hw_name, acfg_proto in hw:
        for tg in targets:
            for mode in MODES:
                tr, te = [], []
                for s in range(seeds):
                    acfg = AnalogConfig(**dict(acfg_proto.__dict__,
                                               mismatch_seed=1000 + s))
                    r = run_one(tg, mode, acfg, s, spec_kw, iters,
                                args.probes, args.probe_iters)
                    r["hw"] = hw_name
                    out["rows"].append(r)
                    tr.append(r["train_nrmse"])
                    te.append(r["test_nrmse"])
                print(f"{tg:9s} {n_vars(tg):3d} {hw_name:12s} {mode:7s} "
                      f"{median(tr):10.4f} {min(tr):10.4f} {median(te):10.4f} "
                      f"[{time.time()-t0:5.0f}s]", flush=True)
                Path(args.out).parent.mkdir(exist_ok=True)
                with open(args.out, "w") as f:
                    json.dump(out, f, indent=2)

    print(f"\nSaved {args.out} ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
