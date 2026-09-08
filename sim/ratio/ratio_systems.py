"""Systems for the RATIO x CONTRACTING hypothesis test.

Hypothesis under test: the analog EML fabric wins as an ODE nonlinearity
surrogate when BOTH (i) the nonlinear term is ratio/saturation structured
(log-linearisable, suits the eml grammar) and (ii) the dynamics contract.

The design is a 2x2 factorial, plus three MATCHED PAIRS in which the
nonlinear term is IDENTICAL and only the dynamics change:

    N(x,y) = x*y        bimolecular (contracting) | lotka_volterra (conserv.)
    N(p)   = 1/(1+p^n)  gene_autoreg (contracting) | repressilator (limit cyc.)
    N(th)  = sin(th)    pendulum_damped (contract.) | pendulum (conservative)

Each entry:
  rhs(t, X)          exact field
  sub(t, X, N)       field with the nonlinear term replaced by N: (B,nvars)->(B,k)
  nl(P)              exact nonlinear term, returns (B,k)
  nl_cols            state indices that feed the nonlinear term
  inv(X) or None     conserved quantity
  ics, T, dim, nvars, n_out, cls ('ratio'|'poly') x ('contract'|'osc')
"""
import numpy as np


def _c(*a):
    return np.stack(a, axis=1)


# ===========================================================================
# CELL A: ratio-structured AND contracting
# ===========================================================================

# --- Hill / cooperative binding decay cascade ------------------------------
# dS = -V S^n/(K^n+S^n);  dP = +V S^n/(K^n+S^n) - kp P
def _hill(n, V=1.0, K=1.0, kp=0.3):
    def nl(P):
        S = np.clip(P[:, 0], 0.0, None)
        return _c(V * S ** n / (K ** n + S ** n))

    def rhs(t, X):
        v = float(nl(np.array([[X[0]]]))[0, 0])
        return [-v, v - kp * X[1]]

    def sub(t, X, N):
        v = float(N(np.array([[X[0]]]))[0, 0])
        return [-v, v - kp * X[1]]
    return nl, rhs, sub


# --- two-step enzyme cascade, two coupled MM rate laws ---------------------
EC = dict(V1=1.0, K1=0.6, V2=0.8, K2=0.4)


def ec_nl(P):
    S, I = np.clip(P[:, 0], 0, None), np.clip(P[:, 1], 0, None)
    return _c(EC["V1"] * S / (EC["K1"] + S), EC["V2"] * I / (EC["K2"] + I))


def ec_rhs(t, X):
    v = ec_nl(np.array([[X[0], X[1]]]))[0]
    return [-v[0], v[0] - v[1], v[1]]


def ec_sub(t, X, N):
    v = N(np.array([[X[0], X[1]]]))[0]
    return [-float(v[0]), float(v[0] - v[1]), float(v[1])]


# --- negative autoregulation: Hill repression, contracting to fixed point --
GA = dict(a=4.0, K=1.0, n=2.0, b=1.0, c=0.6)


def ga_nl(P):
    p = np.clip(P[:, 0], 0, None)
    return _c(1.0 / (1.0 + (p / GA["K"]) ** GA["n"]))


def ga_rhs(t, X):
    h = float(ga_nl(np.array([[X[1]]]))[0, 0])
    return [GA["a"] * h - X[0], GA["b"] * X[0] - GA["c"] * X[1]]


def ga_sub(t, X, N):
    h = float(N(np.array([[X[1]]]))[0, 0])
    return [GA["a"] * h - X[0], GA["b"] * X[0] - GA["c"] * X[1]]


# --- Monod chemostat: saturating growth, stable steady state ---------------
MO = dict(mu=1.2, Ks=0.5, D=0.4, Sin=3.0, Y=0.5)


def mo_nl(P):                      # N(S,X) = S/(Ks+S) * X
    S, Xc = np.clip(P[:, 0], 0, None), P[:, 1]
    return _c(MO["mu"] * S / (MO["Ks"] + S) * Xc)


def mo_rhs(t, X):
    g = float(mo_nl(np.array([[X[0], X[1]]]))[0, 0])
    return [MO["D"] * (MO["Sin"] - X[0]) - g / MO["Y"], g - MO["D"] * X[1]]


def mo_sub(t, X, N):
    g = float(N(np.array([[X[0], X[1]]]))[0, 0])
    return [MO["D"] * (MO["Sin"] - X[0]) - g / MO["Y"], g - MO["D"] * X[1]]


# --- Gompertz growth: log-structured, contracting to carrying capacity -----
GO = dict(r=0.8, K=3.0, kp=0.4)


