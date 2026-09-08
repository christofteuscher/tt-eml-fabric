"""
EML Fabric Analog-Non-Ideality Simulator
=========================================

Software model of a reconfigurable analog EML fabric (TLAB-TR-2026-007):
a full binary tree of identical cells computing eml(u, v) = exp(u) - ln(v),
where each cell input is a learnable affine combination

    u_i = alpha + beta * x + gamma * child_output        (report eq. 2)

This module deliberately differs from the upstream PyTorch trainer
(tree_prototype_torch_v16_final.py) in three ways that reflect *hardware*
rather than *math*:

  1. REAL-valued signals (an analog circuit has no complex plane).
     The ln input is clamped to a positive floor, as a log-amp would rail.
  2. Continuous affine weights (the programmable alpha/beta/gamma of the
     fabric) instead of softmax symbol selection -- calibration curves
     contain real constants, so 0/1 snapping cannot represent them.
  3. A non-ideality forward model: per-cell static mismatch, dynamic-range
     saturation, per-stage noise, finite weight resolution (quantization-
     aware with straight-through estimator), and global V_T temperature
     drift (translinear exp/ln both scale with absolute temperature).

With all non-idealities at their defaults the cell reduces to exact
real-domain eml(u, v).
"""

from dataclasses import dataclass, field, asdict
import math
import warnings

import torch
import torch.nn as nn

REAL_DTYPE = torch.float64


@dataclass
class AnalogConfig:
    """Non-ideality knobs. Defaults = ideal (real-domain) math."""

    # Dynamic range: |cell output| and exp() output are clamped to sat.
    sat: float = 1.0e12
    # Log-amp input floor: ln argument is clamped to >= ln_floor.
    # 1e-12 ~ a 12-decade log amp; real subthreshold parts are 6-9 decades.
    ln_floor: float = 1.0e-12
    # Additive Gaussian noise at each cell output, fresh every forward pass
    # (in-situ training sees it; hardware always has it).
    noise_std: float = 0.0
    # Static per-cell mismatch, drawn once from mismatch_seed:
    # gain errors (1+g) on the exp argument and on the ln output,
    # input-referred offsets on both paths.
    mismatch_gain_std: float = 0.0
    mismatch_offset_std: float = 0.0
    mismatch_seed: int = 0
    # Finite weight resolution: quantize alpha/beta/gamma to weight_bits
    # over [-weight_range, +weight_range]. 0 = continuous. The readout is
    # NOT quantized (it models a digital output stage after the ADC).
    weight_bits: int = 0
    weight_range: float = 8.0
    # Rail leak: fraction of slope retained beyond saturation / below the
    # ln floor. Real rails compress softly, and a strictly flat rail has
    # zero gradient, which stalls in-situ learning. 0 = hard rail.
    rail_leak: float = 0.02
    # Global V_T drift, set at EVAL time (train at 0): translinear
    # exp computes exp(u/(1+delta)), log amp output scales by (1+delta).
    temp_delta: float = 0.0

    # -- hardware-derived effects (v3b cell / FAB_ERROR).  All default OFF,
    #    so an AnalogConfig() built by older code is bit-identical. ---------
    #
    # (a) LOGARITHMIC PEDESTAL. The realised cell computes ln(v + s), not
    #     ln(v): the segmented-resistor ladder on the v port sits on a
    #     non-zero floor, so a commanded v = 0 still presents s to the log
    #     amp. In SIGNAL units (see PEDESTAL_SEGMENTS / SEGMENT_UNIT).
    ln_pedestal: float = 0.0
    # (b) PER-HOP ATTENUATION of the v port: the signal actually presented
    #     to the log amp is atten_v * v.  1.0 = lossless.  NOTE: on its own
    #     this is exactly a constant output offset (ln(a v) = ln v + ln a)
    #     and is therefore absorbed by retraining; it only bites in
    #     combination with the pedestal (ln(a v + s) is not separable) or
    #     with the finite span.  Both are modelled, so do not switch (b) on
    #     alone and conclude it is harmless.
    #
    #     *** (b) IS NOT INDEPENDENT OF (a) -- see allow_double_count. ***
    atten_v: float = 1.0
    # (c) FINITE DEVICE SPAN. Every internal signal is a current and the
    #     fabric only spans span_decades decades, from span_hi down.
    #     0 = unlimited (legacy behaviour: sat above, ln_floor below).
    span_decades: float = 0.0
    span_hi: float = 0.0          # 0 -> use sat
    # >0: instead of only clamping, accumulate a hinge penalty in decades
    #     of excursion which train() adds to the loss (TrainConfig.lam_span).
    span_penalty: float = 0.0

    # Opt-in escape hatch for the ONE combination that is not physics:
    # (a) ln_pedestal and (b) atten_v switched on together.  See the
    # DOUBLE-COUNTING note under silicon_config().  Leave False unless you
    # are deliberately computing a pessimistic stress-test bound, in which
    # case worst_case_config() sets it for you.
    allow_double_count: bool = False

    def __post_init__(self):
        # Guard rail: (b) is DERIVED from (a) (lambda_v = k/(out + s) =
        # 1.094/(1.741+2.547) = 0.2551), so enabling both models the same
        # v-port loss twice.  Measured effect: lambda_v drops from the
        # silicon's 0.2551 (pedestal alone) to 0.0933, 2.7x too small.
        # Refuse to let that happen silently.
        if (self.ln_pedestal != 0.0 and self.atten_v != 1.0
                and not self.allow_double_count):
            warnings.warn(
                "AnalogConfig: ln_pedestal (a) and atten_v (b) are both on. "
                "lambda_v = 1.094/(1.741+2.547) = 0.2551 is DERIVED from the "
                "pedestal, so this double-counts the v-port loss (realised "
                "hop gain 0.0933 vs the silicon's 0.2551). Use "
                "silicon_config() for the silicon; if you really want the "
                "pessimistic bound, use worst_case_config() or pass "
                "allow_double_count=True.",
                RuntimeWarning, stacklevel=2)

    # -- helpers -----------------------------------------------------------
    def span_lo(self):
        """Bottom of the representable current window, or None if off."""
        if self.span_decades <= 0:
            return None
        return self.span_hi_eff() * 10.0 ** (-self.span_decades)

    def span_hi_eff(self):
        return self.span_hi if self.span_hi > 0 else self.sat

    def exp_cap(self):
        """Ceiling the exp() output is railed at: the device span top when
        the span is modelled, otherwise the legacy `sat`."""
        return min(self.sat, self.span_hi_eff()) if self.span_decades > 0 \
            else self.sat


