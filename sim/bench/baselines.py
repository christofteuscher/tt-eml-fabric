"""
Common baseline harness: fit and score conventional approximators on an
arbitrary (X, y) regression task, ALWAYS reporting accuracy against a
resource count.

The resource count is the number of stored parameters, i.e. what a chip or
a microcontroller would have to hold:

  polynomial, degree p, d inputs   C(p+d, d) coefficients
  cubic spline, m interior knots   m + 4 B-spline coefficients (knots are on
                                   a fixed uniform grid, so they cost nothing
                                   to store; `params_with_knots` reports the
                                   alternative convention)
  LUT, N entries per axis          N**d stored values (grid implicit); the
                                   table is FIT to the data by least squares
                                   on the hat-function basis, it does not
                                   peek at the true function
  MLP, width w, h hidden layers    all weights and biases, counted exactly

For comparison, the EML fabric stores 6 numbers per cell plus a 2-number
readout, so a depth-D binary tree of 2**D - 1 cells costs 6*(2**D - 1) + 2
parameters: 44 at depth 3, 92 at depth 4, 380 at depth 6, 1532 at depth 8.

Every method is scored with the same metric (RMSE in the task's own units)
on the same three sets: the training points, a fresh in-range test set, and
the extrapolation set.
"""
from __future__ import annotations

import itertools
import math
import time
from dataclasses import dataclass, field, asdict

import numpy as np


# ---------------------------------------------------------------------------
@dataclass
class Task:
    """X: (n, d). y in the units the RMSE should be reported in."""
    name: str
    Xtr: np.ndarray
    ytr: np.ndarray
    Xte: np.ndarray
    yte: np.ndarray
    Xex: np.ndarray | None = None
    yex: np.ndarray | None = None
    unit: str = ""

    @property
    def d(self):
        return self.Xtr.shape[1]


@dataclass
class Result:
    method: str
    params: int
    rmse_train: float
    rmse_test: float
    rmse_extrap: float = float("nan")
    seconds: float = 0.0
    extra: dict = field(default_factory=dict)


def rmse(a, b):
    a = np.asarray(a, dtype=np.float64)
    a = np.where(np.isfinite(a), a, 1e12)
    return float(np.sqrt(np.mean((a - b) ** 2)))


def _score(name, params, predict, task, t0, **extra):
    return Result(
        method=name, params=int(params),
        rmse_train=rmse(predict(task.Xtr), task.ytr),
        rmse_test=rmse(predict(task.Xte), task.yte),
        rmse_extrap=(rmse(predict(task.Xex), task.yex)
                     if task.Xex is not None else float("nan")),
        seconds=time.time() - t0, extra=extra)


# ---------------------------------------------------------------------------
# feature transforms (generic; identity by default)
# ---------------------------------------------------------------------------
XFORMS = {
    "id": (lambda X: X, "x"),
    "log": (lambda X: np.log(np.clip(X, 1e-300, None)), "log x"),
}
YFORMS = {
    # (forward, inverse, label)
    "id": (lambda y: y, lambda z: z, "y"),
    "recip": (lambda y: 1.0 / y, lambda z: 1.0 / np.where(
        np.abs(z) < 1e-300, 1e-300, z), "1/y"),
}


# ---------------------------------------------------------------------------
# 1. polynomial regression
# ---------------------------------------------------------------------------
def _monomials(d, deg):
    out = []
    for total in range(deg + 1):
        for c in itertools.combinations_with_replacement(range(d), total):
            p = [0] * d
            for i in c:
                p[i] += 1
            out.append(tuple(p))
    return out


def _design(X, powers, lo, hi):
    Z = 2.0 * (X - lo) / np.where(hi - lo == 0, 1.0, hi - lo) - 1.0  # cond.
    return np.stack([np.prod(Z ** np.array(p), axis=1) for p in powers], 1)


def fit_poly(task, deg, xform="id", yform="id"):
    t0 = time.time()
    fx = XFORMS[xform][0]
    fy, fyi = YFORMS[yform][0], YFORMS[yform][1]
    Xt = fx(task.Xtr)
    lo, hi = Xt.min(0), Xt.max(0)
    powers = _monomials(task.d, deg)
    A = _design(Xt, powers, lo, hi)
    coef, *_ = np.linalg.lstsq(A, fy(task.ytr), rcond=None)

    def predict(X):
        return fyi(_design(fx(X), powers, lo, hi) @ coef)

    lbl = f"poly{deg}"
    if xform != "id" or yform != "id":
        lbl += f"[{YFORMS[yform][2]} vs {XFORMS[xform][1]}]"
    return _score(lbl, len(powers), predict, task, t0, degree=deg,
                  xform=xform, yform=yform)


