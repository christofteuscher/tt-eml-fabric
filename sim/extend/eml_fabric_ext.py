"""
EML fabric with a THIRD, current-summed input port (the "w port").

Standard cell (shipped silicon, eml_cell_v3b.inc):

    out = exp(u) - ln(v + s)

with u, v each an affine combination of x and of child-cell outputs.  In the
netlist the two paths meet at node `out` as CURRENTS: `VSPM mpo out 0` brings
the exp-path pmos mirror leg in, `VSNM out mno 0` brings the ln-path nmos
mirror leg in, and `XLO3 out pbias ...` is a fixed bias leg.  Node `out` is
therefore already a KCL summing node.

Extended cell:

    out = exp(u) - ln(v + s) + w,     w = alpha_w + beta_w . x + gamma_w . children

The w port is one more mirror leg dropped on that same node.  It costs a
weight MDAC + a mirror leg + routing; it does NOT cost a translinear path
(no npn transdiode, no servo OTA, no `chainglue` pedestal conversion), which
is what the u and v ports each need.

Everything else -- AnalogConfig, the rails, the mismatch draws, the pedestal,
the identity init -- is inherited unchanged from AnalogEMLFabric so results
stay comparable with RESULTS.md / RESULTS_SCALING.md.

MODELLING NOTE (important when reading the numbers): the w port is modelled
as UNATTENUATED (hop gain = gamma_w exactly), while the u/v ports carry the
pedestal's realised hop gain.  That is the physical claim being tested -- a
current summed into a mirror is not squeezed through ln(v+s) -- but it means
the w port's advantage here is a *structural* one that the sim's continuous
weights can partly fake for u/v as well (gamma is unquantised in ladder A).
On the die, where gamma is a 4-bit+sign MDAC and the v-port link attenuates
6.2x per stage, the gap would be larger, not smaller.
"""
import math
import sys
import os

import torch
import torch.nn as nn

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eml_fabric_sim import AnalogConfig, REAL_DTYPE          # noqa: E402
from eml_fabric_topo import AnalogEMLFabric, FabricSpec      # noqa: E402