# ---------------------------------------------------------------------------
# Silicon constants (measured; see the provenance note on each).
# The fabric's signal unit is 1 unit = 0.5 uA, so all of these are already
# in the simulator's dimensionless signal units -- no basis conversion.
# ---------------------------------------------------------------------------

# (a) ln pedestal.  SEGMENTED-resistor basis (the layout draws 4 series
#     L=11.44 bodies with ~741 ohm end resistance each, +4.31 % on the
#     string), which is the truthful die basis:
#         io = 2.478 - 1.094 ln(v + 2.547)
#     paper/FAB_CORPUS.md:36, paper/FAB_NETWORKS.md:41,69.
#     The LUMPED basis used by the LVS reference netlist gives
#         2.549 - 1.145 ln(v + 2.574)
#     (silicon/cell/v3/eml_cell_v3b.inc:60, paper/CHARACTERISATION.md:47).
#     Always quote the basis.  1.05 % apart on s, 4.5 % on the slope.
PEDESTAL_SEGMENTED = 2.547     # units, die basis  <- default
PEDESTAL_LUMPED = 2.574        # units, LVS-netlist basis
LN_SLOPE_SEGMENTED = 1.094
LN_SLOPE_LUMPED = 1.145

# (b) v-port per-hop gain.  paper/FAB_ERROR.md:300 shipped fixed point
#     (MPO W=24): lambda_v = 0.2551.  Measured tangents at the two chain
#     operating points: 0.1542 and 0.2778 (FAB_ERROR.md:180-182).
ATTEN_V_NOMINAL = 0.2551
ATTEN_V_SECANT = 1.0 / 6.2     # = 0.1613, the "6.2x per stage" reading

