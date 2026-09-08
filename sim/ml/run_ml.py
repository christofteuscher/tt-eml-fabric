"""EML fabric as a machine-learning primitive: three experiments.

  reg    real-data regression vs matched-parameter MLP and polynomial ridge
  bias   where the exp/log inductive bias helps and where it hurts
  scale  depth/width at fixed cell budget, ideal vs pedestal

Usage:  python3 run_ml.py --exp reg [--pilot]

MLP BASELINE, 2026-08: the MLP column now uses run_mlp_val (grid winner
chosen on a held-out validation slice).  The first pass used run_mlp, which
selected on TRAIN NRMSE, picked the most overfitting grid member and
produced a spurious fabric win (diabetes test 1.087; corrected 0.712).  The
old numbers survive in results/ml_reg.json and results/ml_bias.json under
*_SUPERSEDED keys, and the corrected column is results/ml_mlp_val.json.
Re-running this script overwrites those files with the corrected protocol.
"""
import argparse
import json
import time
from pathlib import Path

import torch

from ml_common import (ITERS, SEEDS, SYNTH, hw_config, median, mix_task,
                       real_task, run_fabric, run_mlp_val, run_poly, synth_task)

torch.set_num_threads(1)
OUT = Path(__file__).resolve().parent / "results"
OUT.mkdir(exist_ok=True)


def fabric_stats(data, hw, seeds=SEEDS, **kw):
    rows = [run_fabric(*data, hw=hw, seed=s, **kw) for s in range(seeds)]
    return dict(hw=hw, train=median([r["train"] for r in rows]),
                test=median([r["test"] for r in rows]),
                test_best=min(r["test"] for r in rows),
                params=rows[0]["params"], cells=rows[0]["cells"],
                secs=sum(r["secs"] for r in rows), rows=rows)


def exp_reg(args):
    out = {}
    for task in ["diabetes", "wine_proline"]:
        data = real_task(task)
        n_tr, d = data[0].shape
        rec = {"n_train": n_tr, "n_test": data[2].shape[0], "n_feat": d,
               "fabric": [], "mlp": [], "poly": []}
        print(f"\n=== {task}: {n_tr} train / {rec['n_test']} test, "
              f"{d} features ===", flush=True)
        for hw in (["ideal", "pedestal"] if args.pilot
                   else ["ideal", "pedestal", "pdk+ped"]):
            r = fabric_stats(data, hw, seeds=args.seeds, iters=args.iters)
            rec["fabric"].append(r)
            print(f"fabric {hw:9s} cells={r['cells']:3d} P={r['params']:5d} "
                  f"train {r['train']:.4f} test {r['test']:.4f} "
                  f"(best {r['test_best']:.4f}) [{r['secs']:.0f}s]", flush=True)
        P = rec["fabric"][0]["params"]
        m = run_mlp_val(*data, P=P, seeds=args.seeds, iters=args.iters)
        rec["mlp"].append(m)
        print(f"mlp    {str(m['hidden']):9s} {m['act']} lr={m['lr']} "
              f"P={m['params']:5d} train {m['train']:.4f} "
              f"test {m['test']:.4f} (best {m['test_best']:.4f})", flush=True)
        for p in run_poly(*data):
            rec["poly"].append(p)
            print(f"{p['method']:9s} P={p['params']:5d} "
                  f"train {p['train']:.4f} test {p['test']:.4f}", flush=True)
        out[task] = rec
    return out