class AnalogEMLFabricW(AnalogEMLFabric):
    """AnalogEMLFabric + a third summed-current input port per cell.

    Parameters per layer l (P = 3 instead of 2):
        alpha[l] : (n_l, 3)
        beta[l]  : (n_l, 3) or (n_l, 3, n_vars)
        gamma[l] : (n_l, 3, F_l)
    Path 0 = exp/u, path 1 = ln/v, path 2 = w (summed at the output node).
    """

    N_PATH = 3

    def __init__(self, spec, acfg, seed=0, w_share=1.0 / 3.0, **kw):
        # build the standard 2-path fabric first (identical draws / mismatch)
        super().__init__(spec, acfg, seed=seed, **kw)
        self.w_share = w_share
        g = torch.Generator().manual_seed(seed + 77_000)
        div = kw.get("div", 0.35)
        eps = kw.get("id_noise", 0.05)
        rn = lambda *s: torch.randn(*s, generator=g, dtype=self.dtype)

        # Re-pack alpha/beta/gamma with a third path, and rescale the two
        # existing paths so the TOTAL unity gain is still 1 (split over 3
        # paths, not 2).  Without the rescale the extended fabric would
        # simply have 1.5x the loop gain at init, which is not the effect
        # under test.
        new_a, new_b, new_gm = [], [], []
        for l in range(self.depth):
            n_l = self.sizes[l]
            a, b, gm = self.alpha[l].data, self.beta[l].data, self.gamma[l].data
            F = gm.shape[-1]
            has_child = (l < self.depth - 1)

            a3 = torch.zeros(n_l, 3, dtype=self.dtype)
            a3[:, :2] = a
            a3[:, 2] = rn(n_l) * eps                # w constant ~ 0

            if b.dim() == 2:
                b3 = torch.zeros(n_l, 3, dtype=self.dtype)
                b3[:, :2] = b
            else:
                b3 = torch.zeros(n_l, 3, b.shape[-1], dtype=self.dtype)
                b3[:, :2] = b

            gm3 = torch.zeros(n_l, 3, F, dtype=self.dtype)
            gm3[:, :2] = gm

            if has_child:
                # 2/3 of the original loop gain stays on exp+ln, 1/3 goes to w.
                scale = (1.0 - w_share) if w_share < 1.0 else 2.0 / 3.0
                gm3[:, :2] *= scale
                wg = w_share / F                    # hop gain of the w port IS gamma
                gm3[:, 2, :] = wg
                gm3[:, 2, :] *= (1.0 + rn(n_l, F) * div)
                gm3[:, 2, :] += rn(n_l, F) * eps * abs(wg)
            else:
                # deepest layer: x is the only drive; give w a small share too
                beta0 = 1.0 / max(self.depth, 1)
                if b3.dim() == 2:
                    b3[:, 2] = w_share * beta0 * (1.0 + rn(n_l) * div)
                else:
                    nv = b3.shape[-1]
                    b3[:, 2, :] = (w_share * beta0 / nv) * (
                        1.0 + rn(n_l, nv) * div)

            new_a.append(nn.Parameter(a3))
            new_b.append(nn.Parameter(b3))
            new_gm.append(nn.Parameter(gm3))

        self.alpha = nn.ParameterList(new_a)
        self.beta = nn.ParameterList(new_b)
        self.gamma = nn.ParameterList(new_gm)

        if self.var_mode == "soft":
            logits = []
            for l in range(self.depth):
                lg = torch.randn(self.sizes[l], 3, self.n_rails,
                                 generator=g, dtype=self.dtype) * 0.1
                logits.append(nn.Parameter(lg))
            self.sel_logit = nn.ParameterList(logits)
        elif self.var_mode == "fixed":
            for l in range(self.depth):
                sel = torch.randint(0, self.n_rails, (self.sizes[l], 3),
                                    generator=g)
                self.register_buffer(f"sel_{l}", sel, persistent=True)

    # -- connectivity: replicate the 2-path table onto 3 paths ---------------
    def _conn3(self, l):
        ci = getattr(self, f"conn_{l}")          # (n_l, 2, F)
        return torch.cat([ci, ci[:, :1]], dim=1)  # (n_l, 3, F)

    def _apply(self, uvw, l, noisy):
        """uvw: (n_l, 3, B) -> cell outputs (n_l, B)."""
        out = self._cells(uvw[:, 0], uvw[:, 1], l, noisy=False)
        out = out + uvw[:, 2]                     # KCL at the output node
        out = self._leaky_clamp(out, self.acfg.sat)
        if noisy and self.acfg.noise_std > 0:
            out = out + torch.randn_like(out) * self.acfg.noise_std
        return out

    def forward(self, x, noisy=True):
        self._pen = torch.zeros((), dtype=self.dtype)
        X = self._prep_x(x)
        child = None
        for l in reversed(range(self.depth)):
            uvw = self._drive(l, X, quant=True)             # (n_l, 3, B)
            if child is not None:
                gm = self._quant(self.gamma[l])
                ci = self._conn3(l)
                uvw = uvw + (gm.unsqueeze(-1) * child[ci]).sum(dim=2)
            child = self._apply(uvw, l, noisy)
        return (self.ro_w.unsqueeze(-1) * child).sum(0) + self.ro_b

    @torch.no_grad()
    def _layer0(self, x):
        X = self._prep_x(x)
        child = None
        for l in reversed(range(self.depth)):
            uvw = self._drive(l, X, quant=False)
            if child is not None:
                ci = self._conn3(l)
                uvw = uvw + (self.gamma[l].unsqueeze(-1) * child[ci]).sum(dim=2)
            child = self._apply(uvw, l, noisy=False)
        return child


# ---------------------------------------------------------------------------
# extra target: additive structure the log-domain grammar has to pay for
# ---------------------------------------------------------------------------

def make_expdiff(n_train=384, n_test=384, seed=1234, lo=0.2, hi=1.8):
    """y = exp(x1) - exp(x2).  Trivial for a cell WITH a summing port
    (two depth-1 cells + KCL); the standard grammar must build the
    subtraction out of ln/exp round trips."""
    g = torch.Generator().manual_seed(seed)

    def draw(n):
        c = [torch.empty(n, dtype=REAL_DTYPE).uniform_(lo, hi, generator=g)
             for _ in range(2)]
        return torch.stack(c, dim=1)

    xt, xv = draw(n_train), draw(n_test)
    f = lambda X: torch.exp(X[:, 0]) - torch.exp(X[:, 1])
    tt, tv = f(xt), f(xv)
    s = float(torch.sqrt(torch.mean(tt ** 2)))
    return xt, tt / s, xv, tv / s, s, "nrmse"