# (c) Device span.  "2.90e-12 .. 6.83e-4 A = 5.80e-6 .. 1366 units at
#     1 unit = 0.5 uA (8.4 decades, MEASURED)" -- FAB_CORPUS.md:37,
#     FAB_NETWORKS.md:44.  log10(1366 / 5.80e-6) = 8.372.
SPAN_HI_UNITS = 1366.0
SPAN_LO_UNITS = 5.80e-6
SPAN_DECADES = math.log10(SPAN_HI_UNITS / SPAN_LO_UNITS)   # 8.372


def silicon_config(**over):
    """AnalogConfig for the MEASURED SILICON CELL (segmented basis).

    Only effect (a), the ln pedestal, is switched on.  This is the
    physically correct configuration; the other two are deliberately off:

    (b) atten_v is NOT INDEPENDENT of (a) -- it is a CONSEQUENCE of it.
        FAB_ERROR.md defines lambda_v = -k/(out + P + s/G); at the shipped
        fixed point that is

            lambda_v = k / (v + s) = 1.094 / (1.741 + 2.547) = 0.2551

        i.e. exactly ATTEN_V_NOMINAL.  The pedestal ALONE already puts the
        cell there:  AnalogEMLFabric.measured_hop_gain_v(1.741) returns
        1/(v+s) = 1/4.288 = 0.2332, and 0.2332 * k = 0.2332 * 1.094 =
        0.2551 = lambda_v (the sim carries unit ln gain, so the slope k =
        LN_SLOPE_SEGMENTED is the one factor left out of the forward
        model).  Switching atten_v on as well applies the same loss twice:
        the hop gain falls to 0.0853, i.e. lambda_v = 0.0933, 2.7x smaller
        than the silicon's.  Every number produced that way is pessimistic
        by an amount that is not a measurement.

    (c) the span does not bind at its true value: 8.372 decades is wider
        than anything these workloads use (measured over-excursion 0.00
        decades in every row of results/nonideal.json), so turning it on
        only costs runtime and adds rail leak.  Use SPAN_DECADES explicitly
        when the point of the study IS the span.

    Each effect can still be isolated for stress testing by overriding:
    silicon_config(atten_v=ATTEN_V_NOMINAL, allow_double_count=True), or
    the pre-packaged worst_case_config() below.  Anything that turns on
    (a) and (b) together without allow_double_count raises a RuntimeWarning
    from AnalogConfig.__post_init__.
    """
    base = dict(ln_pedestal=PEDESTAL_SEGMENTED)
    base.update(over)
    return AnalogConfig(**base)


def worst_case_config(**over):
    """(a)+(b)+(c) all on: a PESSIMISTIC BOUND, *not* the silicon.

    This DOUBLE-COUNTS the v-port loss (see silicon_config()): it charges
    the pedestal's own 0.2551 per-hop gain a second time as atten_v, giving
    a realised hop gain of 0.0933.  It is kept because a "nothing is
    correlated, everything is worst case" bound is a useful stress test and
    because the pinned regression cases were computed with it -- NOT
    because it describes any measured device.  Do not report it as the
    silicon result; report silicon_config() and quote this as the bound.
    """
    base = dict(ln_pedestal=PEDESTAL_SEGMENTED,
                atten_v=ATTEN_V_NOMINAL,
                span_decades=SPAN_DECADES,
                span_hi=SPAN_HI_UNITS,
                allow_double_count=True)
    base.update(over)
    return AnalogConfig(**base)


@dataclass
class TrainConfig:
    iters: int = 3000
    lr: float = 0.02
    lr_final: float = 0.002       # cosine decay endpoint
    eval_every: int = 100
    lam_l1: float = 0.0           # sparsity pressure on affine weights
    lam_span: float = 0.0         # weight on the out-of-device-span penalty
    init_scale: float = 0.7
    grad_clip: float = 1.0


