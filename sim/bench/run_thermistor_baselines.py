"""
Conventional baselines on the SAME thermistor calibration task the EML
fabric is evaluated on, so the paper has a calibrated reference.

Task (copied bit-exactly from eml_fabric_sim.make_data, NOT imported, so the
other agent's edits to that file cannot silently move the reference):
  x = R/R25, 256 log-uniform samples in [0.30, 7.85]  (T in [-20, 60] C),
  seed 1234; targets thermistor_beta and thermistor_sh; RMSE in Kelvin.
Added here: a fresh in-range TEST set (4096 points, seed 99) because a
256-entry LUT can interpolate 256 training points exactly, and the training
RMSE alone would reward that.

EML reference numbers, from RESULTS.md / RESULTS_SCALING.md (train RMSE, K):
  ideal fabric, unity-gain init, depth 3/4/6/8 : 0.014 / 0.010 / 0.014 / 0.009
  PDK chip (mismatch+noise+sat30+8bit), depth 3/4/6/8 : 0.162/0.134/0.138/0.225
  parameters: 44 / 92 / 380 / 1532
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import baselines as B  # noqa: E402

REAL = torch.float64
TRAIN_RANGE = (0.30, 7.85)
FULL_RANGE = (0.145, 24.8)


def thermistor_beta(x):
    Bc, T25 = 3435.0, 298.15
    return 1.0 / (1.0 / T25 + np.log(x) / Bc)          # Kelvin


def thermistor_sh(x):
    A, Bc, C = 1.129241e-3, 2.341077e-4, 8.775468e-8
    lr = np.log(x * 10000.0)
    return 1.0 / (A + Bc * lr + C * lr ** 3)           # Kelvin


TARGETS = {"thermistor_beta": thermistor_beta, "thermistor_sh": thermistor_sh}


def make_task(name, n_train=256, n_extrap=512, n_test=4096, seed=1234):
    """Training points identical to eml_fabric_sim.make_data(seed=1234)."""
    fn = TARGETS[name]
    tlo, thi = TRAIN_RANGE
    elo, ehi = FULL_RANGE
    g = torch.Generator().manual_seed(seed)
    xt = torch.exp(torch.empty(n_train, dtype=REAL).uniform_(
        math.log(tlo), math.log(thi), generator=g)).numpy()
    xe_all = torch.exp(torch.empty(n_extrap * 4, dtype=REAL).uniform_(
        math.log(elo), math.log(ehi), generator=g)).numpy()
    xe = xe_all[(xe_all < tlo) | (xe_all > thi)][:n_extrap]
    rng = np.random.default_rng(99)
    xs = np.exp(rng.uniform(math.log(tlo), math.log(thi), n_test))
    return B.Task(name=name, Xtr=xt[:, None], ytr=fn(xt),
                  Xte=xs[:, None], yte=fn(xs),
                  Xex=xe[:, None], yex=fn(xe), unit="K")


def run(task):
    res = []
    for deg in range(1, 10):
        res.append(B.fit_poly(task, deg))                       # plain poly
        res.append(B.fit_poly(task, deg, xform="log"))          # poly in ln x
    for deg in range(1, 6):
        # the classical sensor-engineering baseline: Steinhart-Hart is
        # exactly "1/T is a polynomial in ln R"
        res.append(B.fit_poly(task, deg, xform="log", yform="recip"))
    for k in (1, 2, 4, 8, 16, 32):
        res.append(B.fit_spline(task, k))
        res.append(B.fit_spline(task, k, xform="log"))
    for n in (4, 8, 16, 32, 64, 128, 256):
        res.append(B.fit_lut(task, n))
        res.append(B.fit_lut(task, n, xform="log"))
    for (w, h) in ((4, 1), (8, 1), (16, 1), (32, 1), (8, 2), (16, 2), (32, 2)):
        runs = [B.fit_mlp(task, w, h, seed=s) for s in range(3)]
        best = min(runs, key=lambda r: r.rmse_test)
        med = sorted(runs, key=lambda r: r.rmse_test)[1]
        best.extra["role"] = "best-of-3-seeds"
        med.method += " (median seed)"
        med.extra["role"] = "median-of-3-seeds"
        res += [best, med]
    return res


def main():
    out = {}
    for name in TARGETS:
        task = make_task(name)
        print("=" * 96)
        print(f"{name}: {len(task.ytr)} train / {len(task.yte)} test / "
              f"{len(task.yex)} extrapolation points; "
              f"y span {task.ytr.min():.2f}-{task.ytr.max():.2f} K")
        print("=" * 96)
        res = run(task)
        print(B.summarize(res, unit="K"))
        print("\nPareto front (cheapest method reaching each test RMSE):")
        for p, r, m in B.pareto(res):
            print(f"  {p:6d} params  {r:10.4g} K   {m}")
        print("\nEML fabric reference (train RMSE, RESULTS_SCALING.md):")
        for d, ideal, pdk in ((3, 0.014, 0.162), (4, 0.010, 0.134),
                              (6, 0.014, 0.138), (8, 0.009, 0.225)):
            print(f"  depth {d}: {B.eml_params(d):6d} params  "
                  f"ideal {ideal:.3f} K   PDK chip {pdk:.3f} K")
        # what does each baseline need to match the fabric?
        for tag, target in (("ideal EML (0.010 K)", 0.010),
                            ("PDK-chip EML (0.134 K)", 0.134)):
            print(f"\n  cheapest baseline reaching {tag} on TEST:")
            hits = [r for r in res if r.rmse_test <= target]
            if hits:
                c = min(hits, key=lambda r: r.params)
                print(f"    {c.method}  {c.params} params  "
                      f"{c.rmse_test:.4g} K")
            else:
                print("    none of the baselines reach it")
        out[name] = B.to_dicts(res)

    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "results_thermistor_baselines.json")
    with open(p, "w") as fh:
        json.dump(out, fh, indent=1)
    print(f"\nwrote {p}")


if __name__ == "__main__":
    main()