def go_nl(P):
    x = np.clip(P[:, 0], 1e-6, None)
    return _c(-GO["r"] * x * np.log(x / GO["K"]))


def go_rhs(t, X):
    g = float(go_nl(np.array([[X[0]]]))[0, 0])
    return [g, g - GO["kp"] * X[1]]


def go_sub(t, X, N):
    g = float(N(np.array([[X[0]]]))[0, 0])
    return [g, g - GO["kp"] * X[1]]


# --- bimolecular mass action: SAME N = x*y as Lotka-Volterra, contracting --
BI = dict(k=0.8)


def bi_nl(P):
    return _c(P[:, 0] * P[:, 1])


def bi_rhs(t, X):
    v = BI["k"] * float(bi_nl(np.array([[X[0], X[1]]]))[0, 0])
    return [-v, -v]


def bi_sub(t, X, N):
    v = BI["k"] * float(N(np.array([[X[0], X[1]]]))[0, 0])
    return [-v, -v]


# --- bi-substrate Michaelis-Menten: THE ORIGINAL WIN, verbatim from -------
#     fabric_sim/ode/ode_systems.py (vmax=1, ka=0.5, kb=1, T=6).  Included
#     as a control: the prior study compared it only against a polynomial,
#     never against an MLP.
MM = dict(vmax=1.0, ka=0.5, kb=1.0)


def mm_nl(P):
    A, B = P[:, 0], P[:, 1]
    return _c(MM["vmax"] * A * B / ((MM["ka"] + A) * (MM["kb"] + B)))


def mm_rhs(t, X):
    v = float(mm_nl(np.array([[X[0], X[1]]]))[0, 0])
    return [-v, -v]


def mm_sub(t, X, N):
    v = float(N(np.array([[X[0], X[1]]]))[0, 0])
    return [-v, -v]


# ===========================================================================
# CELL B: ratio-structured but OSCILLATORY / conservative
# ===========================================================================

# --- repressilator: SAME Hill N as gene_autoreg, limit cycle ---------------
RP = dict(alpha=20.0, beta=1.0, n=2.0)


def rp_nl(P):
    p = np.clip(P[:, 0], 0, None)
    return _c(1.0 / (1.0 + p ** RP["n"]))


def _rp(hfun, X):
    m1, m2, m3, p1, p2, p3 = X
    a, b = RP["alpha"], RP["beta"]
    h1, h2, h3 = hfun(p3), hfun(p1), hfun(p2)
    return [a * h1 - m1, a * h2 - m2, a * h3 - m3,
            b * (m1 - p1), b * (m2 - p2), b * (m3 - p3)]


def rp_rhs(t, X):
    return _rp(lambda v: float(rp_nl(np.array([[v]]))[0, 0]), X)


def rp_sub(t, X, N):
    return _rp(lambda v: float(N(np.array([[v]]))[0, 0]), X)


# --- Goodwin oscillator: Hill repression + linear chain --------------------
GW = dict(k1=1.0, k2=0.2, k3=1.0, k4=0.2, k5=1.0, k6=0.2, K=1.0, n=12.0)


def gw_nl(P):
    z = np.clip(P[:, 0], 0, None)
    return _c(1.0 / (1.0 + (z / GW["K"]) ** GW["n"]))


def gw_rhs(t, X):
    h = float(gw_nl(np.array([[X[2]]]))[0, 0])
    return [GW["k1"] * h - GW["k2"] * X[0], GW["k3"] * X[0] - GW["k4"] * X[1],
            GW["k5"] * X[1] - GW["k6"] * X[2]]


def gw_sub(t, X, N):
    h = float(N(np.array([[X[2]]]))[0, 0])
    return [GW["k1"] * h - GW["k2"] * X[0], GW["k3"] * X[0] - GW["k4"] * X[1],
            GW["k5"] * X[1] - GW["k6"] * X[2]]


# --- Lotka-Volterra: SAME N = x*y as bimolecular, conservative ------------
LV = dict(a=1.5, b=1.0, c=3.0, d=1.0)


def lv_nl(P):
    return _c(P[:, 0] * P[:, 1])


def lv_rhs(t, X):
    n = float(lv_nl(np.array([[X[0], X[1]]]))[0, 0])
    return [LV["a"] * X[0] - LV["b"] * n, -LV["c"] * X[1] + LV["d"] * n]


def lv_sub(t, X, N):
    n = float(N(np.array([[X[0], X[1]]]))[0, 0])
    return [LV["a"] * X[0] - LV["b"] * n, -LV["c"] * X[1] + LV["d"] * n]