class AnalogEMLTree(nn.Module):
    """Full binary tree of depth `depth`, heap-indexed (root = 0,
    children of i = 2i+1 / 2i+2). Cells at the deepest level have no
    children (child output = 0). Single external input x.

    Output = readout_gain * root + readout_offset (the output amplifier;
    absorbs physical units so internal signals can stay O(1)-ish).
    """

    def __init__(self, depth, acfg: AnalogConfig, seed=0, init_scale=0.7):
        super().__init__()
        self.depth = depth
        self.n_cells = 2 ** depth - 1
        self._pen = torch.zeros((), dtype=REAL_DTYPE)
        self.acfg = acfg
        self.temp_delta = acfg.temp_delta  # mutable at eval time

        g = torch.Generator().manual_seed(seed)
        # weights[i, j, k]: cell i, input j (0=exp path, 1=ln path),
        # k in (alpha, beta, gamma)
        w = torch.randn(self.n_cells, 2, 3, generator=g, dtype=REAL_DTYPE) * init_scale
        # bias the ln input toward a safe positive constant
        w[:, 1, 0] += 1.5
        self.weights = nn.Parameter(w)
        self.readout = nn.Parameter(torch.tensor([1.0, 0.0], dtype=REAL_DTYPE))

        # Static mismatch draws (buffers: saved with state_dict, not trained)
        gm = torch.Generator().manual_seed(acfg.mismatch_seed)
        def draw(std):
            return torch.randn(self.n_cells, generator=gm, dtype=REAL_DTYPE) * std
        self.register_buffer("mm_exp_gain", draw(acfg.mismatch_gain_std))
        self.register_buffer("mm_ln_gain", draw(acfg.mismatch_gain_std))
        self.register_buffer("mm_exp_off", draw(acfg.mismatch_offset_std))
        self.register_buffer("mm_ln_off", draw(acfg.mismatch_offset_std))

    # -- non-ideality primitives ------------------------------------------

    def _quant(self, w):
        """Quantization-aware fake-quant with straight-through gradient."""
        bits = self.acfg.weight_bits
        if bits <= 0:
            return w
        r = self.acfg.weight_range
        step = 2.0 * r / (2 ** bits - 1)
        wq = torch.round(torch.clamp(w, -r, r) / step) * step
        return w + (wq - w).detach()

    def _leaky_max(self, x, hi, cap=5.0):
        """Rail at hi with rail_leak residual slope near the rail; the
        leak itself saturates at `cap` so nothing downstream can blow up
        (a strictly flat rail has zero gradient and stalls learning)."""
        k = self.acfg.rail_leak
        return torch.clamp(x, max=hi) + torch.clamp(k * (x - hi), 0.0, cap)

    def _leaky_clamp(self, x, lim):
        """Symmetric saturating rail at +-lim with bounded leak (<= lim)."""
        k = self.acfg.rail_leak
        return (torch.clamp(x, -lim, lim)
                + torch.clamp(k * (x - lim), 0.0, lim)
                - torch.clamp(k * (-lim - x), 0.0, lim))

    def _leaky_min(self, x, lo):
        """Floor at lo with rail_leak residual slope below it."""
        k = self.acfg.rail_leak
        return -self._leaky_max(-x, -lo)

    def _span_rail(self, x):
        """Confine a current-domain signal to the representable window
        [span_lo, span_hi] (effect (c)).  Off unless span_decades > 0.
        Accrues the out-of-span hinge penalty in decades if asked."""
        a = self.acfg
        lo = a.span_lo()
        if lo is None:
            return x
        hi = a.span_hi_eff()
        if a.span_penalty > 0:
            xs = torch.clamp(x.detach() * 0 + x, min=lo * 1e-9)
            self._pen = self._pen + a.span_penalty * (
                torch.relu(torch.log10(xs / hi)).mean()
                + torch.relu(torch.log10(lo / xs)).mean())
        return self._leaky_min(self._leaky_max(x, hi), lo)

    def _ln_railed(self, x):
        """Log amp: ln(x) for x >= floor; below the floor the output rails
        at ln(floor) with a small bounded leak so gradients still point
        back into the domain.

        Effects (b) and (a) live here, in port order: the v-port signal is
        first attenuated (atten_v), then the fixed silicon pedestal is
        added, so the cell realises ln(atten_v * v + s) -- which is what
        makes the pedestal un-absorbable, since the attenuation drives the
        commanded signal down towards a floor that does not shrink with it.
        """
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

    def _cell(self, u, v, i, noisy):
        """One analog EML cell: sat(exp(u') - ln(v')) + noise."""
        a = self.acfg
        t = 1.0 + self.temp_delta
        u2 = (1.0 + self.mm_exp_gain[i]) * u + self.mm_exp_off[i]
        v2 = (1.0 + self.mm_ln_gain[i]) * v + self.mm_ln_off[i]
        # exp: argument scales as 1/V_T; rail so exp() itself stops at ~sat
        # (or at the top of the device span, whichever is in force)
        e = torch.exp(self._leaky_max(u2 / t, math.log(a.exp_cap())))
        e = self._span_rail(e)
        # ln: output scales with V_T
        l = t * self._ln_railed(v2)
        out = self._leaky_clamp(e - l, a.sat)
        if noisy and a.noise_std > 0:
            out = out + torch.randn_like(out) * a.noise_std
        return out

    # -- forward ------------------------------------------------------------

    def forward(self, x, noisy=True):
        self._pen = torch.zeros((), dtype=REAL_DTYPE)
        w = self._quant(self.weights)
        ro = self.readout  # digital output stage: full precision
        outputs = [None] * self.n_cells
        for i in reversed(range(self.n_cells)):
            lc, rc = 2 * i + 1, 2 * i + 2
            cl = outputs[lc] if lc < self.n_cells else 0.0
            cr = outputs[rc] if rc < self.n_cells else 0.0
            u = w[i, 0, 0] + w[i, 0, 1] * x + w[i, 0, 2] * cl
            v = w[i, 1, 0] + w[i, 1, 1] * x + w[i, 1, 2] * cr
            outputs[i] = self._cell(u, v, i, noisy)
        return ro[0] * outputs[0] + ro[1]

    def affine_params(self):
        """The programmable affine weights (not the readout), for L1."""
        return [self.weights]

    # -- manual programming (for verification) -------------------------------

    def program(self, weights, readout):
        """Set weights explicitly. weights: (n_cells, 2, 3) list/tensor."""
        with torch.no_grad():
            self.weights.copy_(torch.as_tensor(weights, dtype=REAL_DTYPE))
            self.readout.copy_(torch.as_tensor(readout, dtype=REAL_DTYPE))

    # -- formula readback -----------------------------------------------------

    def readback(self, chop=1e-4, simplify=True):
        """Return the configured formula as a sympy expression:
        the 'config = formula' interpretability claim, made literal."""
        import sympy as sp

        x = sp.Symbol("x")
        w = self.weights.detach().cpu().numpy()
        ro = self.readout.detach().cpu().numpy()

        def c(val):
            return sp.Float(0) if abs(val) < chop else sp.Float(float(val), 6)

        def node(i):
            if i >= self.n_cells:
                return None
            cl, cr = node(2 * i + 1), node(2 * i + 2)
            u = c(w[i, 0, 0]) + c(w[i, 0, 1]) * x
            if cl is not None:
                u = u + c(w[i, 0, 2]) * cl
            v = c(w[i, 1, 0]) + c(w[i, 1, 1]) * x
            if cr is not None:
                v = v + c(w[i, 1, 2]) * cr
            return sp.exp(u) - sp.log(v)

        expr = c(ro[0]) * node(0) + c(ro[1])
        if simplify:
            try:
                expr = sp.simplify(expr)
            except Exception:
                pass
        return expr


