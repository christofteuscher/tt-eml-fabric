## How it works

This is an analog computing tile: a chain of two **EML cells**, each
computing `exp(u) − ln(v)` in current mode using translinear NPN loops
(the "single operator" of Odrzywołek's EML formulation).  Weighted
connections between cells are radix-4, all-unit-device current MDACs
(4 magnitude bits + sign per weight), and the whole fabric is biased from
an on-chip PTAT core with a 3-bit trimmed reference resistor.

The chain is `x_in` → CELL A → γ weight → CELL B → `out_CELLB`.  Only the
final output is observable: with three analog pins there is no room for
stage taps, so a wrong answer cannot be localised to CELL A, the coupling
or CELL B.

### Block diagram

```
              ua[1] iref_in
                 │  (optional external bias override)
                 ▼
        ┌──────────────────┐        ┌──────────────┐
        │  PTAT bias core  │──pbias─┤ rptat_trim   │  3-bit R trim
        │  + refchain      │        │ 15–50 kΩ     │  bits [27:25]
        └────────┬─────────┘        └──────────────┘
                 │ pbias / vcasc / vg / vg4  (to everything below)
                 ▼
 ua[0]      ┌─────────┐   out_A   ┌────────┐   ┌────────┐  sum_Bv  ┌─────────┐
 x_in ─────►│ CELL A  ├──────────►│ glue   ├──►│ γ MDAC ├─────────►│ CELL B  ├──► ua[2]
            │ exp−ln  │           │ pedestal│   │ weight │          │ exp−ln  │   out_CELLB
            └────▲────┘           └────────┘   └────▲───┘          └────▲────┘
                 │                                  │                   │
              A.u A.v                             B.γ                B.u B.v
                 │                                  │                   │
            ┌────┴──────────────────────────────────┴───────────────────┴────┐
            │   cfgdig — 29-bit scan chain, 5 weights × (4 mag + sign)        │
            └────────────────────────────────────────────────────────────────┘
                 ▲              ▲                ▲
              ui[0]          ui[2]            uo[0]
             scan_data      scan_clk          scan_out
```

Each cell computes `eml(u,v) = exp(u) − ln(v)`.  Every weight is a signed
radix-4 current MDAC built from identical unit devices; the weights set
`u` and `v` at each cell input, and the γ weight scales the coupling from
CELL A into CELL B.

### Configuration — a 29-bit scan chain (3.3 V logic, `sky130_fd_sc_hvl`)

| bits | function |
|---|---|
| `[24:0]` | five 5-bit signed weights: `A.u`, `A.v`, `B.u`, `B.v`, `B.gamma` |
| `[27:25]` | R_ptat trim (3 bits, 8 codes) |
| `[28]` | chain tail — appears on `scan_out` |

Each 5-bit weight is `w[4]` = sign, `w[3:0]` = magnitude m, value = m/4
(full scale ±3.75 unit currents).  The magnitude is **two base-4 digits,
binary within each digit**: `m = (a0 + 2·a1) + (b0 + 2·b1)/4`.

The chain is **latchless**: the analog follows the shift register
directly, so program first, then measure — values wiggle harmlessly while
a word shifts.

### Analog pins — currents, not voltages

| pin | net | role |
|---|---|---|
| `ua[0]` | `x_in` | input current |
| `ua[1]` | `iref_in` | override/augment the internal bias reference (the chip self-biases; this is for characterisation) |
| `ua[2]` | `out_CELLB` | final output of the chain |


## How to test

1. Power up (1.8 V digital + 3.3 V VAPWR).  Release `rst_n` — the config
   chain resets to a safe all-zero state (all weights off).
2. Shift 29 configuration bits into `ui[0]` (scan_data), clocked on the
   rising edge of **`ui[2]`** (scan_clk).  `uo[0]` (scan_out) echoes the
   chain 29 clocks later — shift 58 clocks and compare the second 29 to
   verify programming.
   *`ui[2]`, not `ui[1]`: `ui[1]` sits off the analog macro's 0.6 µm
   routing grid, so no via could be placed beside it.*
3. Drive `ua[0]` (x_in) with the input current: unit current is 0.5 µA,
   useful range roughly 0.1–6.5 µA.
4. Measure `ua[2]` (out_CELLB) for the chain result.
5. Optionally trim the PTAT current via bits `[27:25]` (8 monotonic codes
   spanning 15–50 kΩ, ~127 % of design current; nominal at code `100`)
   and observe the effect on any output.

No clock is required beyond the scan clock you provide; the analog is
continuous-time.

## Known limitations

- **Weight monotonicity is likely, not guaranteed.**  Each radix-4 digit
  is binary rather than thermometer (the thermometer decoder was removed
  to fit the config routing), so a code step at an inter-digit carry is a
  *difference* between matched devices instead of simply adding a leg.
  Simulated (schematic level): nominal DNL −0.139/+0.057 LSB; across 70
  mismatch samples **0 were non-monotonic**, with the per-sample worst
  DNL distributed mean −0.276, σ 0.190 LSB, worst observed −0.981 against
  the −1.0 limit.  That puts the limit ~3.8σ out — but note −0.981 turned
  up once in 70 samples where a Gaussian at that σ predicts nearer 1 in
  3800, so the tail is heavier than normal and 70 samples cannot resolve
  it.  The margin is real but not large.  If weight sweeps show a flat or
  reversed step, suspect codes 4, 8, 12 of a digit pair before suspecting
  your setup.
- **The exp term is correct as of this build.**  An earlier build computed
  `exp(1.23·u)` because the poly resistors were sized by `L/W × rsheet`,
  which ignores end resistance (~24 % low).  Corrected: the exponent is
  now 0.96 of nominal.
- **THE ln ARGUMENT IS NOT `v`.  The cell computes `ln(v + 2.57)` up to scale.**
  Measured 2026-08-14 on the layout-matched netlist (`emlcell_b_sim12.inc`,
  derived from `lvsref/emlcell_b_flat.spice`, which LVS-matches the shipped
  layout), tt, 27 °C, over `v = 0.5 … 4`:

  | fitted against | result | max residual |
  |---|---|---|
  | `ln(v + 2.57)` | `2.55 − 1.145·ln(v + 2.57)` | **0.0002 units** |
  | `ln(v)` | `1.05 − 0.416·ln(v)` | 0.078 units |

  Read the first row: as a log amplifier the cell is close to ideal — slope
  −1.145 against its true argument, residual two ten-thousandths of a unit.
  It is only the *argument* that is offset.

  **Mechanism.**  The layout hard-wires a bias pedestal the schematic bench
  never modelled: `XLPA` puts a fixed 936 nA (1.872 units) on the `nv`
  transdiode, and the reference leg `XLPB_LVR` carries 1394 nA (2.789 units).
  That accounts for roughly 1.87 units of offset.  **The measured offset on
  the shipping (unbuffered) cell is 2.57**, so the pedestal explains most but
  not all of it; the remaining ~0.7 units is not yet accounted for and is an
  open item.  The pedestal model was validated against the *buffered* build,
  where it matched the local slope at every point; it has not been re-fitted
  for this one.  What is directly measured, and what should be relied on, is
  the fit in the table above.

  **How to use it.**  Pre-map the input as `v_ext = a·v_eff − 2.57` (units
  of the 0.5 µA reference; `a` is absorbed by the compiler's alpha).  This has to happen in the compiler or the drive
  electronics: `ln(v + 2.57)` is **not** `k·ln(v)` for any `k`, so no output
  gain or offset trim recovers it.  `silicon/README.md:158` records
  this as the original design intent — "ln input becomes ln((v+2)/3);
  constants absorbed by alpha/compiler" — it simply was never carried into
  this document.

  **CORRECTION.**  Earlier revisions of this file claimed `1.06 − 1.05·ln(v)`
  with a 0.019-unit residual and a usable range of `|error| < 0.05` for
  `v ≥ 1`.  All three claims were wrong.  That figure came from a schematic
  bench (`char/_v2d_lay2.inc`) which (a) omits the pedestal legs the layout
  generates internally, and (b) is byte-identical to `char/_v2d_quiet.inc`
  and self-oscillates, so the number was read off a DC equilibrium the bench
  does not occupy.  Time-averaging that bench through its limit cycle gives
  `0.83 − 1.38·ln(v)` with a 0.53-unit residual.  The statement that the
  slope only collapses below `v ≈ 0.35` was also wrong: without the input
  mapping the apparent slope varies continuously across the whole range,
  −0.15 at `v = 0.35` to −0.63 at `v = 4`, never reaching −1.

  **A source-follower buffer was briefly shipped and has been REVERTED.**
  Between 2026-08-13 and 2026-08-14 this repository carried a build with a
  source follower (`MSF`, W16 L1) plus a 0.5 µA sink (`MBM`, W4 L8) added to
  the two ln servos, intended to fix an apparent slope error.  That apparent
  error was an artifact of fitting against `ln(v)` instead of the true
  argument — the unbuffered cell was already a clean logarithm — and the
  buffer made the servo loop **unstable**: a sustained ~7.2 MHz limit cycle
  from the DC operating point with no stimulus, 1.37 units peak-to-peak at
  the output for `v = 1` (126 % of the signal), confirmed under both
  trapezoidal and Gear-2 integration and by active perturbation.  Reverting
  either added device restores 0.00000 units of ripple with the DC law
  unchanged.  The current GDS is the unbuffered cell and is stable.
- **The thermistor-linearisation figure has not been re-validated.**  The
  "residual 1.1 % of span" result was obtained with the earlier
  three-digit thermometer weight; this build has two digits, binary.
- All results quoted here are simulation, schematic-level except where
  stated.  Nothing has been measured on silicon.

## External hardware

A source-measure unit (or one current source + one current meter) for the
analog pins.  Everything else — bias, references, configuration — is
on-chip.

## Reference

The operator this fabric implements:

> A. Odrzywołek, **"All elementary functions from a single operator"**,
> Institute of Theoretical Physics, Jagiellonian University, Kraków.
> [arXiv:2603.21852v2](https://arxiv.org/abs/2603.21852) \[cs.SC\], 4 Apr 2026.

The paper shows that the single binary operator

```
eml(x, y) = exp(x) − ln(y)
```

together with the constant 1 generates the standard scientific-calculator
repertoire — constants (`e`, `π`, `i`), arithmetic (`+ − × /`,
exponentiation) and the transcendental and algebraic functions.  For
example `eˣ = eml(x, 1)` and `ln x = eml(1, eml(eml(1, x), 1))`.  Every
expression becomes a binary tree of identical nodes under the grammar
`S → 1 | eml(S, S)`.

This chip is a hardware realisation of that node: two `eml` cells with
programmable weights, so a depth-2 tree can be evaluated in continuous
time rather than symbolically.