def lv_inv(X):
    x, y = np.clip(X[0], 1e-9, None), np.clip(X[1], 1e-9, None)
    return LV["d"] * x - LV["c"] * np.log(x) + LV["b"] * y - LV["a"] * np.log(y)


# ===========================================================================
# CELL C: contracting but NOT ratio-structured
# ===========================================================================

# --- logistic: N = x - x^2/K, an additive mix, not log-linearisable -------
LG = dict(r=1.0, K=3.0, kp=0.4)


def lg_nl(P):
    x = P[:, 0]
    return _c(LG["r"] * x * (1.0 - x / LG["K"]))


def lg_rhs(t, X):
    g = float(lg_nl(np.array([[X[0]]]))[0, 0])
    return [g, g - LG["kp"] * X[1]]


def lg_sub(t, X, N):
    g = float(N(np.array([[X[0]]]))[0, 0])
    return [g, g - LG["kp"] * X[1]]


# --- damped Duffing: N = x + b x^3 restoring force, contracting spiral -----
DU = dict(d=0.4, b=1.0)


def du_nl(P):
    x = P[:, 0]
    return _c(x + DU["b"] * x ** 3)


def du_rhs(t, X):
    f = float(du_nl(np.array([[X[0]]]))[0, 0])
    return [X[1], -DU["d"] * X[1] - f]


def du_sub(t, X, N):
    f = float(N(np.array([[X[0]]]))[0, 0])
    return [X[1], -DU["d"] * X[1] - f]


# --- damped pendulum: SAME N = sin th as the conservative pendulum --------
PD = dict(d=0.35, gl=1.0)


def pd_nl(P):
    return _c(np.sin(P[:, 0]))


def pd_rhs(t, X):
    s = float(pd_nl(np.array([[X[0]]]))[0, 0])
    return [X[1], -PD["d"] * X[1] - PD["gl"] * s]


def pd_sub(t, X, N):
    s = float(N(np.array([[X[0]]]))[0, 0])
    return [X[1], -PD["d"] * X[1] - PD["gl"] * s]


# ===========================================================================
# CELL D: neither (corner control)
# ===========================================================================
BR = dict(a=1.0, b=3.0)


def br_nl(P):                      # N(x,y) = x^2 y
    return _c(P[:, 0] ** 2 * P[:, 1])


def br_rhs(t, X):
    n = float(br_nl(np.array([[X[0], X[1]]]))[0, 0])
    return [BR["a"] - (BR["b"] + 1) * X[0] + n, BR["b"] * X[0] - n]


def br_sub(t, X, N):
    n = float(N(np.array([[X[0], X[1]]]))[0, 0])
    return [BR["a"] - (BR["b"] + 1) * X[0] + n, BR["b"] * X[0] - n]


# ===========================================================================
h1_nl, h1_rhs, h1_sub = _hill(1.0)
h2_nl, h2_rhs, h2_sub = _hill(2.0)
h4_nl, h4_rhs, h4_sub = _hill(4.0)


def S(nl, rhs, sub, nvars, n_out, dim, T, ics, cols, cls, desc, inv=None):
    return dict(nl=nl, rhs=rhs, sub=sub, nvars=nvars, n_out=n_out, dim=dim,
                T=T, ics=ics, nl_cols=cols, cls=cls, desc=desc, inv=inv)