# ---------------------------------------------------------------------------
# Calibration targets (input x = normalized sensor reading, output O(1))
# ---------------------------------------------------------------------------

def thermistor_beta(x):
    """10k NTC beta-model. x = R/R25, returns T in Kelvin/100.
    T = 1 / (1/T25 + ln(x)/B). Exactly representable by a 3-cell EML chain."""
    B, T25 = 3435.0, 298.15
    return 1.0 / (1.0 / T25 + torch.log(x) / B) / 100.0


def thermistor_sh(x):
    """10k NTC full Steinhart-Hart (adds the (ln R)^3 term).
    NOT exactly representable shallow -> tests approximation quality."""
    A, B, C = 1.129241e-3, 2.341077e-4, 8.775468e-8
    lr = torch.log(x * 10000.0)
    return 1.0 / (A + B * lr + C * lr ** 3) / 100.0


def photodiode_log(x):
    """Log-compressed photocurrent frontend, 5 decades: y = ln(x)/ln(10)/5.
    x = I/I_dark in [1, 1e5]; output = normalized decades. Depth-1 exact."""
    return torch.log(x) / math.log(10.0) / 5.0


TARGETS = {
    # name: (fn, train x-range, extrapolation x-range, unit scale to report,
    #        unit name)  -- thermistor ranges = T in [-20,60]C train,
    #        [-40,85]C full, converted through the beta model R(T).
    "thermistor_beta": (thermistor_beta, (0.30, 7.85), (0.145, 24.8), 100.0, "K"),
    "thermistor_sh":   (thermistor_sh,   (0.30, 7.85), (0.145, 24.8), 100.0, "K"),
    "photodiode_log":  (photodiode_log,  (1.0, 1.0e5), (1.0, 1.0e5),  5.0,  "dec"),
}


