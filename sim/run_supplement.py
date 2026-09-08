"""
Supplementary run: completes the 2x2 of {standard, identity} init crossed
with {ideal, pdk} hardware, which the main sweep skips to save time.

Without the standard+pdk cell you cannot attribute the improvement in the
realistic-chip number to the initialisation rather than to the extra
iteration budget, so this is the control that makes the claim defensible.
Also re-runs the legacy AnalogEMLTree at its own settings as a direct tie
back to RESULTS.md run 3.
"""
import json
import time
from pathlib import Path

import torch

from eml_fabric_sim import (AnalogConfig, TrainConfig, AnalogEMLTree,
                            evaluate, train)
from eml_fabric_topo import AnalogEMLFabric, FabricSpec
from run_scaling import make_data, median, PDK

SEEDS = 3
ITERS = 4000
DEPTHS = [3, 4, 6, 8]
TARGETS = ["thermistor_sh", "osc_k3"]


def main():
    out = {"seeds": SEEDS, "iters": ITERS, "pdk": PDK, "rows": [], "legacy": []}
    tcfg = TrainConfig(iters=ITERS)
    t0 = time.time()

    print("=== standard init on the corrected-PDK chip (the missing cell) ===")
    print(f"{'target':16s} {'init':9s} {'cfg':6s} {'depth':>5} "
          f"{'train med':>10} {'train best':>10}", flush=True)
    for target in TARGETS:
        xt, tt, xv, tv, scale, unit = make_data(target)
        for d in DEPTHS:
            per = []
            for s in range(SEEDS):
                acfg = AnalogConfig(mismatch_seed=1000 + s, **PDK)
                m = AnalogEMLFabric(FabricSpec("tree", d), acfg, seed=s,
                                    init_scheme="standard")
                train(m, xt, tt, tcfg)
                r, _ = evaluate(m, xt, tt)
                per.append(r * scale)
                out["rows"].append(dict(target=target, init="standard",
                                        cfg="pdk", depth=d, seed=s,
                                        train_rmse=r * scale, unit=unit))
            print(f"{target:16s} {'standard':9s} {'pdk':6s} {d:5d} "
                  f"{median(per):10.4f} {min(per):10.4f} "
                  f"[{time.time()-t0:5.0f}s]", flush=True)

    print("\n=== legacy AnalogEMLTree, same data, as a tie to RESULTS.md ===",
          flush=True)
    for target in TARGETS:
        xt, tt, xv, tv, scale, unit = make_data(target)
        for d in [3]:
            per = []
            for s in range(SEEDS):
                acfg = AnalogConfig(mismatch_seed=1000 + s, **PDK)
                m = AnalogEMLTree(depth=d, acfg=acfg, seed=s)
                train(m, xt, tt, tcfg)
                r, _ = evaluate(m, xt, tt)
                per.append(r * scale)
                out["legacy"].append(dict(target=target, depth=d, seed=s,
                                          train_rmse=r * scale, unit=unit))
            print(f"{target:16s} {'legacy':9s} {'pdk':6s} {d:5d} "
                  f"{median(per):10.4f} {min(per):10.4f} "
                  f"[{time.time()-t0:5.0f}s]", flush=True)

    Path("results").mkdir(exist_ok=True)
    with open("results/supplement.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nSaved results/supplement.json ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
