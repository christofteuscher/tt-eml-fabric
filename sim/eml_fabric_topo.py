"""
EML Fabric: layered multi-topology core
=======================================

Generalises `eml_fabric_sim.AnalogEMLTree` in three ways, without changing
the analog cell model at all (same AnalogConfig, same non-idealities, same
rails, so results remain comparable with the depth-1..4 tree data in
RESULTS.md):

  1. TOPOLOGY. Connectivity is a per-layer gather table instead of a
     hardwired heap index, so the same code runs

       tree  -- full binary tree, fan-in 1 per input path, no sharing
                (bit-identical to the original AnalogEMLTree)
       dag   -- constant-width layers, every cell may draw from every cell
                in the layer below: subexpressions are shared, so cell
                count is linear in depth instead of exponential
       mesh  -- constant-width layers with a local connection window
                (nearest-neighbour tile routing), i.e. dag + locality mask

  2. SCALE. Cells are evaluated a LAYER at a time (vectorised over cells)
     rather than one at a time in a Python loop. Depth 10 is 10 gather+
     matmul steps instead of 1023 sequential tensor ops.

  3. TRAINABILITY. A near-identity initialisation, which is what makes
     depth > 4 trainable at all. See `init_scheme='identity'` below.

Unity-gain ("averaging") initialisation
--------------------------------------
An EML cell computes out = exp(u) - ln(v) with

    u = a_u + b_u x + sum_f gu_f c_f
    v = a_v + b_v x + sum_f gv_f c_f

Linearising about a_u = u0, a_v = A, with e0 = exp(u0):

    exp(u) ~= e0 (1 + sum_f gu_f c_f)
    -ln(v) ~= -ln A - sum_f (gv_f / A) c_f

so the constant term is e0 - ln A, which vanishes for

    A = exp(e0),

and the first-order gain from child f is e0*gu_f on the exp path and
-gv_f/A on the ln path. Asking each cell to be a unity-gain average of its
children, i.e. total gain 1 split evenly over the 2F child connections,
fixes

    gu_f = w / e0,      gv_f = -w * A,       w = 1 / (2F).

A stack of such cells is a pass-through with bounded gain rather than an
exp-of-exp-of-exp tower, which is what makes depth > 4 trainable at all.

Two details matter and were got wrong in the first attempt:

  * u0 must not be so negative that the exp path is dead. At u0 = -12,
    d/du exp(u) = 6e-6 and half of every cell's parameters receive no
    gradient. u0 = -2 gives e0 = 0.135, small enough that the cell is
    dominated by the well-conditioned ln path but large enough that the
    exp path still trains.
  * BOTH children must be driven. Routing only the ln path leaves a binary
    tree connected along a single root-to-leaf spine, so a depth-10 tree
    has 10 live cells and 1013 dead ones. Splitting the gain across both
    paths keeps the whole fabric live.

`init_readout_lstsq` then solves the output stage in closed form against
the target, so training starts from the best linear readout of the
fabric's initial features instead of from ro_w = e_0, ro_b = 0.
"""

from dataclasses import dataclass
import math

import torch
import torch.nn as nn

from eml_fabric_sim import AnalogConfig, REAL_DTYPE  # noqa: F401  (re-export)


# ---------------------------------------------------------------------------
# Connectivity
# ---------------------------------------------------------------------------