def make_data(target_name, n_train=256, n_extrap=512, seed=1234):
    """Log-uniform sampling in x (resistance/current decades are the natural
    measure for sensors). Extrapolation set = full range MINUS train range."""
    fn, (tlo, thi), (elo, ehi), scale, unit = TARGETS[target_name]
    g = torch.Generator().manual_seed(seed)

    xt = torch.exp(torch.empty(n_train, dtype=REAL_DTYPE).uniform_(
        math.log(tlo), math.log(thi), generator=g))
    xe_all = torch.exp(torch.empty(n_extrap * 4, dtype=REAL_DTYPE).uniform_(
        math.log(elo), math.log(ehi), generator=g))
    mask = (xe_all < tlo) | (xe_all > thi)
    xe = xe_all[mask][:n_extrap]
    if len(xe) == 0:            # extrap range == train range (photodiode)
        xe = torch.exp(torch.empty(n_extrap, dtype=REAL_DTYPE).uniform_(
            math.log(elo), math.log(ehi), generator=g))
    return xt, fn(xt), xe, fn(xe), scale, unit


# ---------------------------------------------------------------------------
# Training (in-situ: gradients flow through the non-ideal forward model)
# ---------------------------------------------------------------------------

def rmse(pred, target):
    return torch.sqrt(torch.mean((pred - target) ** 2)).item()


@torch.no_grad()
def evaluate(model, x, t, noisy=False, n_noisy_passes=8):
    """Clean RMSE, plus noise-averaged RMSE if the config has noise."""
    clean = rmse(torch.nan_to_num(model(x, noisy=False), nan=1e6), t)
    if noisy and model.acfg.noise_std > 0:
        acc = 0.0
        for _ in range(n_noisy_passes):
            acc += rmse(torch.nan_to_num(model(x, noisy=True), nan=1e6), t) ** 2
        return clean, math.sqrt(acc / n_noisy_passes)
    return clean, clean


def train(model, x_train, t_train, tcfg: TrainConfig, verbose=False):
    """Full-batch Adam with cosine lr decay; tracks best clean-eval state."""
    opt = torch.optim.Adam(model.parameters(), lr=tcfg.lr)
    best = {"rmse": float("inf"), "state": None}

    for it in range(1, tcfg.iters + 1):
        frac = it / tcfg.iters
        lr = tcfg.lr_final + 0.5 * (tcfg.lr - tcfg.lr_final) * (
            1 + math.cos(math.pi * frac))
        opt.param_groups[0]["lr"] = lr

        opt.zero_grad()
        pred = model(x_train, noisy=True)
        loss = torch.mean((pred - t_train) ** 2)
        if tcfg.lam_l1 > 0:
            loss = loss + tcfg.lam_l1 * sum(
                p.abs().mean() for p in model.affine_params())
        if tcfg.lam_span > 0 and getattr(model, "_pen", None) is not None:
            loss = loss + tcfg.lam_span * model._pen
        if not torch.isfinite(loss):
            continue
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), tcfg.grad_clip)
        opt.step()

        if it % tcfg.eval_every == 0 or it == tcfg.iters:
            r, _ = evaluate(model, x_train, t_train)
            if r < best["rmse"]:
                best["rmse"] = r
                best["state"] = {k: v.detach().clone()
                                 for k, v in model.state_dict().items()}
            if verbose:
                print(f"  it={it:5d} lr={lr:.4f} train_rmse={r:.3e}")

    if best["state"] is not None:
        model.load_state_dict(best["state"])
    return best["rmse"]
