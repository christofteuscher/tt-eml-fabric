"""Matched-CELL-COUNT comparison: standard 2-port EML cell vs the extended
3-port cell (third input summed at the output node, KCL).

Cells are the hardware resource, so every row of a comparison holds the cell
count fixed and varies depth x width at that budget.  Ladder A hardware
(SOFTWARE_RESULTS.md 0.3): ideal, and pedestal = ln_pedestal 2.547 ONLY.
"""
import argparse
import json
import os
import statistics
import sys
import time

import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from eml_fabric_sim import (AnalogConfig, TrainConfig, train, evaluate,  # noqa
                            PEDESTAL_SEGMENTED, make_data)
from eml_fabric_topo import FabricSpec, AnalogEMLFabric                 # noqa
from eml_feynman import make_data_mv                                    # noqa
from eml_fabric_ext import AnalogEMLFabricW, make_expdiff               # noqa

torch.set_num_threads(2)

# (depth, width) pairs at a fixed 12-cell budget
BUDGET = 12
SHAPES = [(1, 12), (2, 6), (3, 4), (4, 3)]


def get_data(name):
    if name in ("thermistor_beta", "thermistor_sh"):
        xt, tt, xe, te, scale, unit = make_data(name, n_train=256, n_extrap=256)
        return xt, tt, xt, tt, scale, "K", 1
    if name == "expdiff":
        xt, tt, xv, tv, s, u = make_expdiff()
        return xt, tt, xv, tv, 1.0, "nrmse", 2
    xt, tt, xv, tv, s, u = make_data_mv(name, n_train=384, n_test=384)
    return xt, tt, xv, tv, 1.0, "nrmse", xt.shape[1]


def run_one(target, arch, hw, depth, width, seed, iters):
    xt, tt, xv, tv, scale, unit, nv = get_data(target)
    acfg = AnalogConfig() if hw == "ideal" else \
        AnalogConfig(ln_pedestal=PEDESTAL_SEGMENTED)
    spec = FabricSpec(topology="mesh", depth=depth, width=width,
                      window=min(3, width), n_vars=nv)
    Cls = AnalogEMLFabric if arch == "std" else AnalogEMLFabricW
    m = Cls(spec, acfg, seed=seed, init_scheme="identity", var_mode="dense")
    m.init_readout_lstsq(xt, tt)
    train(m, xt, tt, TrainConfig(iters=iters, eval_every=100))
    tr, _ = evaluate(m, xt, tt)
    te, _ = evaluate(m, xv, tv)
    return (tr * scale, te * scale, m.n_params(), spec.n_cells())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--iters", type=int, default=1500)
    ap.add_argument("--seeds", type=int, default=3)
    a = ap.parse_args()

    rows = []
    t0 = time.time()
    for target in a.targets.split(","):
        for hw in ("ideal", "pedestal"):
            for depth, width in SHAPES:
                for arch in ("std", "ext"):
                    trs, tes, npar, ncell = [], [], None, None
                    for s in range(a.seeds):
                        tr, te, npar, ncell = run_one(
                            target, arch, hw, depth, width, s, a.iters)
                        trs.append(tr)
                        tes.append(te)
                    rows.append(dict(
                        target=target, hw=hw, arch=arch, depth=depth,
                        width=width, cells=ncell, params=npar,
                        train_med=statistics.median(trs),
                        train_best=min(trs),
                        test_med=statistics.median(tes),
                        test_best=min(tes),
                        test_all=tes))
                    r = rows[-1]
                    print(f"{target:16s} {hw:9s} {arch:3s} d={depth} w={width:2d} "
                          f"cells={ncell:2d} p={npar:4d} "
                          f"test med={r['test_med']:.4g} best={r['test_best']:.4g} "
                          f"[{time.time()-t0:.0f}s]", flush=True)
    with open(a.out, "w") as f:
        json.dump(rows, f, indent=1)
    print("DONE", a.out, f"{time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
