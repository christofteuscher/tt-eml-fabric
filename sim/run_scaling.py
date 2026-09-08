"""
Depth- and topology-scaling study for the analog EML fabric.

Three experiments, in the order the conclusions depend on each other:

  A  TRAINABILITY GATE. Depth sweep on the binary tree, standard vs
     near-identity init. RESULTS.md run 1 found depth-3 best and depth-4
     worse ("no gain, harder optimisation"). Before any claim about what a
     large fabric can represent, we have to know whether that turnover is
     the fabric or the optimiser. If identity init removes it, the old
     depth ceiling was an artefact.

  B  FORWARD ERROR ACCUMULATION, no training. Freeze one set of weights,
     evaluate on an ideal chip and on a mismatched chip, and measure how
     the divergence grows with depth. This isolates the physics (a gain
     error g on the exp argument gives exp((1+g)u) = exp(u)exp(gu), so the
     per-stage relative error is ~g|u| and the question is whether it
     compounds as sqrt(depth) or geometrically) from anything the
     optimiser does.

  C  TOPOLOGY. tree vs reuse-DAG vs local mesh, compared both at equal
     depth and at equal cell budget. A tree cannot share subexpressions,
     which is the same limitation that makes Odrzywolek's compiler emit
     K=41 for multiplication where direct search finds K=17.

Mismatch defaults use the CORRECTED gain sigma of 3 percent (fabric_sim
run 3 assumed 2 percent; log-interpolating the W=8 mirror MC row between
4.30 % at 1 uA and 1.93 % at 10 uA gives 4.30 % * (1.93/4.30)^log10(3) =
2.96 % at the ~3 uA the chain traces actually sit at).

Usage:
  python3 run_scaling.py --pilot      # ~5 min sanity run
  python3 run_scaling.py              # full study
"""
import argparse
import json
import math
import time
from pathlib import Path

import torch

from eml_fabric_sim import AnalogConfig, TrainConfig, rmse, evaluate, train
from eml_fabric_topo import AnalogEMLFabric, FabricSpec, REAL_DTYPE

# ---------------------------------------------------------------------------
# Targets: the two sensor curves from the original benchmark (controls, both
# easy and effectively saturated by depth 3) plus an explicit difficulty
# ladder so that depth has something to buy. sin(k ln x) is NOT exactly
# representable in a real-valued EML fabric -- Odrzywolek's trig construction
# needs complex intermediates -- so this measures approximation capacity.
# ---------------------------------------------------------------------------

def thermistor_beta(x):
    B, T25 = 3435.0, 298.15
    return 1.0 / (1.0 / T25 + torch.log(x) / B) / 100.0


def thermistor_sh(x):
    A, B, C = 1.129241e-3, 2.341077e-4, 8.775468e-8
    lr = torch.log(x * 10000.0)
    return 1.0 / (A + B * lr + C * lr ** 3) / 100.0


def _osc(k):
    def f(x):
        return torch.sin(k * torch.log(x))
    return f


TARGETS = {
    "thermistor_beta": (thermistor_beta, (0.30, 7.85), 100.0, "K"),
    "thermistor_sh":   (thermistor_sh,   (0.30, 7.85), 100.0, "K"),
    "osc_k3":          (_osc(3.0),       (0.30, 7.85), 1.0,  "au"),
    "osc_k5":          (_osc(5.0),       (0.30, 7.85), 1.0,  "au"),
    "osc_k8":          (_osc(8.0),       (0.30, 7.85), 1.0,  "au"),
}

# Corrected-PDK realistic chip.
PDK = dict(mismatch_gain_std=0.03, mismatch_offset_std=0.005,
           noise_std=3e-3, sat=30.0, weight_bits=8)


def make_data(name, n_train=256, n_test=512, seed=1234):
    fn, (lo, hi), scale, unit = TARGETS[name]
    g = torch.Generator().manual_seed(seed)
    xt = torch.exp(torch.empty(n_train, dtype=REAL_DTYPE).uniform_(
        math.log(lo), math.log(hi), generator=g))
    xv = torch.exp(torch.empty(n_test, dtype=REAL_DTYPE).uniform_(
        math.log(lo), math.log(hi), generator=g))
    return xt, fn(xt), xv, fn(xv), scale, unit