def exp_bias(args):
    out = {"suite": {}, "crossover": {}}
    for name in SYNTH:
        data = synth_task(name)
        rec = {"expr": SYNTH[name][0], "fabric": [], "mlp": [], "poly": []}
        print(f"\n=== {name}: y = {SYNTH[name][0]} ===", flush=True)
        for hw in ["ideal", "pedestal"]:
            r = fabric_stats(data, hw, seeds=args.seeds, iters=args.iters)
            rec["fabric"].append(r)
            print(f"fabric {hw:9s} P={r['params']:5d} train {r['train']:.4f} "
                  f"test {r['test']:.4f} (best {r['test_best']:.4f}) "
                  f"[{r['secs']:.0f}s]", flush=True)
        P = rec["fabric"][0]["params"]
        m = run_mlp_val(*data, P=P, seeds=args.seeds, iters=args.iters)
        rec["mlp"].append(m)
        print(f"mlp    {str(m['hidden']):9s} {m['act']} lr={m['lr']} "
              f"P={m['params']:5d} train {m['train']:.4f} "
              f"test {m['test']:.4f}", flush=True)
        for p in run_poly(*data):
            rec["poly"].append(p)
            print(f"{p['method']:9s} P={p['params']:5d} "
                  f"train {p['train']:.4f} test {p['test']:.4f}", flush=True)
        out["suite"][name] = rec

    print("\n=== crossover: y_t = (1-t) z[x1x2x3] + t z[sin4x1+sin4x2+sin4x3] "
          "===", flush=True)
    for t in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        data = mix_task(t)
        r = fabric_stats(data, "ideal", seeds=args.seeds, iters=args.iters)
        rp = fabric_stats(data, "pedestal", seeds=args.seeds, iters=args.iters)
        m = run_mlp_val(*data, P=r["params"], seeds=args.seeds,
                        iters=args.iters)
        pol = run_poly(*data)
        out["crossover"][f"{t:.1f}"] = {"fabric_ideal": r,
                                        "fabric_pedestal": rp, "mlp": m,
                                        "poly": pol}
        print(f"t={t:.1f} fabric {r['test']:.4f} / ped {rp['test']:.4f} "
              f"| mlp {m['test']:.4f} | poly3 {pol[2]['test']:.4f} "
              f"| ratio fab/mlp {r['test']/m['test']:.2f}", flush=True)
    return out


def exp_scale(args):
    out = {}
    budgets = [(2, 16), (4, 8), (8, 4), (2, 8), (4, 4), (8, 2)]
    tasks = {"diabetes": real_task("diabetes"),
             "powlaw": synth_task("powlaw"),
             "osc_sum": synth_task("osc_sum")}
    for tname, data in tasks.items():
        print(f"\n=== depth/width at fixed cell budget: {tname} ===",
              flush=True)
        print(f"{'d':>2} {'w':>3} {'cells':>5} {'params':>7} "
              f"{'ideal_te':>9} {'ped_te':>9} {'ideal_best':>10}", flush=True)
        rec = []
        for d, w in budgets:
            a = fabric_stats(data, "ideal", seeds=args.seeds, depth=d,
                             width=w, iters=args.iters)
            b = fabric_stats(data, "pedestal", seeds=args.seeds, depth=d,
                             width=w, iters=args.iters)
            rec.append({"depth": d, "width": w, "cells": a["cells"],
                        "params": a["params"], "ideal": a, "pedestal": b})
            print(f"{d:2d} {w:3d} {a['cells']:5d} {a['params']:7d} "
                  f"{a['test']:9.4f} {b['test']:9.4f} "
                  f"{a['test_best']:10.4f} [{a['secs']+b['secs']:.0f}s]",
                  flush=True)
        out[tname] = rec
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", required=True,
                    choices=["reg", "bias", "scale"])
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--seeds", type=int, default=SEEDS)
    ap.add_argument("--iters", type=int, default=ITERS)
    args = ap.parse_args()
    if args.pilot:
        args.seeds, args.iters = 1, 150
    t0 = time.time()
    res = {"reg": exp_reg, "bias": exp_bias, "scale": exp_scale}[args.exp](args)
    path = OUT / f"ml_{args.exp}{'_pilot' if args.pilot else ''}.json"
    with open(path, "w") as f:
        json.dump({"iters": args.iters, "seeds": args.seeds, "res": res},
                  f, indent=2, default=str)
    print(f"\nSaved {path} ({time.time()-t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
