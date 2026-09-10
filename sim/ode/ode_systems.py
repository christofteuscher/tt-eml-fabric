"""ODE systems whose difficulty is the NONLINEAR term.

Each entry gives
  rhs_true(t, X)             exact vector field
  rhs_sub(t, X, N)           same field with the nonlinear term N(pts)->vals
                             substituted (N takes (B, nvars) -> (B,))
  nl_vars(X)                 the arguments the nonlinear term consumes
  nl_true(pts)               the exact nonlinear term
  invariant(X) or None       conserved quantity
  ics, T, name, nvars
"""
import numpy as np

# --- Lotka-Volterra ---------------------------------------------------------
LV = dict(a=1.5, b=1.0, c=3.0, d=1.0)


def lv_nl(P):                      # N(x, y) = x*y
    return P[:, 0] * P[:, 1]


def lv_true(t, X):
    x, y = X
    n = x * y
    return [LV["a"] * x - LV["b"] * n, -LV["c"] * y + LV["d"] * n]


def lv_sub(t, X, N):
    x, y = X
    n = float(N(np.array([[x, y]]))[0])
    return [LV["a"] * x - LV["b"] * n, -LV["c"] * y + LV["d"] * n]


def lv_inv(X):                     # d x - c ln x + b y - a ln y
    x, y = np.clip(X[0], 1e-9, None), np.clip(X[1], 1e-9, None)
    return (LV["d"] * x - LV["c"] * np.log(x)
            + LV["b"] * y - LV["a"] * np.log(y))


# --- Van der Pol ------------------------------------------------------------
MU = 1.0


def vdp_nl(P):                     # N(x, y) = (1 - x^2) y
    return (1.0 - P[:, 0] ** 2) * P[:, 1]


def vdp_true(t, X):
    x, y = X
    return [y, MU * (1.0 - x * x) * y - x]


def vdp_sub(t, X, N):
    x, y = X
    return [y, MU * float(N(np.array([[x, y]]))[0]) - x]


# --- bi-substrate Michaelis-Menten -----------------------------------------
MM = dict(vmax=1.0, ka=0.5, kb=1.0)


def mm_nl(P):                      # v(A,B) = vmax A B /((Ka+A)(Kb+B))
    A, B = P[:, 0], P[:, 1]
    return MM["vmax"] * A * B / ((MM["ka"] + A) * (MM["kb"] + B))


def mm_true(t, X):
    v = float(mm_nl(np.array([list(X)]))[0])
    return [-v, -v]


def mm_sub(t, X, N):
    v = float(N(np.array([list(X)]))[0])
    return [-v, -v]


# --- pendulum (hostile: sin theta) -----------------------------------------
G_L = 1.0


def pen_nl(P):                     # N(theta) = sin theta
    return np.sin(P[:, 0])


def pen_true(t, X):
    th, om = X
    return [om, -G_L * np.sin(th)]


def pen_sub(t, X, N):
    th, om = X
    return [om, -G_L * float(N(np.array([[th]]))[0])]


def pen_inv(X):
    return 0.5 * X[1] ** 2 + G_L * (1.0 - np.cos(X[0]))


SYSTEMS = {
    "lotka_volterra": dict(
        nvars=2, dim=2, T=20.0, rhs=lv_true, sub=lv_sub, nl=lv_nl,
        inv=lv_inv, inv_name="d x - c ln x + b y - a ln y",
        ics=[(1.0, 1.0), (2.0, 1.0), (3.0, 1.0), (1.5, 2.0), (4.0, 2.0)],
        desc="dx=ax-bxy, dy=-cy+dxy; nonlinearity = xy"),
    "van_der_pol": dict(
        nvars=2, dim=2, T=20.0, rhs=vdp_true, sub=vdp_sub, nl=vdp_nl,
        inv=None, inv_name=None,
        ics=[(2.0, 0.0), (0.5, 0.5), (-1.0, 2.0), (1.0, -1.0), (0.1, 0.1)],
        desc="dx=y, dy=mu(1-x^2)y-x; nonlinearity = (1-x^2)y"),
    "michaelis_menten": dict(
        nvars=2, dim=2, T=6.0, rhs=mm_true, sub=mm_sub, nl=mm_nl,
        inv=None, inv_name=None,
        ics=[(3.0, 3.0), (2.0, 3.0), (3.0, 1.5), (1.0, 2.0), (2.5, 2.5)],
        desc="dA=dB=-vmax AB/((Ka+A)(Kb+B)); nonlinearity = a ratio"),
    "pendulum": dict(
        nvars=1, dim=2, T=20.0, rhs=pen_true, sub=pen_sub, nl=pen_nl,
        inv=pen_inv, inv_name="0.5 om^2 + (g/L)(1-cos th)",
        ics=[(0.5, 0.0), (1.0, 0.0), (2.0, 0.0), (2.8, 0.0), (0.0, 1.5)],
        desc="dth=om, dom=-(g/L) sin th; nonlinearity = sin th (HOSTILE)"),
}


def nl_args(name, Xtraj):
    """Columns of the state trajectory that feed the nonlinear term."""
    if name == "pendulum":
        return Xtraj[[0], :].T          # theta only
    return Xtraj[:2, :].T               # both states
