#!/usr/bin/env python3
"""
Binary operators built ONLY from constitutive relations matter supplies for free.
Registered into fabric_sim/operators/op_search.py's OPS dict so that the grammar,
grid X, caps (UCAP/BIG), dedup key and every metric are IDENTICAL to the previous
(mathematically-motivated) search.  operators/ is NOT modified.

Each entry:  (f, df/du, df/dv, domain-mask, "expression   HOST PHYSICS")
"""
import os, sys
import numpy as np

_OPD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "operators")
if _OPD not in sys.path:
    sys.path.insert(0, _OPD)
import op_search as OS                                   # noqa: E402

np.seterr(all="ignore")
UCAP, BIG = OS.UCAP, OS.BIG


# ---------------------------------------------------------------- helpers
def _erf(z):
    """Numerical-Recipes erfc rational approx, |err| < 1.2e-7.  numpy has no erf
    and scipy is unavailable; error is deterministic so dedup stays exact."""
    x = np.abs(z)
    t = 1.0 / (1.0 + 0.5 * x)
    y = t * np.exp(-x * x - 1.26551223 + t * (1.00002368 + t * (0.37409196 + t * (
        0.09678418 + t * (-0.18628806 + t * (0.27886807 + t * (-1.13520398 + t * (
            1.48851587 + t * (-0.82215223 + t * 0.17087277)))))))))
    return np.sign(z) * (1.0 - y)


def _W_of_logz(L, iters=60):
    """Lambert W(z) for z=exp(L)>0, i.e. solve w + ln w = L.  This is exactly the
    DC operating point a diode in series with a resistor settles to on its own."""
    L = np.clip(np.asarray(L, float), -700.0, 1e12)
    w = np.where(L > 1.0, L - np.log(np.maximum(L, 1.0001)), np.exp(np.clip(L, -700, 700)))
    w = np.maximum(w, 1e-300)
    for _ in range(iters):
        g = w + np.log(w) - L
        w = np.maximum(w - g / (1.0 + 1.0 / w), 1e-300)
    return w


def _sig(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -UCAP, UCAP)))


_ALL = lambda u, v: np.ones(np.broadcast(u, v).shape, bool)

