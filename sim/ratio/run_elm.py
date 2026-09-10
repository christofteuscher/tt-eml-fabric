"""RANDOM-FEATURE (ELM) regime for the analog EML fabric.

SIMULATION ONLY.  Nothing here is a measurement of a physical device.

WHY THIS RUN EXISTS
-------------------
Every other benchmark in this study trains *all* the fabric's weights by
gradient descent through the behavioural model and reads the answer out of
layer 0.  The fabric is used as a fitted approximator, so every interior cell
is required to hold a particular value to a stated precision -- and holding
interior values to a stated precision is exactly what the servo scaffolding
buys, i.e. the whole of the composability overhead.

The random-feature regime removes that requirement.  The interior weights are
drawn once and FROZEN; the fabric is a fixed nonlinear map; every cell output
is a feature; and only a linear readout is fitted, in closed form by ridge
regression.  No interior node has a target value, so nothing upstream has to
be held to a precision -- it only has to be REPEATABLE.  Device mismatch stops
being error and becomes diversity.

Strictly this is an extreme learning machine (ELM) / physical random-feature
map, not a reservoir: the fabric is feedforward and has no fading memory.
The recurrence in the closed-loop columns belongs to the ODE, not the device.

The comparison this answers: does the fabric, which loses on every trained
axis, win in the one regime where its binding constraint is relaxed?

PROTOCOL
--------
Deliberately identical to run_ratio.py wherever a choice exists, so the rows
produced here can be pooled with results/ratio_all.json and scored by the same
criteria:
  * the same 16 systems, the same ICs, the same training box and input offset,
  * the same n_train = 768 uniform samples and the same validation draw,
  * the same closed-loop substitution, blow-up guard and NRMSE definitions,
  * best-of-seeds selected on TRAINING error, as run_ratio.py does,
  * noisy=False at evaluation, as run_ratio.py's fabric_fn does, so read
    noise is excluded from BOTH studies alike.
Only the fitting rule differs, which is the point of the experiment.

MODELS
------
  elm_{hw}_c{N}   fabric of N cells, interior frozen at its random draw,
                  ridge readout over ALL N cell outputs.  Trainable
                  parameters: N + 1 per output.
  elmtanh_f{N}    the standard ELM baseline: random Gaussian projection into
                  N features, tanh, ridge readout.  Same feature count, same
                  ridge selection, same everything downstream.

HW CONFIGS
----------
  ideal     AnalogConfig()                    -- real-domain math
  pedestal  ln_pedestal = 2.547               -- the realised cell ln(v+s)
  silicon   pedestal + PDK mismatch, output rail and 8-bit weights
            (run_pdk_chip.py's PDK config, minus read noise for the
            comparability reason above)
`atten_v` is LEFT OFF throughout: it is derived from the pedestal and
enabling both double-counts the same physics.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from scipy.integrate import solve_ivp

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eml_fabric_sim import AnalogConfig                                # noqa
from eml_fabric_topo import AnalogEMLFabric, FabricSpec                # noqa
from ratio_systems import SYSTEMS, nl_args                             # noqa
from run_ratio import (reference, training_box, make_data, nrmse,      # noqa
                       closed_loop, summarise, NTRAIN, PEDESTAL)

# PDK-realistic cell, from run_pdk_chip.py:29.  noise_std is deliberately
# omitted: run_ratio.py evaluates the trained fabric with noisy=False, and a
# stochastic right-hand side would also make the closed-loop integration
# non-deterministic.  Read noise is therefore absent from both studies.
HW = {
    "ideal": dict(),
    "pedestal": dict(ln_pedestal=PEDESTAL),
    "silicon": dict(ln_pedestal=PEDESTAL, mismatch_gain_std=0.02,
                    mismatch_offset_std=0.005, sat=30.0, weight_bits=8),
}

# (topology, depth, width, window) -> cells.  The first two match
# run_ratio.py exactly; the rest ask what width buys, since a random-feature
# machine is supposed to improve with the size of its feature bank and cells
# are the currency the energy argument is denominated in.
CFGS = [("mesh", 2, 4, 3),      # 8
        ("mesh", 3, 6, 3),      # 18
        ("mesh", 3, 16, 3),     # 48
        ("mesh", 3, 64, 3)]     # 192

# Standardised features are railed at +-CLIP sigma before the readout sees
# them.  A real output stage has a finite input range, and without some rail
# a single out-of-domain excursion in closed loop dominates the fit.  The
# fraction of entries actually clipped is recorded per row; where it is ~0
# the rail is immaterial.
CLIP = 8.0
LAMS = np.logspace(-12, 6, 73)


# --------------------------------------------------------------- ridge
def ridge_gcv(Phi, Y, lams=LAMS):
    """Ridge with the penalty chosen by generalised cross-validation.

    Phi is (B, p) standardised and Y is (B, k) centred, so no intercept is
    penalised.  One SVD serves the whole lambda grid.  GCV is used rather
    than a held-out split so that every one of the 768 training points is
    used for fitting, which is the setting most favourable to the ELM.
    """
    U, s, Vt = np.linalg.svd(Phi, full_matrices=False)
    UtY = U.T @ Y
    B = Phi.shape[0]
    s2 = s ** 2
    best = (np.inf, None, None)
    for lam in lams:
        d = s / (s2 + lam)
        fit = U @ ((s * d)[:, None] * UtY)
        dof = float(np.sum(s2 / (s2 + lam)))
        denom = 1.0 - dof / B
        if denom <= 1e-6:
            continue
        gcv = float(np.mean((Y - fit) ** 2)) / denom ** 2
        if np.isfinite(gcv) and gcv < best[0]:
            best = (gcv, lam, Vt.T @ (d[:, None] * UtY))
    return best[2], best[1]


class Readout:
    """Standardise -> rail -> ridge.  Carries its own train-set statistics."""

    def __init__(self, Phi, Y):
        Phi = np.nan_to_num(np.asarray(Phi, float), nan=0.0,
                            posinf=1e6, neginf=-1e6)
        self.mu = Phi.mean(0)
        self.sd = np.maximum(Phi.std(0), 1e-9)
        Z, self.clip_frac = self._z(Phi)
        self.ybar = Y.mean(0)
        self.W, self.lam = ridge_gcv(Z, Y - self.ybar)
        self.p = Phi.shape[1]

    def _z(self, Phi):
        Z = (Phi - self.mu) / self.sd
        frac = float(np.mean(np.abs(Z) > CLIP))
        return np.clip(Z, -CLIP, CLIP), frac

    def __call__(self, Phi):
        Phi = np.nan_to_num(np.asarray(Phi, float), nan=0.0,
                            posinf=1e6, neginf=-1e6)
        Z, _ = self._z(Phi)
        return Z @ self.W + self.ybar

    def ok(self):
        return self.W is not None and np.all(np.isfinite(self.W))


# --------------------------------------------------------------- features
def fabric_features(s, hw, cfg, seed, layer0_only=False):
    """A frozen random fabric and the function that reads its cells.

    `layer0_only` is the CONTROL that separates the two things a frozen
    fabric changes at once.  The trained fabric of run_ratio.py reads only
    its layer-0 cells, so an ELM reading all cells has both (i) no interior
    training and (ii) a wider readout.  Restricting the readout to layer 0
    holds (ii) fixed and isolates (i).  Without this control the frozen-vs-
    trained comparison confounds them and cannot be quoted.
    """
    topo, depth, width, window = cfg
    spec = FabricSpec(topology=topo, depth=depth, width=width, window=window,
                      n_vars=s["nvars"])
    acfg = AnalogConfig(**HW[hw])
    m = AnalogEMLFabric(spec, acfg, seed=seed, var_mode="dense")
    for p in m.parameters():
        p.requires_grad_(False)
    # cell_features appends deepest layer first, so layer 0 is the tail
    n0 = spec.layer_sizes()[0]

    def phi(P, off):
        t = torch.tensor(np.asarray(P, float), dtype=torch.float64) + off
        F = m.cell_features(t, noisy=False).numpy().T         # (B, n_cells)
        return F[:, -n0:] if layer0_only else F
    return phi, (n0 if layer0_only else spec.n_cells())


def tanh_features(s, n_feat, seed):
    """Standard ELM baseline: random Gaussian projection, tanh."""
    rng = np.random.default_rng(1000 + seed)
    nin = s["nvars"]
    W = rng.normal(0.0, 1.0, size=(nin, n_feat)) / np.sqrt(nin)
    b = rng.uniform(-1.0, 1.0, size=n_feat)

    def phi(P, off):
        return np.tanh(np.asarray(P, float) @ W + b)
    return phi, n_feat


def fit_elm(s, phi, xt, yt, in_off, off_t):
    """Ridge readout on frozen features; returns the predictor and stats."""
    Phi = phi(xt, off_t)
    ro = Readout(Phi, yt)
    if not ro.ok():
        return None, None

    def F(P):
        return ro(phi(P, off_t))
    return F, dict(lam=float(ro.lam), clip_frac=ro.clip_frac,
                   n_feat=int(ro.p))


# --------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", default="")
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--out", default="results/elm.json")
    ap.add_argument("--budget", type=float, default=6.0)
    a = ap.parse_args()
    names = a.systems.split(",") if a.systems else list(SYSTEMS)

    out = {"note": "SIMULATION ONLY. Random-feature (ELM) readout of a "
                   "FROZEN analog EML fabric: interior weights are never "
                   "trained, only the linear readout is fitted. Protocol "
                   "matches run_ratio.py so rows pool with ratio_all.json.",
           "hw": {k: (v or "AnalogConfig() ideal") for k, v in HW.items()},
           "cfgs": [list(c) for c in CFGS], "seeds": a.seeds,
           "ntrain": NTRAIN, "clip_sigma": CLIP, "rows": []}

    t0 = time.time()
    print(f"{'system':20s} {'model':16s} {'testN':>9s} {'trajN':>9s} "
          f"{'tdiv/T':>7s} {'oob':>5s} {'lam':>9s} {'clip':>6s} {'par':>5s}",
          flush=True)

    for name in names:
        s = SYSTEMS[name]
        te, refs = reference(s)
        lo, hi = training_box(name, refs)
        in_off = np.where(lo < 0.5, 0.5 - lo, 0.0)
        off_t = torch.tensor(in_off, dtype=torch.float64)
        xt, yt, xv, yv = make_data(s, lo, hi)
        yt = yt.reshape(len(xt), -1)
        yv = yv.reshape(len(xv), -1)
        Ptr = np.concatenate([nl_args(name, y) for y in refs], 0)
        ytr = s["nl"](Ptr).reshape(len(Ptr), -1)

        jobs = []
        for hw in HW:
            for cfg in CFGS:
                jobs.append((f"elm_{hw}", cfg, hw, False))
        # control: frozen interior but the trained fabric's layer-0 readout
        for hw in ("ideal", "pedestal"):
            for cfg in CFGS[:2]:
                jobs.append((f"elm0_{hw}", cfg, hw, True))
        for nf in (18, 192):
            jobs.append((f"elmtanh_f{nf}", nf, None, False))

        for label, spec_or_nf, hw, l0 in jobs:
            # best-of-seeds on TRAINING error, as run_ratio.py does
            best = (np.inf, None, None, None)
            for sd in range(a.seeds):
                if hw is not None:
                    phi, nfeat = fabric_features(s, hw, spec_or_nf, sd,
                                                 layer0_only=l0)
                else:
                    phi, nfeat = tanh_features(s, spec_or_nf, sd)
                F, info = fit_elm(s, phi, xt, yt, in_off, off_t)
                if F is None:
                    continue
                tr = float(np.mean([nrmse(F(xt)[:, k], yt[:, k])
                                    for k in range(s["n_out"])]))
                if np.isfinite(tr) and tr < best[0]:
                    best = (tr, F, info, nfeat)
            tr, F, info, nfeat = best
            if hw is None:
                mname = label
            elif l0:
                ncell = sum(FabricSpec(topology=spec_or_nf[0],
                                       depth=spec_or_nf[1],
                                       width=spec_or_nf[2]).layer_sizes())
                mname = f"{label}_c{ncell}"
            else:
                mname = f"{label}_c{nfeat}"
            if F is None:
                print(f"{name:20s} {mname:16s}  ALL SEEDS FAILED", flush=True)
                continue

            te_n = float(np.mean([nrmse(F(xv)[:, k], yv[:, k])
                                  for k in range(s["n_out"])]))
            ot_n = float(np.mean([nrmse(F(Ptr)[:, k], ytr[:, k])
                                  for k in range(s["n_out"])]))
            cl = summarise(closed_loop(s, name, F, te, refs, lo, hi))
            npar = (nfeat + 1) * s["n_out"]
            info.update(params=npar, cells=(nfeat if hw is not None else 0),
                        train_nrmse=tr, frozen_interior=hw is not None)
            out["rows"].append(dict(system=name, cls=s["cls"], model=mname,
                                    test_nrmse=te_n, on_traj_nrmse=ot_n,
                                    T=s["T"], info=info, **cl))
            print(f"{name:20s} {mname:16s} {te_n:9.4f} "
                  f"{cl['traj_nrmse']:9.4f} {cl['t_div'] / s['T']:7.3f} "
                  f"{cl['oob']:5.2f} {info['lam']:9.2e} "
                  f"{info['clip_frac']:6.3f} {npar:5d} "
                  f"[{time.time() - t0:5.0f}s]", flush=True)
            Path(a.out).parent.mkdir(parents=True, exist_ok=True)
            json.dump(out, open(a.out, "w"), indent=2)

    print(f"\nSaved {a.out} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