def median(v):
    v = sorted(v)
    n = len(v)
    return v[n // 2] if n % 2 else 0.5 * (v[n // 2 - 1] + v[n // 2])


def run_one(spec, acfg, target, seed, tcfg, init_scheme):
    xt, tt, xv, tv, scale, unit = make_data(target)
    m = AnalogEMLFabric(spec, acfg, seed=seed, init_scheme=init_scheme)
    if init_scheme == "identity":
        m.init_readout_lstsq(xt, tt)
    train(m, xt, tt, tcfg)
    tr, _ = evaluate(m, xt, tt)
    te, _ = evaluate(m, xv, tv)
    return m, {"train_rmse": tr * scale, "test_rmse": te * scale,
               "unit": unit, "cells": m.n_cells, "params": m.n_params()}


# ---------------------------------------------------------------------------
# A: trainability gate
# ---------------------------------------------------------------------------

def exp_a(args, tcfg, out, t0):
    print("\n=== A: depth sweep, tree, standard vs near-identity init ===",
          flush=True)
    print(f"{'target':16s} {'cfg':6s} {'init':9s} {'depth':>5} {'cells':>6} "
          f"{'train med':>10} {'train best':>10} {'test med':>10}", flush=True)
    # 'standard' is the legacy init and only needs to be run on ideal
    # hardware -- its job here is to reproduce the depth-4 turnover, not to
    # be characterised again under mismatch.
    combos = [("ideal", {}, "standard"), ("ideal", {}, "identity"),
              ("pdk", PDK, "identity")]
    for target in args.targets:
        for cfg_name, over, scheme in combos:
            if True:
                for d in args.depths:
                    per = []
                    for s in range(args.seeds):
                        acfg = AnalogConfig(mismatch_seed=1000 + s, **over)
                        _, m = run_one(FabricSpec("tree", d), acfg, target,
                                       s, tcfg, scheme)
                        m.update(dict(target=target, cfg=cfg_name,
                                      init=scheme, depth=d, seed=s,
                                      topology="tree"))
                        per.append(m)
                        out["A"].append(m)
                    print(f"{target:16s} {cfg_name:6s} {scheme:9s} {d:5d} "
                          f"{per[0]['cells']:6d} "
                          f"{median([p['train_rmse'] for p in per]):10.4f} "
                          f"{min(p['train_rmse'] for p in per):10.4f} "
                          f"{median([p['test_rmse'] for p in per]):10.4f} "
                          f"[{time.time()-t0:5.0f}s]", flush=True)


# ---------------------------------------------------------------------------
# B: forward error accumulation, no training
# ---------------------------------------------------------------------------

def exp_b(args, out, t0):
    print("\n=== B: forward error vs depth, frozen weights, no training ===",
          flush=True)
    print("relative RMS divergence between an ideal chip and a mismatched "
          "chip running identical weights", flush=True)
    print(f"{'gain sigma':>10} {'depth':>5} {'cells':>6} {'rel err med':>12} "
          f"{'per-stage equiv':>16}", flush=True)
    x = torch.exp(torch.linspace(math.log(0.3), math.log(7.85), 256,
                                 dtype=REAL_DTYPE))
    for sigma in (0.01, 0.03, 0.10):
        for d in args.depths:
            per = []
            for s in range(args.seeds):
                ideal = AnalogEMLFabric(FabricSpec("tree", d), AnalogConfig(),
                                        seed=s, init_scheme="identity")
                bad = AnalogEMLFabric(
                    FabricSpec("tree", d),
                    AnalogConfig(mismatch_gain_std=sigma,
                                 mismatch_offset_std=sigma / 6.0,
                                 mismatch_seed=1000 + s),
                    seed=s, init_scheme="identity")
                with torch.no_grad():
                    for l in range(d):
                        bad.alpha[l].copy_(ideal.alpha[l])
                        bad.beta[l].copy_(ideal.beta[l])
                        bad.gamma[l].copy_(ideal.gamma[l])
                    bad.ro_w.copy_(ideal.ro_w)
                    bad.ro_b.copy_(ideal.ro_b)
                    a = ideal(x, noisy=False)
                    b = bad(x, noisy=False)
                    denom = float(a.pow(2).mean().sqrt())
                    rel = float((a - b).pow(2).mean().sqrt()) / max(denom, 1e-30)
                per.append(rel)
                out["B"].append(dict(sigma=sigma, depth=d, seed=s,
                                     rel_err=rel, cells=ideal.n_cells))
            med = median(per)
            # if error compounded independently per stage: rel ~ e1*sqrt(d)
            per_stage = med / math.sqrt(d) if d > 0 else float("nan")
            print(f"{sigma:10.3f} {d:5d} {2**d - 1:6d} {med:12.4e} "
                  f"{per_stage:16.4e} [{time.time()-t0:5.0f}s]", flush=True)


# ---------------------------------------------------------------------------
# C: topology comparison
# ---------------------------------------------------------------------------

def exp_c(args, tcfg, out, t0):
    print("\n=== C: topology, equal depth and equal cell budget ===",
          flush=True)
    print(f"{'target':16s} {'topo':5s} {'depth':>5} {'width':>5} {'cells':>6} "
          f"{'params':>7} {'train med':>10} {'train best':>10} "
          f"{'test med':>10}", flush=True)
    for target in args.targets:
        for d in args.topo_depths:
            tree_cells = 2 ** d - 1
            # width that matches the tree's cell count at this depth
            w_match = max(2, round(tree_cells / d))
            specs = [FabricSpec("tree", d)]
            for w in sorted({args.width, w_match}):
                specs.append(FabricSpec("dag", d, width=w))
                specs.append(FabricSpec("mesh", d, width=w, window=3))
            for spec in specs:
                per = []
                for s in range(args.seeds):
                    acfg = AnalogConfig(mismatch_seed=1000 + s, **PDK)
                    _, m = run_one(spec, acfg, target, s, tcfg, "identity")
                    m.update(dict(target=target, topology=spec.topology,
                                  depth=d, width=spec.width, seed=s))
                    per.append(m)
                    out["C"].append(m)
                print(f"{target:16s} {spec.topology:5s} {d:5d} "
                      f"{spec.width if spec.topology!='tree' else 0:5d} "
                      f"{per[0]['cells']:6d} {per[0]['params']:7d} "
                      f"{median([p['train_rmse'] for p in per]):10.4f} "
                      f"{min(p['train_rmse'] for p in per):10.4f} "
                      f"{median([p['test_rmse'] for p in per]):10.4f} "
                      f"[{time.time()-t0:5.0f}s]", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--seeds", type=int, default=4)
    ap.add_argument("--iters", type=int, default=2500)
    ap.add_argument("--width", type=int, default=8)
    ap.add_argument("--only", type=str, default="ABC")
    ap.add_argument("--outdir", type=str, default="results")
    args = ap.parse_args()

    args.depths = [1, 2, 3, 4, 6, 8, 10]
    args.topo_depths = [4, 6, 8]
    # thermistor_sh: smooth sensor curve, effectively saturated by depth 3.
    # osc_k3: sin(3 ln x), not exactly representable in a real-valued
    #   fabric, and the one target where extra depth demonstrably buys
    #   accuracy (0.158 -> 0.027 from depth 3 to depth 6 in the pilot).
    # osc_k5 and osc_k8 are excluded from the sweep because nothing learns
    #   them at any depth tried; that cliff is reported separately.
    args.targets = ["thermistor_sh", "osc_k3"]
    if args.pilot:
        args.seeds, args.iters = 2, 600
        args.depths = [3, 8]
        args.topo_depths = [6]
        args.targets = ["thermistor_sh", "osc_k8"]

    tcfg = TrainConfig(iters=args.iters)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    out = {"args": {k: v for k, v in vars(args).items()},
           "pdk": PDK, "A": [], "B": [], "C": []}
    t0 = time.time()

    if "B" in args.only:
        exp_b(args, out, t0)
    if "A" in args.only:
        exp_a(args, tcfg, out, t0)
    if "C" in args.only:
        exp_c(args, tcfg, out, t0)

    tag = "pilot" if args.pilot else "full"
    p = outdir / f"scaling_{tag}.json"
    with open(p, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nSaved {p}  ({time.time()-t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