@dataclass
class FabricSpec:
    """Describes the cell arrangement, independent of the analog model.

    topology : 'tree' | 'dag' | 'mesh'
    depth    : number of cell layers (layer 0 = output layer)
    width    : cells per layer for 'dag'/'mesh' (ignored for 'tree')
    window   : local fan-in for 'mesh' (odd; 3 = self + two neighbours)
    """
    topology: str = "tree"
    depth: int = 3
    width: int = 4
    window: int = 3
    n_vars: int = 1        # number of external input variables x1..xn

    def layer_sizes(self):
        if self.topology == "tree":
            return [2 ** l for l in range(self.depth)]
        return [self.width] * self.depth

    def n_cells(self):
        return sum(self.layer_sizes())

    def conn_index(self, l):
        """LongTensor (n_l, 2, F) of layer-(l+1) indices feeding layer l.

        Path 0 is the exp/u input, path 1 is the ln/v input.
        Returns None for the deepest layer (no children).
        """
        sizes = self.layer_sizes()
        if l >= self.depth - 1:
            return None
        n_l, n_c = sizes[l], sizes[l + 1]

        if self.topology == "tree":
            # heap children, expressed layer-locally: cell j -> 2j, 2j+1
            j = torch.arange(n_l)
            idx = torch.stack([2 * j, 2 * j + 1], dim=1)      # (n_l, 2)
            return idx.unsqueeze(-1)                           # F = 1

        if self.topology == "dag":
            # every cell may draw from every child; F = n_c
            idx = torch.arange(n_c).view(1, 1, n_c)
            return idx.expand(n_l, 2, n_c).contiguous()

        if self.topology == "mesh":
            # local window, wrapped: cell j sees children j-w/2 .. j+w/2
            w = self.window
            off = torch.arange(w) - w // 2
            # map cell j onto the child ring proportionally (widths are equal
            # here, but this keeps it correct if they ever differ)
            centre = (torch.arange(n_l) * n_c) // n_l
            idx = (centre.view(n_l, 1) + off.view(1, w)) % n_c
            return idx.unsqueeze(1).expand(n_l, 2, w).contiguous()

        raise ValueError(f"unknown topology {self.topology!r}")


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class AnalogEMLFabric(nn.Module):
    """Layered analog EML fabric with pluggable topology.

    Parameters per layer l:
        alpha[l] : (n_l, 2)        constant term of each input path
        beta[l]  : (n_l, 2)        coefficient on the external input x
        gamma[l] : (n_l, 2, F_l)   coefficients on the selected children

    Readout: out = sum_i ro_w[i] * layer0[i] + ro_b
    """

    def __init__(self, spec: FabricSpec, acfg: AnalogConfig, seed=0,
                 init_scheme="identity", init_scale=0.7, id_noise=0.05,
                 div=0.35, u0=-2.0, u0_spread=0.7, dtype=REAL_DTYPE,
                 var_mode="dense", var_assign=None):
        super().__init__()
        self.spec = spec
        self.acfg = acfg
        self._pen = torch.zeros((), dtype=dtype)
        self.dtype = dtype
        self.temp_delta = acfg.temp_delta
        self.sizes = spec.layer_sizes()
        self.n_cells = spec.n_cells()
        self.depth = spec.depth
        self.n_vars = spec.n_vars
        self.var_mode = var_mode        # 'dense' | 'soft' | 'fixed'
        self.n_rails = self.n_vars + 1  # rail 0 is the constant 1
        self.tau = 1.0                  # softmax temperature for 'soft'
        if var_mode not in ("dense", "soft", "fixed"):
            raise ValueError(f"unknown var_mode {var_mode!r}")

        g = torch.Generator().manual_seed(seed)

        alphas, betas, gammas = [], [], []
        for l in range(spec.depth):
            n_l = self.sizes[l]
            ci = spec.conn_index(l)
            F = 0 if ci is None else ci.shape[-1]
            if ci is not None:
                self.register_buffer(f"conn_{l}", ci)

            a = torch.zeros(n_l, 2, dtype=dtype)
            # 'dense' with n_vars > 1 gives every input path a coefficient on
            # every variable (the assignment is *learned*, and L1 sparsifies
            # it); 'soft'/'fixed' keep one scalar gain per path and select
            # which rail it multiplies (the assignment is *searched*).
            if self.var_mode == "dense" and self.n_vars > 1:
                b = torch.zeros(n_l, 2, self.n_vars, dtype=dtype)
            else:
                b = torch.zeros(n_l, 2, dtype=dtype)
            gm = torch.zeros(n_l, 2, max(F, 1), dtype=dtype)

            if init_scheme == "standard":
                # matches the original AnalogEMLTree init
                a.normal_(0, init_scale, generator=g)
                b.normal_(0, init_scale, generator=g)
                gm.normal_(0, init_scale, generator=g)
                a[:, 1] += 1.5
            elif init_scheme == "identity":
                eps = id_noise
                rn = lambda *s: torch.randn(*s, generator=g, dtype=dtype)
                beta0 = 1.0 / max(spec.depth, 1)

                # Per-cell operating point. A single shared u0 makes every
                # cell in a layer compute the SAME shape, and correlation is
                # scale-invariant, so multiplicative jitter cannot decorrelate
                # them: layer-0 features stay collinear at |corr| = 0.9997 and
                # extra width buys nothing. Spreading u0 across cells varies
                # e0 = exp(u0) over roughly an order of magnitude, which moves
                # each cell to a different point on the exp nonlinearity and
                # makes the outputs genuinely different functions of x.
                u0_i = u0 + rn(n_l) * u0_spread                # (n_l,)
                e0_i = torch.exp(u0_i)
                A_i = torch.exp(e0_i)      # kills the constant term per cell

                # Hardware-aware operating point.  The log amp actually
                # sees atten_v * v + s, so (i) the smallest realisable ln
                # argument is s, not 0, and (ii) the v needed to present
                # A_i is (A_i - s)/atten_v.  If A_i < s the constant term
                # e0 - ln(A) cannot be cancelled at this u0 at all, so the
                # operating point is raised to the lowest one that can be:
                # e0 = ln(s).  With ideal defaults (s = 0, atten_v = 1)
                # every line below is an exact no-op.
                amin = acfg.ln_pedestal + acfg.atten_v * 1e-3
                if float(A_i.min()) < amin:
                    A_i = torch.clamp(A_i, min=amin)
                    e0_i = torch.log(A_i)
                    u0_i = torch.log(e0_i)
                vgain = 1.0 / acfg.atten_v

                a[:, 0] = u0_i
                a[:, 1] = (A_i - acfg.ln_pedestal) * vgain
                # x enters both paths with a per-cell random gain. With
                # several variables the per-variable drive is divided by
                # n_vars so the total input drive per path is unchanged.
                if b.dim() == 2:
                    b[:, 0] = rn(n_l) * beta0 * div
                    b[:, 1] = beta0 * (1.0 + rn(n_l) * div) * vgain
                else:
                    nv = self.n_vars
                    b[:, 0, :] = rn(n_l, nv) * beta0 * div / nv
                    b[:, 1, :] = (beta0 / nv) * (1.0 + rn(n_l, nv) * div) \
                        * vgain
                if F > 0:
                    # unity total gain, split evenly over both paths and all
                    # F connections, so no child and no path is left dead
                    w = 1.0 / (2.0 * F)
                    gm[:, 0, :] = (w / e0_i).unsqueeze(-1)     # exp path
                    # ln path: the realised small-signal gain is
                    # -atten_v * gv / (atten_v v + s) = -atten_v gv / A,
                    # so the commanded gain carries the 1/atten_v back out
                    gm[:, 1, :] = (-w * A_i * vgain).unsqueeze(-1)
                    gm *= (1.0 + rn(*gm.shape) * div)
                    gm += rn(*gm.shape) * eps * gm.abs().mean().clamp(min=1e-3)
                else:
                    # deepest layer has no children: x is the only drive, so
                    # give it the full per-cell gain rather than beta0
                    if b.dim() == 2:
                        b[:, 1] = (1.0 + rn(n_l) * div) * vgain
                    else:
                        b[:, 1, :] = (1.0 + rn(n_l, self.n_vars) * div) \
                            * vgain / self.n_vars
                a += rn(*a.shape) * eps
            else:
                raise ValueError(f"unknown init_scheme {init_scheme!r}")

            alphas.append(nn.Parameter(a))
            betas.append(nn.Parameter(b))
            gammas.append(nn.Parameter(gm))

        self.alpha = nn.ParameterList(alphas)
        self.beta = nn.ParameterList(betas)
        self.gamma = nn.ParameterList(gammas)

        # -- leaf-to-variable assignment ------------------------------------
        if self.var_mode == "fixed":
            # a hard, searchable assignment: cell path (l, i, k) reads rail
            # sel[l][i, k] out of [1, x1..xn].
            for l in range(spec.depth):
                sel = torch.randint(0, self.n_rails, (self.sizes[l], 2),
                                    generator=g)
                self.register_buffer(f"sel_{l}", sel)
            if var_assign is not None:
                self.set_assignment(var_assign)
        elif self.var_mode == "soft":
            # a learned assignment: per-path logits over the rails,
            # discretised in the forward pass with a straight-through
            # estimator, so training and evaluation see the same one-hot.
            logits = []
            for l in range(spec.depth):
                lg = torch.randn(self.sizes[l], 2, self.n_rails,
                                 generator=g, dtype=dtype) * 0.1
                logits.append(nn.Parameter(lg))
            self.sel_logit = nn.ParameterList(logits)

        ro_w = torch.zeros(self.sizes[0], dtype=dtype)
        ro_w[0] = 1.0
        self.ro_w = nn.Parameter(ro_w)
        self.ro_b = nn.Parameter(torch.zeros(1, dtype=dtype))

        # static mismatch, drawn once per chip instance
        gmm = torch.Generator().manual_seed(acfg.mismatch_seed)
        for l in range(spec.depth):
            n_l = self.sizes[l]
            for nm, std in (("mm_exp_gain", acfg.mismatch_gain_std),
                            ("mm_ln_gain", acfg.mismatch_gain_std),
                            ("mm_exp_off", acfg.mismatch_offset_std),
                            ("mm_ln_off", acfg.mismatch_offset_std)):
                self.register_buffer(
                    f"{nm}_{l}",
                    torch.randn(n_l, generator=gmm, dtype=dtype) * std)

    # -- multivariate input plumbing ----------------------------------------

    def _prep_x(self, x):
        """Accept (B,) for a scalar fabric or (B, n_vars); return
        (n_vars, B).  The scalar case is bit-identical to the old path."""
        if x.dim() == 1:
            if self.n_vars != 1:
                raise ValueError(
                    f"fabric has n_vars={self.n_vars}, got a 1-D input; "
                    f"pass x of shape (B, {self.n_vars})")
            return x.view(1, -1)
        if x.dim() != 2 or x.shape[1] != self.n_vars:
            raise ValueError(f"expected x of shape (B, {self.n_vars}), "
                             f"got {tuple(x.shape)}")
        return x.transpose(0, 1).contiguous()

    def _rails(self, X):
        """[1, x1..xn] as (n_rails, B): the constant is a selectable leaf."""
        one = torch.ones(1, X.shape[1], dtype=X.dtype)
        return torch.cat([one, X], dim=0)

    def _sel_weights(self, l):
        """(n_l, 2, n_rails) one-hot rail selector for layer l."""
        if self.var_mode == "fixed":
            sel = getattr(self, f"sel_{l}")
            return torch.nn.functional.one_hot(
                sel, self.n_rails).to(self.dtype)
        p = torch.softmax(self.sel_logit[l] / self.tau, dim=-1)
        hard = torch.nn.functional.one_hot(
            p.argmax(dim=-1), self.n_rails).to(p.dtype)
        return hard + p - p.detach()        # straight-through

    def _drive(self, l, X, quant):
        """alpha + input-path drive for layer l: (n_l, 2, B)."""
        a = self.alpha[l]
        b = self.beta[l]
        if quant:
            a, b = self._quant(a), self._quant(b)
        a = a.unsqueeze(-1)
        if self.var_mode == "dense":
            if self.n_vars == 1:
                return a + b.unsqueeze(-1) * X.view(1, 1, -1)   # legacy path
            return a + torch.einsum("pkv,vb->pkb", b, X)
        w = self._sel_weights(l)                        # (n_l, 2, n_rails)
        r = self._rails(X)                              # (n_rails, B)
        return a + b.unsqueeze(-1) * torch.einsum("pkr,rb->pkb", w, r)

    @torch.no_grad()
    def assignment(self):
        """Current leaf-to-variable assignment as a list of (n_l, 2) index
        tensors, rail 0 = constant 1, rail v = x_v.  None for 'dense'."""
        if self.var_mode == "dense":
            return None
        if self.var_mode == "fixed":
            return [getattr(self, f"sel_{l}").clone()
                    for l in range(self.depth)]
        return [lg.argmax(dim=-1).clone() for lg in self.sel_logit]

    @torch.no_grad()
    def set_assignment(self, assign):
        for l, s in enumerate(assign):
            getattr(self, f"sel_{l}").copy_(torch.as_tensor(s))
        return self

    def affine_params(self):
        return list(self.alpha) + list(self.beta) + list(self.gamma)

    @torch.no_grad()
    def init_readout_lstsq(self, x, t, ridge=1e-6, wmax=1e3):
        """Solve the output stage in closed form: ridge-regularised fit of
        the layer-0 cell outputs (plus a constant) to the target, so
        training starts from the best linear readout of the initial
        features instead of from an arbitrary ro_w = e_0, ro_b = 0.

        The ridge term is not cosmetic. Layer-0 features in a
        constant-width fabric are strongly collinear, so plain lstsq
        returns huge cancelling coefficients: it fits the training set at
        init and then explodes the moment mismatch, noise or weight
        quantisation perturbs the features it was balanced against."""
        feats = self._layer0(x)                       # (n_0, B)
        F = torch.cat([feats.T, torch.ones(feats.shape[1], 1,
                                           dtype=feats.dtype)], dim=1)
        good = torch.isfinite(F).all(dim=1) & torch.isfinite(t)
        if int(good.sum()) < F.shape[1]:
            return self
        Fg, tg = F[good], t[good].unsqueeze(1)
        G = Fg.T @ Fg
        lam = ridge * float(torch.diagonal(G).mean().clamp(min=1e-30))
        G = G + lam * torch.eye(G.shape[0], dtype=G.dtype)
        try:
            sol = torch.linalg.solve(G, Fg.T @ tg)[:, 0]
        except Exception:
            return self
        if torch.isfinite(sol).all() and float(sol.abs().max()) < wmax:
            self.ro_w.copy_(sol[:-1])
            self.ro_b.copy_(sol[-1:])
        return self

    @torch.no_grad()
    def _layer0(self, x):
        X = self._prep_x(x)
        child = None
        for l in reversed(range(self.depth)):
            uv = self._drive(l, X, quant=False)
            if child is not None:
                ci = getattr(self, f"conn_{l}")
                uv = uv + (self.gamma[l].unsqueeze(-1) * child[ci]).sum(dim=2)
            child = self._cells(uv[:, 0], uv[:, 1], l, noisy=False)
        return child

    # -- non-ideality primitives (identical semantics to AnalogEMLTree) ------

    def _quant(self, w):
        bits = self.acfg.weight_bits
        if bits <= 0:
            return w
        r = self.acfg.weight_range
        step = 2.0 * r / (2 ** bits - 1)
        wq = torch.round(torch.clamp(w, -r, r) / step) * step
        return w + (wq - w).detach()

    def _leaky_max(self, x, hi, cap=5.0):
        k = self.acfg.rail_leak
        return torch.clamp(x, max=hi) + torch.clamp(k * (x - hi), 0.0, cap)

    def _leaky_clamp(self, x, lim):
        k = self.acfg.rail_leak
        return (torch.clamp(x, -lim, lim)
                + torch.clamp(k * (x - lim), 0.0, lim)
                - torch.clamp(k * (-lim - x), 0.0, lim))

    def _leaky_min(self, x, lo):
        return -self._leaky_max(-x, -lo)

    def _span_rail(self, x):
        """Effect (c): confine a current-domain signal to the representable
        window [span_lo, span_hi].  Off unless span_decades > 0."""
        a = self.acfg
        if getattr(self, "_probe", None) is not None:
            d = x.detach().abs()
            self._probe.append((float(d.min()), float(d.max())))
        lo = a.span_lo()
        if lo is None:
            return x
        hi = a.span_hi_eff()
        if a.span_penalty > 0:
            xs = torch.clamp(x, min=lo * 1e-9)
            self._pen = self._pen + a.span_penalty * (
                torch.relu(torch.log10(xs / hi)).mean()
                + torch.relu(torch.log10(lo / xs)).mean())
        return self._leaky_min(self._leaky_max(x, hi), lo)

    def _ln_railed(self, x):
        """Effects (b) then (a): ln(atten_v * v + s).  See AnalogConfig."""
        a = self.acfg
        if a.atten_v != 1.0:
            x = a.atten_v * x
        if a.ln_pedestal != 0.0:
            x = x + a.ln_pedestal
        x = self._span_rail(x)
        lo = a.span_lo()
        floor = a.ln_floor if lo is None else max(a.ln_floor, lo)
        l = torch.log(torch.clamp(x, min=floor))
        return l + torch.clamp(a.rail_leak * (x - floor), -5.0, 0.0)

    def _cells(self, u, v, l, noisy):
        """Vectorised layer of analog EML cells. u, v: (n_l, B)."""
        a = self.acfg
        t = 1.0 + self.temp_delta
        eg = getattr(self, f"mm_exp_gain_{l}").unsqueeze(-1)
        lg = getattr(self, f"mm_ln_gain_{l}").unsqueeze(-1)
        eo = getattr(self, f"mm_exp_off_{l}").unsqueeze(-1)
        lo = getattr(self, f"mm_ln_off_{l}").unsqueeze(-1)
        u2 = (1.0 + eg) * u + eo
        v2 = (1.0 + lg) * v + lo
        e = torch.exp(self._leaky_max(u2 / t, math.log(a.exp_cap())))
        e = self._span_rail(e)
        ln = t * self._ln_railed(v2)
        out = self._leaky_clamp(e - ln, a.sat)
        if noisy and a.noise_std > 0:
            out = out + torch.randn_like(out) * a.noise_std
        return out

    # -- forward -------------------------------------------------------------

    def forward(self, x, noisy=True):
        """x: (B,) or (B, n_vars) -> (B,). Layers evaluated deepest-first."""
        self._pen = torch.zeros((), dtype=self.dtype)
        X = self._prep_x(x)                     # (n_vars, B)
        child = None                            # outputs of layer l+1
        for l in reversed(range(self.depth)):
            n_l = self.sizes[l]
            uv = self._drive(l, X, quant=True)                # (n_l, 2, B)
            if child is not None:
                gm = self._quant(self.gamma[l])              # (n_l, 2, F)
                ci = getattr(self, f"conn_{l}")              # (n_l, 2, F)
                picked = child[ci]                           # (n_l, 2, F, B)
                uv = uv + (gm.unsqueeze(-1) * picked).sum(dim=2)
            child = self._cells(uv[:, 0], uv[:, 1], l, noisy)  # (n_l, B)
        return (self.ro_w.unsqueeze(-1) * child).sum(0) + self.ro_b

    # -- diagnostics ----------------------------------------------------------

    @torch.no_grad()
    def layer_stats(self, x):
        """Per-layer output RMS, for checking signal scaling at init."""
        X = self._prep_x(x)
        child, stats = None, {}
        for l in reversed(range(self.depth)):
            uv = self._drive(l, X, quant=False)
            if child is not None:
                gm = self.gamma[l]
                ci = getattr(self, f"conn_{l}")
                uv = uv + (gm.unsqueeze(-1) * child[ci]).sum(dim=2)
            child = self._cells(uv[:, 0], uv[:, 1], l, noisy=False)
            stats[l] = float(torch.sqrt(torch.mean(child ** 2)))
        return stats

    def n_params(self):
        return sum(p.numel() for p in self.parameters())

    @torch.no_grad()
    def measured_hop_gain_v(self, v0=1.0, eps=1e-6):
        """Realised per-hop small-signal gain of the v (ln) port, i.e.
        |d out / d v| at operating point v0, with the pedestal and the
        v-port attenuation as configured.  For the ideal cell this is
        1/v0; the silicon cell gives atten_v / (atten_v v0 + s)."""
        a = self.acfg
        f = lambda z: -self._ln_railed(torch.as_tensor(
            [z], dtype=self.dtype))[0]
        return abs(float((f(v0 + eps) - f(v0 - eps)) / (2 * eps)))


