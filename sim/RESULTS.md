# Thermistor benchmark — run 1 (2026-07-02)

Full sweep: depth-3 fabric (7 cells), 2 targets, 6 seeds/config, 3000 Adam
iters, one non-ideality at a time. Raw data:
`results/thermistor_benchmark_full_d3.json`, log `results_full_run.log`.
Errors in Kelvin over the T ∈ [−20, 60] °C training range (80 K span).

## Headline table (train RMSE, median / best over 6 seeds)

| config | β-model med | best | Steinhart–Hart med | best |
|---|---|---|---|---|
| ideal          | 0.83 | 0.18 | 0.72 | 0.23 |
| noise 1e-3     | 0.48 | 0.27 | 0.39 | 0.22 |
| noise 3e-3     | 0.31 | 0.08 | 0.39 | 0.15 |
| noise 1e-2     | 0.79 | 0.25 | 0.77 | 0.14 |
| mismatch 1%    | 0.76 | 0.22 | 0.40 | 0.20 |
| mismatch 5%    | 2.08 | 0.36 | 2.11 | 0.37 |
| mismatch 10%   | 1.25 | 0.26 | 1.61 | 0.41 |
| sat 30         | 4.57 | 2.42 | 4.68 | 2.85 |
| sat 10         | 15.8 | 1.01 | 8.07 | 0.74 |
| sat 3          | 10.6 | 0.35 | 10.2 | 0.89 |
| 8-bit weights  | 2.25 | 1.46 | 1.54 | 0.57 |
| 6-bit weights  | 4.00 | 2.55 | 2.94 | 2.09 |
| 4-bit weights  | 7.07 | 4.29 | 8.34 | 4.31 |

Factory-transfer (ideal-trained weights programmed onto a mismatched
chip) vs in-situ training on that chip, median:

| mismatch | transfer | in-situ | in-situ best |
|---|---|---|---|
| 1%  | 1.3–1.6 K | 0.4–0.8 K | 0.2 K |
| 5%  | 4.6–5.0 K | 2.1 K     | 0.4 K |
| 10% | 9.4–10.2 K | 1.3–1.6 K | 0.3 K |

V_T drift applied to ideal-trained fabric (no retraining):
±3% → ~7 K, ±6% → ~13 K.

Depth sweep (ideal): depth-1 2.8 K, depth-2 1.4–2.3 K, **depth-3 0.7–0.8 K**,
depth-4 1.2–1.5 K (no gain, harder optimization). Depth 3 = sweet spot,
matching where the β-model is exactly representable.

## Findings

1. **The fit works.** An ideal 7-cell fabric calibrates a thermistor to
   0.2–0.8 K over 80 K — within NTC interchangeability tolerance with
   best-of-restarts. Steinhart–Hart (not exactly representable) fits as
   well as the β-model (which is): at these accuracies the fabric is an
   approximator, not a law-finder.

2. **In-situ learning is the killer feature — the adaptive-calibration
   selling point survives.** At realistic subthreshold mismatch (5–10%),
   factory-programmed weights degrade to 5–10 K while in-situ training
   absorbs the mismatch almost completely (median 1.3–2.1 K, best 0.3 K).
   The crossover is at ~1% mismatch: better-matched-than-subthreshold
   hardware doesn't need in-situ learning. (The quick 800-iter run showed
   the opposite — the advantage only appears with an adequate training
   budget.)

3. **Sensitivity ranking (worst → most benign):**
   - **V_T temperature drift** — catastrophic. ±3% (≈ ±9 °C on-chip)
     already costs ~7 K. PTAT/ratiometric bias compensation is
     *mandatory* in any translinear implementation; alternatively drift
     becomes the argument for *continuous* in-situ adaptation (untested).
   - **Dynamic-range ceiling** — confirmed as the big architectural risk,
     but with a twist: the failure is *trainability*, not representability.
     Median RMSE collapses below sat≈30 (5–16 K), yet best seeds still
     find well-scaled solutions inside sat=3 (0.35 K!). Tight rails make
     the loss landscape hostile; restarts (or smarter optimizers) recover
     it. Design point: sat ≥ ~30 in signal units, plus a restart budget.
   - **Weight resolution** — ≥8 bits for ~1 K; 10–12 bits likely needed
     for 0.1 K-class calibration. 4 bits is unusable (4–8 K).
   - **Per-stage noise** — a non-issue up to 1e-2 (0.4% of the ~2.5–3.3
     signal), and mild noise (3e-3) actually *helps*: best runs beat the
     ideal fabric (0.08 K vs 0.18 K). Annealing for free — a genuinely
     analog-friendly result.

