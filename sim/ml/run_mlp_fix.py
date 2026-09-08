"""Recompute every MLP baseline with held-out-validation model selection.

The first pass selected the grid winner on training NRMSE, which picks the
most overfitting member of the grid and unfairly handicaps the baseline.
The fabric results are untouched; only the MLP column is recomputed.
"""
import json
import time
from pathlib import Path

import torch

from ml_common import ITERS, SEEDS, SYNTH, mix_task, real_task, run_mlp_val, synth_task

torch.set_num_threads(1)
OUT = Path(__file__).resolve().parent / "results"

# (label, data, matched parameter budget taken from the fabric run)
TASKS = []
for t in ["diabetes", "wine_proline"]:
    TASKS.append((f"reg/{t}", real_task(t)))
for t in SYNTH:
    TASKS.append((f"bias/{t}", synth_task(t)))
for tv in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
    TASKS.append((f"mix/{tv:.1f}", mix_task(tv)))


def budget(label):
    """Fabric parameter count for the matched comparison (mesh d4 w8 w3)."""
    from eml_fabric_topo import FabricSpec, AnalogEMLFabric
    from eml_fabric_sim import AnalogConfig
    d = dict(TASKS)[label][0].shape[1]
    m = AnalogEMLFabric(FabricSpec(topology="mesh", depth=4, width=8,
                                   window=3, n_vars=d), AnalogConfig(),
                        seed=0, var_mode="dense")
    return m.n_params()


def main():
    t0 = time.time()
    res = {}
    for label, data in TASKS:
        P = budget(label)
        r = run_mlp_val(*data, P=P, seeds=SEEDS, iters=ITERS)
        res[label] = r
        print(f"{label:18s} P={r['params']:5d} (fabric {P}) "
              f"{str(r['hidden']):10s} {r['act']:4s} lr={r['lr']:<6} "
              f"val {r['val']:.4f} train {r['train']:.4f} "
              f"test {r['test']:.4f} (best {r['test_best']:.4f}) "
              f"[{time.time()-t0:.0f}s]", flush=True)
        with open(OUT / "ml_mlp_val.json", "w") as f:
            json.dump(res, f, indent=2, default=str)
    print(f"Saved ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
