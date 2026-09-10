# EML Fabric — Analog Non-Ideality Simulator

Software go/no-go model for the analog/translinear EML fabric proposed in
TLAB-TR-2026-007, built before committing to any silicon (Tiny Tapeout or
otherwise). It answers: *does a hardware-justifying advantage survive
realistic analog non-idealities?*

## What it models

A full binary tree of identical analog cells computing
`eml(u, v) = exp(u) − ln(v)`, with each cell input a programmable affine
combination `α + β·x + γ·child` (report eq. 2), a single external input
`x`, and a full-precision digital readout stage `A·root + B`.

Deliberate differences from the upstream v16 PyTorch trainer:

- **Real-valued** signals (analog circuits have no complex plane); the ln
  input rails at a positive floor like a log amp.
- **Continuous affine weights** instead of softmax symbol selection —
  calibration curves contain real constants.
- **Non-ideality forward model**, each knob independently switchable
  (`AnalogConfig`):
  | knob | physics |
  |---|---|
  | `sat` | dynamic-range ceiling; cell output and exp() rail at ±sat |
  | `ln_floor` | log-amp input floor (decades of usable range) |
  | `noise_std` | per-stage additive noise, fresh every pass |
  | `mismatch_gain_std`, `mismatch_offset_std` | static per-cell device mismatch (drawn per chip from `mismatch_seed`) |
  | `weight_bits`, `weight_range` | finite α,β,γ DAC resolution (QAT with straight-through estimator) |
  | `temp_delta` | global V_T drift: exp arg scales 1/(1+δ), ln output scales (1+δ) |
  | `rail_leak` | small saturating leak through every rail (soft compression; keeps gradients alive — flat rails stall in-situ learning) |
  | `ln_pedestal` | **(a)** the realised cell computes `ln(v + s)`; `s = 2.547` units on the segmented-resistor basis (`PEDESTAL_SEGMENTED`), `2.574` on the lumped LVS basis (`PEDESTAL_LUMPED`) |
  | `atten_v` | **(b)** per-hop gain of the v port, `0.2551` (`ATTEN_V_NOMINAL`) |
  | `span_decades`, `span_hi`, `span_penalty` | **(c)** finite device span: currents confined to `[span_hi·10^-span_decades, span_hi]`, measured as `5.80e-6 .. 1366` units = `8.372` decades (`SPAN_*`); `span_penalty > 0` also accrues a hinge loss in decades, added to the loss via `TrainConfig.lam_span` |

`silicon_config(**over)` returns the **physically correct** silicon cell:
**(a) only**. (b) is *derived* from (a) — `lambda_v = 1.094/(1.741+2.547)
= 0.2551` — so enabling both double-counts the v-port loss (realised hop
gain 0.0933 instead of the measured 0.2551, 2.7× too small), and (c) does
not bind at its true 8.372 decades (0.00 over-excursion measured on every
workload in `results/nonideal.json`). Building an `AnalogConfig` with
`ln_pedestal != 0` **and** `atten_v != 1` raises a `RuntimeWarning` unless
you pass `allow_double_count=True`. `worst_case_config(**over)` is the
pre-packaged opt-in for that pessimistic bound — quote it as a bound, never
as "the silicon". Before 2026-08 `silicon_config()` returned the
double-counted combination; `run_multivar.py` rows labelled `silicon+pdk`
in `results/multivar.json` come from it (the script now emits
`pedestal+pdk`), and the two `mv_product_silicon_*` regression pins are
deliberately kept on `worst_case_config()` so their reference values stay
bit-for-bit valid.

All defaults = ideal real-domain math (verified to
machine precision in `test_fabric_sim.py`; `test_regression.py` re-checks
the pre-existing scalar results bit-for-bit).

## Multivariate input (`eml_fabric_topo.AnalogEMLFabric`)

`FabricSpec(..., n_vars=n)` makes the fabric take `x` of shape `(B, n)`
instead of `(B,)`; `n_vars=1` keeps the old 1-D signature and the old
numbers exactly. The available leaves are the rails `[1, x1..xn]`, and
`AnalogEMLFabric(..., var_mode=...)` chooses how a cell input picks among
them:

| `var_mode` | assignment | parameters |
|---|---|---|
| `'dense'` (default) | learned, continuous | `beta[l]` is `(n_l, 2, n_vars)`: every path weights every variable (use `TrainConfig.lam_l1` to sparsify) |
| `'soft'` | learned, discrete | `sel_logit[l]` `(n_l, 2, n_rails)`, argmax one-hot with a straight-through estimator; `model.tau` is the softmax temperature |
| `'fixed'` | searched | buffer `sel_l` `(n_l, 2)` of rail indices; `model.assignment()` / `model.set_assignment()`, and `eml_fabric_topo.search_assignments(spec, acfg, x, t, n_probe, probe_iters)` random-searches them |

Targets live in `eml_feynman.py`: `FEYNMAN[name]`, `make_data_mv(name)`
(returns `(B, n_vars)` inputs and a unit-RMS target, so RMSE is already an
NRMSE), `n_vars(name)`, `var_names(name)`. Coverage is 2/3/5/5/6/9
variables from the AI Feynman set.

## First benchmark: thermistor calibration (the agreed go/no-go)

`run_thermistor_benchmark.py` learns thermistor R→T calibration in-situ
under each non-ideality (sensitivity ranking), compares **in-situ
learning vs factory-transferred weights** on mismatched chips (the
adaptive-calibration selling point), and reads the learned configuration
back as a sympy formula (the "config = formula" claim).

Targets:
- `thermistor_beta` — 10k NTC β-model, `T = 1/(1/T25 + ln(x)/B)`.
  Exactly representable by a 3-cell EML chain (verified by hand-programming
  it in the tests; readback returns the β-model with correct constants).
- `thermistor_sh` — full Steinhart–Hart with the (ln R)³ term; not exactly
  representable shallow → approximation-quality probe.
- `photodiode_log` — 5-decade log frontend (used in tests).

Train range T ∈ [−20, 60] °C; extrapolation tested on [−40, 85] °C minus
the train range. Errors reported in Kelvin.

## Running

The default `python3` on this machine is x86_64 under Rosetta; torch is
arm64, so force the architecture:

```sh
arch -arm64 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 test_fabric_sim.py
arch -arm64 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 run_thermistor_benchmark.py --quick   # ~30 s smoke
arch -arm64 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 run_thermistor_benchmark.py          # full sweep
arch -arm64 .../python3.12 test_regression.py --check results/regression_ref.json  # scalar path unchanged
arch -arm64 .../python3.12 run_multivar.py --pilot      # AI Feynman targets
arch -arm64 .../python3.12 run_nonideal.py --pilot      # effects (a)/(b)/(c)
```

Results land in `results/*.json`; see `RESULTS.md` for the analyzed runs.

## Known limitations / next steps

- Gradient training is a proxy for in-situ hardware training (which would
  be SPSA/perturbation-based); the `rail_leak` exists partly for this.
- No crystallization pressure yet (`TrainConfig.lam_l1` defaults to 0):
  ideal-hardware fits are good numerically but read back as bushy
  expressions, not the clean β-model. Formula *recovery* (vs fit) needs a
  sparsity/structure schedule — next work item.
- Mismatch is first-order (gain/offset); no 1/f noise, no leakage,
  no inter-cell parasitics.
- `atten_v` (b) is not independent of `ln_pedestal` (a): FAB_ERROR.md
  defines `lambda_v = -k/(out + P + s/G)`, i.e. the measured 0.2551 per-hop
  gain is a *consequence* of the pedestal. The simulator reproduces
  `k/(v+s) = 1.094/(1.741+2.547) = 0.2551` from (a) alone, so switching
  (b) on as well double-counts the loss. Use `abc_silicon` for the
  worst-case bound and `a_pedestal` for the physically-derived one.
- The cell still has unit exp/ln gains: the measured `A = 1.101`,
  `a = 0.967`, `k = 1.094`, `D = 2.469` of the v3b cell are not injected,
  only the pedestal, the v-port gain and the span.
