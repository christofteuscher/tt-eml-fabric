"""
Go/no-go run 3: AnalogConfig calibrated by sky130 measurements
(silicon/char/, 2026-07-02) instead of guesses.

Measured: NPN exp-argument offset sigma = 0.005 V_T units (MC, tt_mm);
V_T drift = 0.34%/K -> +-10% over +-30C ambient. Kept as estimates until
the log amp is characterized: 2% gain errors (FET-dominated), 3e-3 stage
noise, sat 30, 8-bit weight DACs.

New vs run 2: drift is tested three ways --
  (a) uncompensated +-10% (chip with no PTAT, worst case),
  (b) +-1.5% residual (a PTAT loop with ~85% rejection),
  (c) +-10% followed by 300 iters of in-situ RETRAINING at the drifted
      temperature (the "track drift by continuous adaptation" story).
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
PDK = dict(noise_std=3e-3, mismatch_gain_std=0.02,
           mismatch_offset_std=0.005, sat=30.0, weight_bits=8)


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
            acfg = AnalogConfig(mismatch_seed=1000 + s, **PDK)
            chip = AnalogEMLTree(DEPTH, acfg, seed=s)
            train(chip, xt, tt, TrainConfig(iters=ITERS))

            row = {"target": target, "seed": s}
            row["insitu"], _ = evaluate(chip, xt, tt)
            row["extrap"], _ = evaluate(chip, xe, te)

            # (a) uncompensated drift, (b) PTAT residual
            for tag, d in (("drift10", 0.10), ("ptat", 0.015)):
                chip.temp_delta = d
                row[tag], _ = evaluate(chip, xt, tt)
                chip.temp_delta = 0.0

            # (c) drift + short in-situ retraining at temperature
            state = {k: v.detach().clone() for k, v in chip.state_dict().items()}
            chip.temp_delta = 0.10
            train(chip, xt, tt, TrainConfig(iters=300, lr=0.005, lr_final=0.001))
            row["retrained"], _ = evaluate(chip, xt, tt)
            chip.temp_delta = 0.0
            chip.load_state_dict(state)

            for k in ("insitu", "extrap", "drift10", "ptat", "retrained"):
                row[k] *= scale
            rows.append(row)
            results.append(row)
            print(f"[{time.time()-t0:5.0f}s] {target} seed={s} "
                  f"insitu {row['insitu']:7.3f} drift10 {row['drift10']:8.2f} "
                  f"ptat {row['ptat']:6.2f} retrained {row['retrained']:7.3f} "
                  f"extrap {row['extrap']:8.2f} {unit}", flush=True)

        print(f"\n== {target} (median / best of {SEEDS}, {unit}) ==")
        for k in ("insitu", "drift10", "ptat", "retrained", "extrap"):
            vals = [r[k] for r in rows]
            print(f"  {k:10s} median {median(vals):8.3f}  best {min(vals):8.3f}")
        print(flush=True)

    out = Path("results/pdk_chip.json")
    with open(out, "w") as f:
        json.dump({"config": PDK, "seeds": SEEDS, "iters": ITERS,
                   "rows": results}, f, indent=2)
    print(f"Saved {out} ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