# ---------------------------------------------------------------------------
# 2. cubic spline / piecewise polynomial (1-D)
# ---------------------------------------------------------------------------
def fit_spline(task, n_interior, xform="id", yform="id"):
    from scipy.interpolate import LSQUnivariateSpline
    assert task.d == 1, "spline baseline is 1-D"
    t0 = time.time()
    fx = XFORMS[xform][0]
    fy, fyi = YFORMS[yform][0], YFORMS[yform][1]
    x = fx(task.Xtr)[:, 0]
    o = np.argsort(x)
    xs, ys = x[o], fy(task.ytr)[o]
    lo, hi = xs[0], xs[-1]
    # interior knots on a uniform grid in the (transformed) input
    t = np.linspace(lo, hi, n_interior + 2)[1:-1]
    sp = LSQUnivariateSpline(xs, ys, t=t, k=3, ext=0)  # ext=0 -> extrapolate

    def predict(X):
        return fyi(sp(fx(X)[:, 0]))

    n_coef = n_interior + 4
    lbl = f"spline-k{n_interior}"
    if xform != "id" or yform != "id":
        lbl += f"[{YFORMS[yform][2]} vs {XFORMS[xform][1]}]"
    return _score(lbl, n_coef, predict, task, t0, n_interior=n_interior,
                  params_with_knots=n_coef + n_interior, xform=xform,
                  yform=yform)


# ---------------------------------------------------------------------------
# 3. lookup table with linear interpolation, N entries (per axis)
# ---------------------------------------------------------------------------
def _hat_basis(z, grid):
    """Piecewise-linear (hat) basis, linear extrapolation outside."""
    n = len(grid)
    idx = np.clip(np.searchsorted(grid, z) - 1, 0, n - 2)
    x0, x1 = grid[idx], grid[idx + 1]
    w = (z - x0) / (x1 - x0)              # not clipped -> linear extrapolation
    B = np.zeros((len(z), n))
    rows = np.arange(len(z))
    B[rows, idx] = 1.0 - w
    B[rows, idx + 1] = w
    return B


def fit_lut(task, n_entries, xform="id", yform="id"):
    """Least-squares fit of a piecewise-linear table on a fixed uniform grid.
    d-dimensional version uses a tensor-product (multilinear) table."""
    t0 = time.time()
    fx = XFORMS[xform][0]
    fy, fyi = YFORMS[yform][0], YFORMS[yform][1]
    Xt = fx(task.Xtr)
    lo, hi = Xt.min(0), Xt.max(0)
    grids = [np.linspace(lo[j], hi[j], n_entries) for j in range(task.d)]

    def design(X):
        Z = fx(X)
        B = _hat_basis(Z[:, 0], grids[0])
        for j in range(1, task.d):
            Bj = _hat_basis(Z[:, j], grids[j])
            B = (B[:, :, None] * Bj[:, None, :]).reshape(len(Z), -1)
        return B

    A = design(task.Xtr)
    lam = 1e-8 * np.trace(A.T @ A) / A.shape[1]     # tiny ridge for empty cells
    tab = np.linalg.solve(A.T @ A + lam * np.eye(A.shape[1]),
                          A.T @ fy(task.ytr))

    def predict(X):
        return fyi(design(X) @ tab)

    n_par = n_entries ** task.d
    lbl = f"lut-{n_entries}"
    if xform != "id" or yform != "id":
        lbl += f"[{YFORMS[yform][2]} vs {XFORMS[xform][1]}]"
    return _score(lbl, n_par, predict, task, t0, entries=n_par,
                  per_axis=n_entries, xform=xform, yform=yform)


