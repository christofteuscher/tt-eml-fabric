"""Shared machinery for the EML-fabric machine-learning study.

Conventions used everywhere in ml/:

  * Every target is centred and scaled by its TRAINING mean/std, so a
    reported RMSE is an NRMSE with respect to the best constant predictor:
    1.0 = "explains nothing", and on the test split it equals sqrt(1 - R^2).
  * Every input is min-max mapped, using TRAINING statistics only, into the
    positive box [1, 2].  The fabric is a log-domain part and wants positive
    rails; the same mapping is given to every baseline, so no method is
    advantaged by the preprocessing.
  * Resources are reported as trainable parameter count for all methods and
    additionally as cell count for the fabric.
  * MLP baselines are selected on a HELD-OUT VALIDATION slice (run_mlp_val).
    The first pass used run_mlp, which selected on TRAIN NRMSE: that picks
    the most overfitting grid member and produced a spurious fabric win
    (diabetes test 1.087 vs the corrected 0.712).  run_mlp is kept only for
    reproducing the superseded runs; it warns, and stamps its records
    selection="train NRMSE (SUPERSEDED)".  Corrected numbers live in
    results/ml_mlp_val.json.

Hardware configs (see the NON-IDEALITY note in eml_fabric_sim.AnalogConfig):
  ideal     - AnalogConfig(), real-domain math.
  pedestal  - ln_pedestal = 2.547 only.  The v-port attenuation is left OFF
              because lambda_v = 1.094/(1.741+2.547) is DERIVED from the same
              pedestal; enabling both double-counts one physical effect.
              The 8.4-decade span is also left off: measured excursion on
              these workloads is 0.00 decades, so it does not bind.
  pdk+ped   - pedestal on top of the corrected PDK chip (gain sigma 0.03,
              offset sigma 0.005, noise 3e-3, sat 30, 8-bit weights).
"""
import math
import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import torch

from eml_fabric_sim import (AnalogConfig, TrainConfig, PEDESTAL_SEGMENTED,
                            evaluate, train)
from eml_fabric_topo import AnalogEMLFabric, FabricSpec

DT = torch.float64
ITERS = 2000
SEEDS = 3
BOX = (1.0, 2.0)


# --------------------------------------------------------------- hardware
def hw_config(name, seed=0):
    if name == "ideal":
        return AnalogConfig()
    if name == "pedestal":
        return AnalogConfig(ln_pedestal=PEDESTAL_SEGMENTED)
    if name == "pdk+ped":
        return AnalogConfig(ln_pedestal=PEDESTAL_SEGMENTED,
                            mismatch_gain_std=0.03, mismatch_offset_std=0.005,
                            noise_std=3e-3, sat=30.0, weight_bits=8,
                            mismatch_seed=1000 + seed)
    raise ValueError(name)


def median(v):
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


# ------------------------------------------------------------------- data
def _prep(Xtr, ytr, Xte, yte):
    """Positive-box inputs, unit-variance zero-mean target, train stats."""
    mn, mx = Xtr.min(0).values, Xtr.max(0).values
    rng = (mx - mn).clamp_min(1e-12)
    lo, hi = BOX
    f = lambda X: lo + (hi - lo) * (X - mn) / rng
    mu, sd = ytr.mean(), ytr.std()
    return f(Xtr), (ytr - mu) / sd, f(Xte), (yte - mu) / sd


def _split(X, y, frac=0.75, seed=0):
    g = torch.Generator().manual_seed(seed)
    p = torch.randperm(X.shape[0], generator=g)
    k = int(frac * X.shape[0])
    return _prep(X[p[:k]], y[p[:k]], X[p[k:]], y[p[k:]])


def real_task(name):
    """sklearn's bundled datasets only -- nothing here touches the network."""
    from sklearn.datasets import load_diabetes, load_wine
    if name == "diabetes":
        d = load_diabetes()
        X, y = d.data, d.target
    elif name == "wine_proline":
        # Predict proline concentration (feature 12) from the other 12
        # chemical measurements.  load_diabetes is the only bundled *named*
        # regression set; this is a second real-data regression built from
        # bundled continuous measurements rather than an invented function.
        d = load_wine()
        X = d.data[:, :12]
        y = d.data[:, 12]
    else:
        raise ValueError(name)
    return _split(torch.tensor(X, dtype=DT), torch.tensor(y, dtype=DT))