# ---------------------------------------------------------------- operators
PHYS = {
 # ===== Boltzmann / Arrhenius : semiconductors, chemical kinetics ===========
 "bol": (lambda u, v: np.exp(u - v),
         lambda u, v: np.exp(u - v),           lambda u, v: -np.exp(u - v),
         _ALL, "exp(u-v)                Arrhenius/detailed-balance rate ratio"),
 "dio": (lambda u, v: v * (np.exp(u) - 1.0),
         lambda u, v: v * np.exp(u),           lambda u, v: np.exp(u) - 1.0,
         _ALL, "v*(exp(u)-1)            Shockley diode / subthreshold MOS"),

 # ===== Nernst / electrochemistry ==========================================
 "nrn": (lambda u, v: np.log(u / v),
         lambda u, v: 1.0 / u,                 lambda u, v: -1.0 / v,
         lambda u, v: (u > 0.0) & (v > 0.0),
         "ln(u/v)                 Nernst concentration cell"),
 "nsp": (lambda u, v: np.logaddexp(0.0, u) - np.logaddexp(0.0, v),
         lambda u, v: _sig(u),                 lambda u, v: -_sig(v),
         _ALL, "sp(u)-sp(v)             two-state population log-ratio (reg. Nernst)"),

 # ===== Josephson : superconductors ========================================
 "jjs": (lambda u, v: np.sin(u) + np.sin(v),
         lambda u, v: np.cos(u),               lambda u, v: np.cos(v),
         _ALL, "sin(u)+sin(v)           two junctions summing at a node"),
 "squ": (lambda u, v: np.sin(u) * np.cos(v),
         lambda u, v: np.cos(u) * np.cos(v),   lambda u, v: -np.sin(u) * np.sin(v),
         _ALL, "sin(u)*cos(v)           dc SQUID, flux-modulated Ic"),
 "rsj": (lambda u, v: np.sin(u) + v,
         lambda u, v: np.cos(u),               lambda u, v: np.ones_like(v),
         _ALL, "sin(u)+v                JJ shunted by a geometric inductance"),
 "ejs": (lambda u, v: np.exp(u) - np.sin(v),
         lambda u, v: np.exp(u),               lambda u, v: -np.cos(v),
         _ALL, "exp(u)-sin(v)           diode + JJ summing at a node (HYBRID)"),
 "njs": (lambda u, v: np.log(u) - np.sin(v),
         lambda u, v: 1.0 / u,                 lambda u, v: -np.cos(v),
         lambda u, v: u > 0.0,
         "ln(u)-sin(v)            Nernst cell + JJ (HYBRID)"),

 # ===== Binding kinetics / saturable absorption ============================
 "mmk": (lambda u, v: u / (u + v),
         lambda u, v: v / (u + v) ** 2,        lambda u, v: -u / (u + v) ** 2,
         lambda u, v: np.abs(u + v) > 1e-9,
         "u/(u+v)                 Michaelis-Menten / Langmuir binding"),
 "hl2": (lambda u, v: u * u / (u * u + v * v),
         lambda u, v: 2.0 * u * v * v / (u * u + v * v) ** 2,
         lambda u, v: -2.0 * u * u * v / (u * u + v * v) ** 2,
         lambda u, v: (u * u + v * v) > 1e-18,
         "u^2/(u^2+v^2)           Hill n=2 cooperative binding"),
 "par": (lambda u, v: u * v / (u + v),
         lambda u, v: v * v / (u + v) ** 2,    lambda u, v: u * u / (u + v) ** 2,
         lambda u, v: np.abs(u + v) > 1e-9,
         "uv/(u+v)                Kirchhoff parallel / saturable absorber"),

 # ===== Tunnelling : memristors, atomic switches ===========================
 "tun": (lambda u, v: u * np.exp(-v),
         lambda u, v: np.exp(-v),              lambda u, v: -u * np.exp(-v),
         _ALL, "u*exp(-v)               tunnel gap: bias x exp(-d/lambda)"),

 # ===== Mass action : chemistry ============================================
 "mas": (lambda u, v: u * v,
         lambda u, v: v,                       lambda u, v: u,
         _ALL, "u*v                     bimolecular mass action  [CONTROL]"),

 # ===== Fermi-Dirac occupancy : any electron gas ===========================
 "fmi": (lambda u, v: _sig(u - v),
         lambda u, v: _sig(u - v) * (1 - _sig(u - v)),
         lambda u, v: -_sig(u - v) * (1 - _sig(u - v)),
         _ALL, "1/(1+e^(v-u))           Fermi-Dirac occupancy"),

 # ===== Diffusion : erf / Gaussian =========================================
 "dfz": (lambda u, v: _erf(u * np.exp(-v)),
         lambda u, v: 2.0 / np.sqrt(np.pi) * np.exp(-(u * np.exp(-v)) ** 2 - v),
         lambda u, v: -2.0 / np.sqrt(np.pi) * np.exp(-(u * np.exp(-v)) ** 2) * u * np.exp(-v),
         _ALL, "erf(u*e^-v)             1-D diffusion profile (u=x, e^v=sqrt(4Dt))"),
 "gsn": (lambda u, v: u * np.exp(-v * v),
         lambda u, v: np.exp(-v * v),          lambda u, v: -2.0 * v * u * np.exp(-v * v),
         _ALL, "u*exp(-v^2)             Gaussian/diffusive kernel weight"),

 # ===== Mean-field spin / ferroelectric ====================================
 "spn": (lambda u, v: np.tanh(np.clip(u + v, -UCAP, UCAP)),
         lambda u, v: 1.0 / np.cosh(np.clip(u + v, -UCAP, UCAP)) ** 2,
         lambda u, v: 1.0 / np.cosh(np.clip(u + v, -UCAP, UCAP)) ** 2,
         _ALL, "tanh(u+v)               mean-field Ising magnetisation"),

 # ===== Self-consistent settling : Lambert W ===============================
 #   node voltage of a diode fed through a series resistance R=e^v.
 #   Matter solves the transcendental equation by relaxing to its operating point.
 "lmw": (lambda u, v: u - _W_of_logz(u + v),
         lambda u, v: 1.0 / (1.0 + _W_of_logz(u + v)),
         lambda u, v: -_W_of_logz(u + v) / (1.0 + _W_of_logz(u + v)),
         _ALL, "u - W(e^(u+v))          diode + series R settling  [Lambert W]"),
 "lmj": (lambda u, v: u - _W_of_logz(u + v) - np.sin(v),
         lambda u, v: 1.0 / (1.0 + _W_of_logz(u + v)),
         lambda u, v: -_W_of_logz(u + v) / (1.0 + _W_of_logz(u + v)) - np.cos(v),
         _ALL, "u-W(e^(u+v))-sin(v)     diode+R+JJ at one node  [HYBRID]"),
}

OS.OPS.update(PHYS)