# ---------------------------------------------------------------------------
# 4. small MLP
# ---------------------------------------------------------------------------
def fit_mlp(task, width, hidden, seed=0, iters=3000, lr=0.02, act="tanh",
            xform="id"):
    import torch
    t0 = time.time()
    torch.manual_seed(seed)
    fx = XFORMS[xform][0]
    Xt = fx(task.Xtr)
    mu, sd = Xt.mean(0), Xt.std(0) + 1e-12
    ymu, ysd = task.ytr.mean(), task.ytr.std() + 1e-12

    def prep(X):
        return torch.tensor((fx(X) - mu) / sd, dtype=torch.float64)

    layers, nin = [], task.d
    A = {"tanh": torch.nn.Tanh, "relu": torch.nn.ReLU}[act]
    for _ in range(hidden):
        layers += [torch.nn.Linear(nin, width, dtype=torch.float64), A()]
        nin = width
    layers += [torch.nn.Linear(nin, 1, dtype=torch.float64)]
    net = torch.nn.Sequential(*layers)
    n_par = sum(p.numel() for p in net.parameters())

    xt, tt = prep(task.Xtr), torch.tensor((task.ytr - ymu) / ysd)
    opt = torch.optim.Adam(net.parameters(), lr=lr)
    best, best_state = float("inf"), None
    for it in range(1, iters + 1):
        opt.param_groups[0]["lr"] = 1e-4 + 0.5 * (lr - 1e-4) * (
            1 + math.cos(math.pi * it / iters))
        opt.zero_grad()
        loss = torch.mean((net(xt)[:, 0] - tt) ** 2)
        loss.backward()
        opt.step()
        if it % 50 == 0 or it == iters:
            v = float(loss.detach())
            if v < best:
                best, best_state = v, {k: p.detach().clone()
                                       for k, p in net.state_dict().items()}
    if best_state is not None:
        net.load_state_dict(best_state)

    @torch.no_grad()
    def predict(X):
        return (net(prep(X))[:, 0].numpy() * ysd + ymu)

    lbl = f"mlp-{width}x{hidden}"
    if xform != "id":
        lbl += f"[{XFORMS[xform][1]}]"
    return _score(lbl, n_par, predict, task, t0, width=width, hidden=hidden,
                  seed=seed, iters=iters, xform=xform)


# ---------------------------------------------------------------------------
def run_suite(task, degrees=(1, 2, 3, 4, 5, 6, 7, 8, 9),
              knots=(1, 2, 4, 8, 16, 32), lut=(4, 8, 16, 32, 64, 128),
              mlps=((4, 1), (8, 1), (16, 1), (32, 1), (8, 2), (16, 2), (32, 2)),
              seeds=3, iters=3000, xforms=("id",), yforms=("id",),
              max_params=30000):
    """Fit every baseline family on an arbitrary Task. Returns [Result]."""
    res = []
    for xf in xforms:
        for yf in yforms:
            for d in degrees:
                if len(_monomials(task.d, d)) <= max_params:
                    res.append(fit_poly(task, d, xform=xf, yform=yf))
            if task.d == 1:
                for k in knots:
                    res.append(fit_spline(task, k, xform=xf, yform=yf))
            for n in lut:
                if n ** task.d <= min(max_params, len(task.ytr)):
                    res.append(fit_lut(task, n, xform=xf, yform=yf))
        for (w, h) in mlps:
            runs = [fit_mlp(task, w, h, seed=s, iters=iters, xform=xf)
                    for s in range(seeds)]
            best = min(runs, key=lambda r: r.rmse_test)
            best.extra["role"] = f"best-of-{seeds}-seeds"
            med = sorted(runs, key=lambda r: r.rmse_test)[len(runs) // 2]
            med = Result(**{**asdict(med), "method": med.method + " (median seed)"})
            med.extra["role"] = f"median-of-{seeds}-seeds"
            res += [best, med]
    return res


def eml_params(depth):
    """Stored parameters of a depth-`depth` binary EML tree (6/cell + 2)."""
    return 6 * (2 ** depth - 1) + 2


def summarize(results, unit=""):
    hdr = (f"{'method':34s} {'params':>7s} {'train':>10s} {'test':>10s} "
           f"{'extrap':>10s}")
    lines = [hdr, "-" * len(hdr)]
    for r in results:
        lines.append(f"{r.method:34s} {r.params:7d} {r.rmse_train:10.4g} "
                     f"{r.rmse_test:10.4g} {r.rmse_extrap:10.4g}")
    if unit:
        lines.append(f"(RMSE in {unit})")
    return "\n".join(lines)


def pareto(results):
    """Cheapest method reaching each accuracy, as (params, rmse_test, name)."""
    rs = sorted(results, key=lambda r: (r.params, r.rmse_test))
    out, best = [], float("inf")
    for r in rs:
        if r.rmse_test < best:
            best = r.rmse_test
            out.append((r.params, r.rmse_test, r.method))
    return out


def to_dicts(results):
    return [asdict(r) for r in results]