# ------------------------------------- synthetic inductive-bias targets ---
# All on x in [1,3]^3 (or as noted), 512 train / 512 test, uniform in the box.
SYNTH = {
    # ---- natural for a log-domain fabric: linearise in log space --------
    "prod3":    ("x1*x2*x3", lambda X: X[:, 0] * X[:, 1] * X[:, 2]),
    "powlaw":   ("x1^1.7 * x2^-0.9 * x3^0.4",
                 lambda X: X[:, 0] ** 1.7 * X[:, 1] ** -0.9 * X[:, 2] ** 0.4),
    "expratio": ("exp(x1/x2)/x3",
                 lambda X: torch.exp(X[:, 0] / X[:, 1]) / X[:, 2]),
    # ---- hostile: oscillatory / sign-changing sums ----------------------
    "osc_sum":  ("sin(4x1)+sin(4x2)+sin(4x3)",
                 lambda X: torch.sin(4 * X[:, 0]) + torch.sin(4 * X[:, 1])
                 + torch.sin(4 * X[:, 2])),
    "osc_prod": ("sin(2*pi*x1*x2)",
                 lambda X: torch.sin(2 * math.pi * X[:, 0] * X[:, 1])),
    "diffexp":  ("exp(x1)-exp(x2)",
                 lambda X: torch.exp(X[:, 0]) - torch.exp(X[:, 1])),
}


def synth_task(name, n=512, seed=1234, lo=1.0, hi=3.0, nv=3):
    fn = SYNTH[name][1]
    g = torch.Generator().manual_seed(seed)
    draw = lambda m: torch.empty(m, nv, dtype=DT).uniform_(lo, hi, generator=g)
    Xtr, Xte = draw(n), draw(n)
    return _prep(Xtr, fn(Xtr), Xte, fn(Xte))


def mix_task(t, n=512, seed=1234, lo=1.0, hi=3.0):
    """Crossover family: unit-variance mix of the friendliest and the most
    hostile target.  y_t ~ (1-t)*z[prod3] + t*z[osc_sum], z = standardised."""
    g = torch.Generator().manual_seed(seed)
    draw = lambda m: torch.empty(m, 3, dtype=DT).uniform_(lo, hi, generator=g)
    Xtr, Xte = draw(n), draw(n)
    a, b = SYNTH["prod3"][1], SYNTH["osc_sum"][1]

    def mk(X, stats=None):
        u, v = a(X), b(X)
        if stats is None:
            stats = (u.mean(), u.std(), v.mean(), v.std())
        um, us, vm, vs = stats
        return (1 - t) * (u - um) / us + t * (v - vm) / vs, stats

    ytr, st = mk(Xtr)
    yte, _ = mk(Xte, st)
    return _prep(Xtr, ytr, Xte, yte)


# ----------------------------------------------------------------- fabric
def run_fabric(Xtr, ytr, Xte, yte, hw, seed, depth=4, width=8, window=3,
               topology="mesh", iters=ITERS):
    spec = FabricSpec(topology=topology, depth=depth, width=width,
                      window=window, n_vars=Xtr.shape[1])
    acfg = hw_config(hw, seed)
    torch.manual_seed(seed)
    m = AnalogEMLFabric(spec, acfg, seed=seed, var_mode="dense")
    m.init_readout_lstsq(Xtr, ytr)
    t0 = time.time()
    train(m, Xtr, ytr, TrainConfig(iters=iters))
    tr, _ = evaluate(m, Xtr, ytr)
    te, _ = evaluate(m, Xte, yte)
    return dict(method="fabric", hw=hw, seed=seed, topology=topology,
                depth=depth, width=width, train=tr, test=te,
                params=m.n_params(), cells=m.n_cells,
                secs=round(time.time() - t0, 1))


# ------------------------------------------------------------------- MLP
class MLP(torch.nn.Module):
    def __init__(self, d, hidden, act):
        super().__init__()
        A = {"tanh": torch.nn.Tanh, "relu": torch.nn.ReLU}[act]
        layers, prev = [], d
        for h in hidden:
            layers += [torch.nn.Linear(prev, h, dtype=DT), A()]
            prev = h
        layers += [torch.nn.Linear(prev, 1, dtype=DT)]
        self.net = torch.nn.Sequential(*layers)

    def forward(self, x, noisy=False):
        return self.net(x).squeeze(-1)


def hidden_for_budget(d, P, n_layers):
    """Widths giving a parameter count as close as possible to P."""
    if n_layers == 1:
        h = max(1, round((P - 1) / (d + 2)))
        return [h]
    # equal widths h: P = h(d+1) + (L-1)h(h+1) + (h+1)
    L = n_layers
    A, B, C = (L - 1), (d + 2 + (L - 1)), (1 - P)
    h = max(1, round((-B + math.sqrt(B * B - 4 * A * C)) / (2 * A)))
    return [h] * L