# ---------------------------------------------------------------------------
# Leaf-to-variable assignment search (var_mode='fixed')
# ---------------------------------------------------------------------------

def search_assignments(spec, acfg, x, t, n_probe=16, probe_iters=200,
                       seed=0, tcfg=None, model_kw=None, train_fn=None,
                       eval_fn=None):
    """Random search over hard leaf-to-variable assignments.

    Draws `n_probe` candidate fabrics (each with its own random assignment
    but the same analog chip), trains each for `probe_iters`, and returns
    (best_model, best_rmse, [all probe rmses]).  The winner is NOT
    retrained here -- do that with the returned model and a full TrainConfig.
    """
    from eml_fabric_sim import TrainConfig, train as _train, evaluate as _ev
    train_fn = train_fn or _train
    eval_fn = eval_fn or _ev
    tcfg = tcfg or TrainConfig(iters=probe_iters)
    model_kw = dict(model_kw or {})
    model_kw.setdefault("init_scheme", "identity")

    best, best_r, scores = None, float("inf"), []
    for p in range(n_probe):
        m = AnalogEMLFabric(spec, acfg, seed=seed * 1000 + p,
                            var_mode="fixed", **model_kw)
        m.init_readout_lstsq(x, t)
        train_fn(m, x, t, tcfg)
        r, _ = eval_fn(m, x, t)
        scores.append(r)
        if r < best_r:
            best, best_r = m, r
    return best, best_r, scores
