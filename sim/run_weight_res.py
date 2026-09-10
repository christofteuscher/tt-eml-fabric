#!/usr/bin/env python3
"""Does the silicon's weight resolution suffice, and how much does cell
count cost?

The existing RESULTS.md rows ("4-bit weights", "6-bit weights") use the
sim default weight_range = 8.0, which is NOT what the silicon does.  The
MDACs are radix-4, all-unit-device, signed:

  2 digits (mdac2_*_d2)  value = a + b/4      a,b in 0..3
                         -> +-3.75 in steps of 0.25   (31 levels)
  3 digits (mdac2_*)     value = a + b/4 + c/16
                         -> +-3.9375 in steps of 1/16 (127 levels)

In the sim's parameterisation (step = 2*range/(2**bits - 1)) those are
  2-digit ~ weight_bits=5, weight_range=3.75
  3-digit ~ weight_bits=7, weight_range=3.9375
so the silicon's "4 magnitude bits" is finer than the RESULTS.md 4-bit
row by a factor of four, and the honest comparison is the one below.

Cell count: AnalogEMLTree is a binary tree, depth d -> 2**d - 1 cells.
The chip is a 2-cell CHAIN, which is between depth 1 (1 cell) and depth 2
(3 cells); both are reported so the cost of dropping to 2 cells is
visible rather than argued.

Run: python3 run_weight_res.py [--seeds N] [--iters N]
"""
import argparse, json, statistics as st
from eml_fabric_sim import AnalogConfig, TrainConfig
from run_thermistor_benchmark import run_one

CONFIGS = {
    "ideal (continuous)":      dict(weight_bits=0),
    "3-digit MDAC (silicon)":  dict(weight_bits=7, weight_range=3.9375),
    "2-digit MDAC (silicon)":  dict(weight_bits=5, weight_range=3.75),
    "1-digit (for contrast)":  dict(weight_bits=3, weight_range=3.0),
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=4)
    ap.add_argument("--iters", type=int, default=1500)
    ap.add_argument("--depths", type=int, nargs="+", default=[1, 2])
    a = ap.parse_args()
    tcfg = TrainConfig(iters=a.iters)
    out = {}
    for target in ("thermistor_beta", "thermistor_sh"):
        for depth in a.depths:
            ncell = 2 ** depth - 1
            for name, over in CONFIGS.items():
                rs = []
                for s in range(a.seeds):
                    acfg = AnalogConfig(mismatch_seed=1000 + s, **over)
                    _, m = run_one(target, depth, acfg, seed=s, tcfg=tcfg)
                    rs.append(m["train_rmse"])
                key = (target, depth, name)
                out[str(key)] = rs
                print(f"{target:16s} depth{depth} ({ncell} cell) {name:24s} "
                      f"median {st.median(rs):7.3f} K   best {min(rs):7.3f} K",
                      flush=True)
    json.dump(out, open("results/weight_res.json", "w"), indent=1)

if __name__ == "__main__":
    main()
