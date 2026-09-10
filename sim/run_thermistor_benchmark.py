"""
Thermistor calibration benchmark for the analog EML fabric simulator.

The go/no-go experiment from the design discussion: learn a thermistor
calibration curve in-situ on non-ideal analog hardware, and ask
  (a) what accuracy survives each non-ideality (sensitivity ranking),
  (b) does in-situ learning beat programming factory-calibrated weights
      onto a mismatched chip (the adaptive-calibration selling point),
  (c) does the learned config still read back as a sensible formula.

Sweeps one non-ideality at a time at 3 levels, at fixed depth (default 3,
where the beta-model is exactly representable), plus a depth sweep on
ideal hardware. Reports median over seeds, in Kelvin.

Usage:
  python3 run_thermistor_benchmark.py             # full sweep (~20-40 min)
  python3 run_thermistor_benchmark.py --quick     # smoke test (~2 min)
"""
import argparse
import json
import math
import time
from pathlib import Path

import torch

from eml_fabric_sim import (
    AnalogConfig, AnalogEMLTree, TrainConfig, make_data, evaluate, train,
)

TARGET_NAMES = ["thermistor_beta", "thermistor_sh"]

# (label, AnalogConfig overrides) — one knob at a time
SWEEP = [
    ("ideal",      {}),
    ("noise-1e-3", {"noise_std": 1e-3}),
    ("noise-3e-3", {"noise_std": 3e-3}),
    ("noise-1e-2", {"noise_std": 1e-2}),
    ("mm-1%",      {"mismatch_gain_std": 0.01, "mismatch_offset_std": 0.005}),
    ("mm-5%",      {"mismatch_gain_std": 0.05, "mismatch_offset_std": 0.025}),
    ("mm-10%",     {"mismatch_gain_std": 0.10, "mismatch_offset_std": 0.05}),
    ("sat-30",     {"sat": 30.0}),
    ("sat-10",     {"sat": 10.0}),
    ("sat-3",      {"sat": 3.0}),
    ("bits-8",     {"weight_bits": 8}),
    ("bits-6",     {"weight_bits": 6}),
    ("bits-4",     {"weight_bits": 4}),
]

DRIFT_DELTAS = [-0.06, -0.03, 0.03, 0.06]


def run_one(target, depth, acfg, seed, tcfg):
    xt, tt, xe, te, scale, unit = make_data(target, seed=1234)
    model = AnalogEMLTree(depth=depth, acfg=acfg, seed=seed)
    train(model, xt, tt, tcfg)
    train_rmse, noisy_rmse = evaluate(model, xt, tt, noisy=True)
    extrap_rmse, _ = evaluate(model, xe, te)
    return model, {
        "train_rmse": train_rmse * scale,
        "noisy_rmse": noisy_rmse * scale,
        "extrap_rmse": extrap_rmse * scale,
        "unit": unit,
    }


def copy_weights(dst, src):
    """Program src's learned weights onto dst's (different) hardware."""
    with torch.no_grad():
        dst.weights.copy_(src.weights)
        dst.readout.copy_(src.readout)


def median(vals):
    v = sorted(vals)
    n = len(v)
    return v[n // 2] if n % 2 else 0.5 * (v[n // 2 - 1] + v[n // 2])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--seeds", type=int, default=6)
    ap.add_argument("--iters", type=int, default=3000)
    ap.add_argument("--depth", type=int, default=3)
    ap.add_argument("--outdir", type=str, default="results")
    args = ap.parse_args()

    sweep = SWEEP
    depths = [1, 2, 3, 4]
    if args.quick:
        args.seeds, args.iters = 2, 800
        sweep = SWEEP[:2] + [SWEEP[5], SWEEP[9], SWEEP[11]]
        depths = [2, 3]

    tcfg = TrainConfig(iters=args.iters)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    results = {"args": vars(args), "sweep": [], "depth_sweep": [], "drift": []}

    # ---- keep ideal-trained models per (target, seed) for transfer/drift ----
    ideal_models = {}

    for target in TARGET_NAMES:
        xt, tt, xe, te, scale, unit = make_data(target, seed=1234)

        for label, over in sweep:
            per_seed = []
            for s in range(args.seeds):
                acfg = AnalogConfig(mismatch_seed=1000 + s, **over)
                model, m = run_one(target, args.depth, acfg, seed=s, tcfg=tcfg)
                m.update({"target": target, "config": label, "seed": s})

                if label == "ideal":
                    ideal_models[(target, s)] = model

                # transfer test: factory (ideal-trained) weights on this chip
                if over.get("mismatch_gain_std", 0) > 0 and (target, s) in ideal_models:
                    twin = AnalogEMLTree(depth=args.depth, acfg=acfg, seed=s)
                    copy_weights(twin, ideal_models[(target, s)])
                    tr, _ = evaluate(twin, xt, tt)
                    m["transfer_rmse"] = tr * scale

                per_seed.append(m)
                results["sweep"].append(m)

            med = median([m["train_rmse"] for m in per_seed])
            best = min(m["train_rmse"] for m in per_seed)
            mex = median([m["extrap_rmse"] for m in per_seed])
            line = (f"[{time.time()-t0:6.0f}s] {target:16s} {label:10s} "
                    f"train med {med:8.3f} best {best:8.3f} {unit}  "
                    f"extrap med {mex:8.3f} {unit}")
            if "transfer_rmse" in per_seed[0]:
                mtr = median([m["transfer_rmse"] for m in per_seed])
                line += f"  transfer med {mtr:8.3f} {unit}"
            print(line, flush=True)

        # ---- depth sweep on ideal hardware ----
        for d in depths:
            per_seed = []
            for s in range(args.seeds):
                _, m = run_one(target, d, AnalogConfig(), seed=s, tcfg=tcfg)
                m.update({"target": target, "depth": d, "seed": s})
                per_seed.append(m)
                results["depth_sweep"].append(m)
            med = median([m["train_rmse"] for m in per_seed])
            best = min(m["train_rmse"] for m in per_seed)
            mex = median([m["extrap_rmse"] for m in per_seed])
            print(f"[{time.time()-t0:6.0f}s] {target:16s} depth-{d}    "
                  f"train med {med:8.3f} best {best:8.3f} {unit}  "
                  f"extrap med {mex:8.3f} {unit}", flush=True)

        # ---- V_T drift on the ideal-trained models ----
        for delta in DRIFT_DELTAS:
            per_seed = []
            for s in range(args.seeds):
                model = ideal_models[(target, s)]
                model.temp_delta = delta
                r, _ = evaluate(model, xt, tt)
                model.temp_delta = 0.0
                per_seed.append(r * scale)
                results["drift"].append(
                    {"target": target, "delta": delta, "seed": s,
                     "rmse": r * scale, "unit": unit})
            print(f"[{time.time()-t0:6.0f}s] {target:16s} drift {delta:+.2f} "
                  f"median rmse {median(per_seed):8.3f} {unit}", flush=True)

        # ---- readback of the best ideal seed ----
        best_s = min(range(args.seeds), key=lambda s: evaluate(
            ideal_models[(target, s)], xt, tt)[0])
        try:
            expr = ideal_models[(target, best_s)].readback(chop=1e-3)
            print(f"readback {target} (best seed {best_s}): {expr}", flush=True)
            results.setdefault("readback", {})[target] = str(expr)
        except Exception as ex:
            print(f"readback {target} failed: {ex}", flush=True)

    tag = "quick" if args.quick else "full"
    out = outdir / f"thermistor_benchmark_{tag}_d{args.depth}.json"
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved {out}  ({time.time()-t0:.0f}s total)")


if __name__ == "__main__":
    main()