SYSTEMS = {
    # ---- ratio x contracting ---------------------------------------------
    "hill_n1": S(h1_nl, h1_rhs, h1_sub, 1, 1, 2, 8.0,
                 [(3.0, 0.0), (2.0, 0.5), (4.0, 0.0), (1.0, 1.0)], [0],
                 "ratio/contract", "dS=-V S/(K+S); Hill n=1 (Michaelis)"),
    "hill_n2": S(h2_nl, h2_rhs, h2_sub, 1, 1, 2, 8.0,
                 [(3.0, 0.0), (2.0, 0.5), (4.0, 0.0), (1.0, 1.0)], [0],
                 "ratio/contract", "Hill n=2 cooperative binding"),
    "hill_n4": S(h4_nl, h4_rhs, h4_sub, 1, 1, 2, 8.0,
                 [(3.0, 0.0), (2.0, 0.5), (4.0, 0.0), (1.0, 1.0)], [0],
                 "ratio/contract", "Hill n=4 cooperative binding"),
    "enzyme_cascade": S(ec_nl, ec_rhs, ec_sub, 2, 2, 3, 10.0,
                        [(3.0, 0.0, 0.0), (2.0, 0.5, 0.0), (4.0, 0.0, 0.0),
                         (1.5, 1.0, 0.0)], [0, 1],
                        "ratio/contract", "two coupled MM rate laws"),
    "gene_autoreg": S(ga_nl, ga_rhs, ga_sub, 1, 1, 2, 20.0,
                      [(0.2, 0.2), (3.0, 0.5), (1.0, 3.0), (2.0, 2.0)], [1],
                      "ratio/contract", "negative autoregulation, Hill n=2"),
    "monod_chemostat": S(mo_nl, mo_rhs, mo_sub, 2, 1, 2, 25.0,
                         [(3.0, 0.1), (0.5, 1.0), (2.0, 1.5), (1.0, 0.3)],
                         [0, 1], "ratio/contract", "Monod chemostat"),
    "gompertz": S(go_nl, go_rhs, go_sub, 1, 1, 2, 10.0,
                  [(0.3, 0.0), (0.8, 0.2), (5.0, 0.0), (1.5, 1.0)], [0],
                  "ratio/contract", "dx=-r x ln(x/K), log-structured"),
    "bimolecular": S(bi_nl, bi_rhs, bi_sub, 2, 1, 2, 8.0,
                     [(3.0, 3.0), (2.0, 3.0), (3.0, 1.5), (1.0, 2.0)], [0, 1],
                     "ratio/contract", "dA=dB=-k A B; SAME N=xy as LV"),
    "mm_bisub": S(mm_nl, mm_rhs, mm_sub, 2, 1, 2, 6.0,
                  [(3.0, 3.0), (2.0, 3.0), (3.0, 1.5), (1.0, 2.0)], [0, 1],
                  "ratio/contract", "THE ORIGINAL WIN: bi-substrate MM"),
    # ---- ratio x oscillatory ---------------------------------------------
    "gene_repressilator": S(rp_nl, rp_rhs, rp_sub, 1, 1, 6, 40.0,
                            [(1.0, 0.0, 0.0, 0.5, 0.0, 0.0),
                             (0.5, 0.2, 0.1, 2.0, 0.5, 0.1),
                             (2.0, 1.0, 0.0, 0.0, 1.0, 0.5),
                             (0.1, 0.1, 0.1, 3.0, 0.2, 0.2)], [3],
                            "ratio/osc", "repressilator; SAME Hill N"),
    "goodwin": S(gw_nl, gw_rhs, gw_sub, 1, 1, 3, 60.0,
                 [(0.5, 0.5, 0.5), (1.0, 0.2, 0.3), (2.0, 1.0, 0.5),
                  (0.3, 1.5, 1.0)], [2],
                 "ratio/osc", "Goodwin oscillator, Hill n=12"),
    "lotka_volterra": S(lv_nl, lv_rhs, lv_sub, 2, 1, 2, 20.0,
                        [(1.0, 1.0), (2.0, 1.0), (3.0, 1.0), (1.5, 2.0)],
                        [0, 1], "ratio/osc", "LV; SAME N=xy as bimolecular",
                        inv=lv_inv),
    # ---- non-ratio x contracting -----------------------------------------
    "logistic": S(lg_nl, lg_rhs, lg_sub, 1, 1, 2, 10.0,
                  [(0.3, 0.0), (0.8, 0.2), (5.0, 0.0), (1.5, 1.0)], [0],
                  "poly/contract", "logistic; N = r x(1-x/K)"),
    "duffing_damped": S(du_nl, du_rhs, du_sub, 1, 1, 2, 20.0,
                        [(2.0, 0.0), (1.0, 1.0), (-1.5, 0.5), (0.5, -1.0)],
                        [0], "poly/contract", "damped Duffing; N = x + x^3"),
    "pendulum_damped": S(pd_nl, pd_rhs, pd_sub, 1, 1, 2, 20.0,
                         [(2.0, 0.0), (1.0, 0.0), (2.8, 0.0), (0.0, 1.5)],
                         [0], "trig/contract", "damped pendulum; N = sin th"),
    # ---- corner control ---------------------------------------------------
    "brusselator": S(br_nl, br_rhs, br_sub, 2, 1, 2, 20.0,
                     [(1.0, 1.0), (2.0, 2.0), (0.5, 3.0), (3.0, 1.0)],
                     [0, 1], "poly/osc", "Brusselator; N = x^2 y"),
}


def nl_args(name, Xtraj):
    """(n_t, nvars) matrix of nonlinear-term arguments along a trajectory."""
    return Xtraj[SYSTEMS[name]["nl_cols"], :].T
