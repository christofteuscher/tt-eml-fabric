"""
The go/no-go run: ALL non-idealities at realistic levels simultaneously
(run 1 swept them one at a time). Config = 5% mismatch + 3e-3 stage noise
+ sat 30 + 8-bit weight DACs. Reports in-situ accuracy, factory-transfer
accuracy on the same chip, and post-training V_T drift sensitivity.
"""
import json
import time
from pathlib import Path

import torch

from eml_fabric_sim import (
    AnalogConfig, AnalogEMLTree, TrainConfig, make_data, evaluate, train,
)

SEEDS = 8
ITERS = 3000
DEPTH = 3
REALISTIC = dict(noise_std=3e-3, mismatch_gain_std=0.05,
                 mismatch_offset_std=0.025, sat=30.0, weight_bits=8)


def median(vals):
    v = sorted(vals)
    n = len(v)
    return v[n // 2] if n % 2 else 0.5 * (v[n // 2 - 1] + v[n // 2])


def main():
    t0 = time.time()
    results = []
    for target in ("thermistor_beta", "thermistor_sh"):
        xt, tt, xe, te, scale, unit = make_data(target, seed=1234)
        rows = []
        for s in range(SEEDS):
            # factory reference: trained on ideal hardware
            ideal = AnalogEMLTree(DEPTH, AnalogConfig(), seed=s)
            train(ideal, xt, tt, TrainConfig(iters=ITERS))

            # the realistic chip for this seed
            acfg = AnalogConfig(mismatch_seed=1000 + s, **REALISTIC)
            chip = AnalogEMLTree(DEPTH, acfg, seed=s)
            train(chip, xt, tt, TrainConfig(iters=ITERS))

            row = {"target": target, "seed": s}
            row["insitu"], row["insitu_noisy"] = evaluate(chip, xt, tt, noisy=True)
            row["extrap"], _ = evaluate(chip, xe, te)

            twin = AnalogEMLTree(DEPTH, acfg, seed=s)
            with torch.no_grad():
                twin.weights.copy_(ideal.weights)
                twin.readout.copy_(ideal.readout)
            row["transfer"], _ = evaluate(twin, xt, tt)

            for d in (-0.03, 0.03):
                chip.temp_delta = d
                row[f"drift{d:+.2f}"], _ = evaluate(chip, xt, tt)
            chip.temp_delta = 0.0

            for k in ("insitu", "insitu_noisy", "extrap", "transfer",
                      "drift-0.03", "drift+0.03"):
                row[k] *= scale
            rows.append(row)
            results.append(row)
            print(f"[{time.time()-t0:5.0f}s] {target} seed={s} "
                  f"insitu {row['insitu']:7.3f} (noisy {row['insitu_noisy']:6.3f}) "
                  f"transfer {row['transfer']:7.3f} extrap {row['extrap']:8.2f} "
                  f"drift± {row['drift-0.03']:6.2f}/{row['drift+0.03']:6.2f} {unit}",
                  flush=True)

        print(f"\n== {target} (median / best of {SEEDS} seeds, {unit}) ==")
        for k in ("insitu", "insitu_noisy", "transfer", "extrap",
                  "drift-0.03", "drift+0.03"):
            vals = [r[k] for r in rows]
            print(f"  {k:14s} median {median(vals):8.3f}  best {min(vals):8.3f}")
        print(flush=True)

    out = Path("results/combined_chip.json")
    with open(out, "w") as f:
        json.dump({"config": REALISTIC, "seeds": SEEDS, "iters": ITERS,
                   "rows": results}, f, indent=2)
    print(f"Saved {out} ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
