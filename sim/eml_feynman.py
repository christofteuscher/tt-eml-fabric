"""
Multivariate targets for the EML fabric: a slice of the AI Feynman set.

Each entry is (fn, [(name, lo, hi), ...]) with the sampling box taken from
the AI Feynman database convention (all boxes positive, which suits a
log-domain fabric; nothing here needs a negative argument to ln).

Variable counts run 2, 3, 4, 5, 6, 9 so the "2-9 variables" claim in the
paper is covered at both ends.  Two of them are deliberately adversarial:

  * `I.11.19` is a dot product, i.e. a pure SUM of products.  A log-domain
    cell multiplies for free and adds badly, so this is the case where the
    fabric should struggle.
  * `I.44.4` contains an explicit ln, so it is close to exactly
    representable and acts as the easy control.

Sampling is uniform in the box, in double precision.  Targets are reported
as NRMSE = RMSE / RMS(y) so formulas with wildly different output scales
are comparable; `make_data_mv` also returns the raw scale.
"""
import math

import torch

REAL_DTYPE = torch.float64


def _v(x, i):
    return x[:, i]


FEYNMAN = {
    # name: (fn(X) -> (B,), [(var, lo, hi), ...], comment)
    "I.12.1": (
        lambda X: _v(X, 0) * _v(X, 1),
        [("mu", 1.0, 5.0), ("Nn", 1.0, 5.0)],
        "F = mu Nn -- multiplication, the canonical log-domain win"),
    "I.6.2": (
        lambda X: torch.exp(-(_v(X, 0) / _v(X, 1)) ** 2 / 2)
        / (math.sqrt(2 * math.pi) * _v(X, 1)),
        [("theta", 1.0, 3.0), ("sigma", 1.0, 3.0)],
        "Gaussian -- exp of a ratio squared"),
    "I.15.10": (
        lambda X: _v(X, 0) * _v(X, 1)
        / torch.sqrt(1 - _v(X, 1) ** 2 / _v(X, 2) ** 2),
        [("m0", 1.0, 5.0), ("v", 1.0, 2.0), ("c", 3.0, 10.0)],
        "relativistic momentum -- product with a sqrt(1-r^2) factor"),
    "I.44.4": (
        lambda X: _v(X, 0) * _v(X, 1) * _v(X, 2)
        * torch.log(_v(X, 4) / _v(X, 3)),
        [("n", 1.0, 5.0), ("kb", 1.0, 5.0), ("T", 1.0, 5.0),
         ("V1", 1.0, 5.0), ("V2", 1.0, 5.0)],
        "entropy change -- contains an explicit ln (easy control)"),
    "II.11.20": (
        lambda X: _v(X, 0) * _v(X, 1) ** 2 * _v(X, 2)
        / (3 * _v(X, 3) * _v(X, 4)),
        [("nrho", 1.0, 5.0), ("pd", 1.0, 5.0), ("Ef", 1.0, 5.0),
         ("kb", 1.0, 5.0), ("T", 1.0, 5.0)],
        "pure monomial in 5 variables"),
    "I.11.19": (
        lambda X: _v(X, 0) * _v(X, 1) + _v(X, 2) * _v(X, 3)
        + _v(X, 4) * _v(X, 5),
        [("x1", 1.0, 5.0), ("y1", 1.0, 5.0), ("x2", 1.0, 5.0),
         ("y2", 1.0, 5.0), ("x3", 1.0, 5.0), ("y3", 1.0, 5.0)],
        "dot product -- a SUM of products (adversarial for log domain)"),
    "I.9.18": (
        lambda X: _v(X, 0) * _v(X, 1) * _v(X, 2)
        / ((_v(X, 4) - _v(X, 3)) ** 2 + (_v(X, 6) - _v(X, 5)) ** 2
           + (_v(X, 8) - _v(X, 7)) ** 2),
        [("G", 1.0, 2.0), ("m1", 1.0, 2.0), ("m2", 1.0, 2.0),
         ("x1", 3.0, 4.0), ("x2", 1.0, 2.0), ("y1", 3.0, 4.0),
         ("y2", 1.0, 2.0), ("z1", 3.0, 4.0), ("z2", 1.0, 2.0)],
        "Newtonian gravity in Cartesian coordinates -- 9 variables"),
}


def n_vars(name):
    return len(FEYNMAN[name][1])


def var_names(name):
    return [v[0] for v in FEYNMAN[name][1]]


def make_data_mv(name, n_train=512, n_test=512, seed=1234, normalise=True):
    """Returns xt (n_train, n_vars), tt, xv, tv, scale, unit.

    With normalise=True the target is divided by its training RMS, so a
    reported RMSE is already an NRMSE and 1.0 means "explains nothing".
    `scale` is the factor that converts back to physical units.
    """
    fn, box, _ = FEYNMAN[name]
    g = torch.Generator().manual_seed(seed)

    def draw(n):
        cols = [torch.empty(n, dtype=REAL_DTYPE).uniform_(lo, hi, generator=g)
                for _, lo, hi in box]
        return torch.stack(cols, dim=1)

    xt, xv = draw(n_train), draw(n_test)
    tt, tv = fn(xt), fn(xv)
    scale = float(torch.sqrt(torch.mean(tt ** 2))) if normalise else 1.0
    return xt, tt / scale, xv, tv / scale, scale, "nrmse"