4. **Formula recovery does NOT happen by itself.** Extrapolation to
   [−40, 85] °C is bad everywhere (15–60+ K) and readbacks are bushy
   ~20-term expressions, not `1/(a + b·ln x)`. Gradient fit ≠
   crystallization. This is the main open item: add sparsity/structure
   pressure (L1 exists as `TrainConfig.lam_l1`, unused; consider
   exp-path-off priors, pruning, or v16-style hardening on the affine
   weights) and re-measure extrapolation as the recovery metric.

## Caveats

- 6 seeds → medians are noisy (mm-10% median < mm-5%; sat-10 vs sat-3
  ordering inverted for β). Trends, not precision.
- Gradient training with `rail_leak=0.02` is a proxy for hardware in-situ
  training (SPSA etc.); rails are the place this proxy is most optimistic.
- One knob at a time; no combined-non-ideality run yet (a real chip has
  all of them simultaneously).

## Run 2 (2026-07-02): combined realistic chip — the go/no-go number

All non-idealities simultaneously (5% mismatch + 3e-3 noise + sat 30 +
8-bit weights), 8 seeds, depth 3. `results/combined_chip.json`.

| metric | β-model med / best | Steinhart–Hart med / best |
|---|---|---|
| in-situ train | 6.3 / **0.94 K** | 3.6 / **0.76 K** |
| factory transfer | 27.8 / 15.0 K | 25.0 / 5.5 K |
| drift ±3% after training | ~14 / ~1.0 K | ~11 / ~1.5 K |

Reading: non-idealities COMPOUND (medians ~3× worse than the worst
single knob); factory programming is dead on a realistic chip (25–28 K);
in-situ learning still reaches sub-1 K — but only in the best seed of 8,
so a restart/repeated-calibration budget is part of the architecture.
Notably the best seeds are also nearly drift-immune (seed 7 β: 0.94 K
in-situ, ±1 K under ±3% V_T drift), suggesting drift-robust
configurations exist and could be selected for — worth a dedicated study.
Suspected main compounding pair: 8-bit weights × sat-30 (quantization
blocks the fine rescaling that tight dynamic range demands) — untested.

**Verdict: qualified GO.** The concept survives a realistic chip if
calibration = multiple restarts + pick-best, which is cheap in-situ.

## Run 3 (2026-07-20): PDK-calibrated chip + drift mitigation

Same combined chip but with sky130-measured parameters (NPN offset σ
0.005 instead of guessed 0.025; gain σ 0.02 kept for FET stages), and
three drift scenarios. 8 seeds, depth 3. `results/pdk_chip.json`.

| metric (median / best, K) | β-model | Steinhart–Hart |
|---|---|---|
| in-situ baseline | 5.5 / 0.77 | 3.8 / 0.86 |
| drift ±10% uncompensated | 30.6 / 4.4 | 26.9 / 1.4 |
| drift ±1.5% (PTAT residual) | 9.7 / 1.1 | 8.4 / 0.89 |
| drift ±10% + 300-iter retrain | 14.9 / 4.0 | 14.0 / 0.87 |

Reading: (1) baseline unchanged vs run 2 — the 5× better bipolar
matching doesn't move the needle, confirming sat×bits (not mismatch) as
the binding constraint; (2) uncompensated drift is fatal, as expected;
(3) a PTAT loop with 1.5% residual still costs ~2× at median but best
seeds barely degrade (0.89–1.1 K vs 0.77–0.86) — **PTAT + restart
selection works; PTAT alone at median does not**; (4) short retraining
recovers only half the drift damage (27→14 K median) — continuous
adaptation is a *supplement* to PTAT, not a substitute, at least at this
retraining budget. Drift-robust-seed selection keeps looking like the
key technique — dedicated study still pending.

## Next steps (in rough priority)

1. Crystallization pressure → clean readback + extrapolation (the
   interpretability leg needs this to be real).
2. Combined-realistic-chip config (mismatch 5% + noise 3e-3 + sat 30 +
   8 bits) — the actual go/no-go number.
3. Drift + continuous in-situ retraining (turn the worst weakness into
   the adaptation story).
4. SPSA/perturbation training instead of backprop (hardware can't do
   backprop through itself).