def run_mlp(Xtr, ytr, Xte, yte, P, seeds=SEEDS, iters=ITERS,
            lrs=(3e-3, 1e-2, 3e-2), acts=("tanh", "relu"), layer_counts=(1, 2)):
    """SUPERSEDED -- do not use for reported baselines; call run_mlp_val().

    Matched-parameter MLP whose grid winner is selected on TRAIN NRMSE
    (median over seeds).  That rule picks the most overfitting member of
    the grid and so understates the baseline: on diabetes it chose train
    0.247 / test 1.087, where held-out-validation selection gives 0.712.
    The fabric "win" that followed was an artefact of the selection rule.

    Kept only so the superseded runs stay reproducible.  Every record it
    returns is stamped selection="train NRMSE (SUPERSEDED)", and calling it
    warns.
    """
    warnings.warn(
        "run_mlp() selects the grid winner on TRAIN NRMSE: the superseded, "
        "overfitting-biased protocol (diabetes test 1.087 vs 0.712 with "
        "held-out validation). Use run_mlp_val().",
        RuntimeWarning, stacklevel=2)
    d = Xtr.shape[1]
    best = None
    for nl in layer_counts:
        hid = hidden_for_budget(d, P, nl)
        for act in acts:
            for lr in lrs:
                tr_s, te_s, np_ = [], [], 0
                for s in range(seeds):
                    torch.manual_seed(s)
                    m = MLP(d, hid, act)
                    np_ = sum(p.numel() for p in m.parameters())
                    train(m, Xtr, ytr, TrainConfig(iters=iters, lr=lr,
                                                   lr_final=lr / 10))
                    a, _ = evaluate(m, Xtr, ytr)
                    b, _ = evaluate(m, Xte, yte)
                    tr_s.append(a)
                    te_s.append(b)
                r = dict(method="mlp", hidden=hid, act=act, lr=lr,
                         train=median(tr_s), test=median(te_s),
                         test_best=min(te_s), params=np_, cells=None,
                         selection="train NRMSE (SUPERSEDED)",
                         superseded_by="ml_mlp_val.json / run_mlp_val()")
                if best is None or r["train"] < best["train"]:
                    best = r
    return best


def run_mlp_val(Xtr, ytr, Xte, yte, P, seeds=SEEDS, iters=ITERS,
                lrs=(3e-3, 1e-2, 3e-2), acts=("tanh", "relu"),
                layer_counts=(1, 2), val_frac=0.25):
    """Matched-parameter MLP with HONEST model selection.

    Selecting the grid winner on training NRMSE picks the most overfitting
    member of the grid, which silently handicaps the baseline (on diabetes
    it chose a config with train 0.25 / test 1.09).  Here the winner is
    chosen on a held-out validation slice of the TRAINING split, then
    retrained on the full training split over `seeds` seeds -- the same
    protocol RidgeCV gives the polynomial baseline.

    Tuning effort: {1,2} hidden layers x {tanh,relu} x 3 learning rates
    = 12 configurations, one fit each for selection.  The fabric gets no
    grid at all: fixed mesh d4/w8, lr 0.02, identity init, one config.
    """
    d = Xtr.shape[1]
    n = Xtr.shape[0]
    g = torch.Generator().manual_seed(7)
    p = torch.randperm(n, generator=g)
    k = int((1 - val_frac) * n)
    Xa, ya, Xb, yb = Xtr[p[:k]], ytr[p[:k]], Xtr[p[k:]], ytr[p[k:]]

    best = None
    for nl in layer_counts:
        hid = hidden_for_budget(d, P, nl)
        for act in acts:
            for lr in lrs:
                torch.manual_seed(0)
                m = MLP(d, hid, act)
                train(m, Xa, ya, TrainConfig(iters=iters, lr=lr,
                                             lr_final=lr / 10))
                v, _ = evaluate(m, Xb, yb)
                if best is None or v < best[0]:
                    best = (v, hid, act, lr)
    _, hid, act, lr = best
    tr_s, te_s, np_ = [], [], 0
    for s in range(seeds):
        torch.manual_seed(s)
        m = MLP(d, hid, act)
        np_ = sum(p_.numel() for p_ in m.parameters())
        train(m, Xtr, ytr, TrainConfig(iters=iters, lr=lr, lr_final=lr / 10))
        a, _ = evaluate(m, Xtr, ytr)
        b, _ = evaluate(m, Xte, yte)
        tr_s.append(a)
        te_s.append(b)
    return dict(method="mlp", hidden=hid, act=act, lr=lr, val=best[0],
                train=median(tr_s), test=median(te_s), test_best=min(te_s),
                params=np_, cells=None, selection="held-out val")


# ------------------------------------------------------- polynomial ridge
def run_poly(Xtr, ytr, Xte, yte, degrees=(1, 2, 3)):
    """Polynomial ridge regression.  alpha chosen by 5-fold RidgeCV on the
    training split over a 13-point log grid -- standard practice, no
    per-task hand tuning."""
    import numpy as np
    from sklearn.linear_model import RidgeCV
    from sklearn.preprocessing import PolynomialFeatures
    out = []
    A, b = Xtr.numpy(), ytr.numpy()
    C, dte = Xte.numpy(), yte.numpy()
    for deg in degrees:
        pf = PolynomialFeatures(deg, include_bias=False)
        Pa, Pc = pf.fit_transform(A), pf.transform(C)
        mdl = RidgeCV(alphas=np.logspace(-8, 4, 13), cv=5).fit(Pa, b)
        f = lambda M, y: float(np.sqrt(np.mean((mdl.predict(M) - y) ** 2)))
        out.append(dict(method=f"poly{deg}", train=f(Pa, b), test=f(Pc, dte),
                        params=Pa.shape[1] + 1, cells=None))
    return out
