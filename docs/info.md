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
- **The ln term is ~0.34 of nominal, not 1.0.**  Measured 2026-08-12: the
  cell computes roughly `exp(u) − 0.34·ln(v)`.  The cause is servo gain —
  `nva` should be pinned to `vrefb` and instead drifts ~17 mV, so most of
  the transdiode differential that should drive the ln resistor appears as
  servo input error.  This is a **design-level** limitation, not a layout
  or process effect: the schematic model with idealised OTAs and perfect
  bias sources measures −0.70, so a single 5-transistor servo stage never
  had the gain a translinear loop needs.  It went unnoticed because the
  characterisation always held `v = 1`, which zeroes the ln term.
  Fixing it needs a cell redesign (cascoded or two-stage servo).
  **The exp path is unaffected** and behaves as designed.
- **The thermistor-linearisation figure has not been re-validated.**  The
  "residual 1.1 % of span" result was obtained with the earlier
  three-digit thermometer weight; this build has two digits, binary.
- All results quoted here are simulation, schematic-level except where
  stated.  Nothing has been measured on silicon.

## External hardware

A source-measure unit (or one current source + one current meter) for the
analog pins.  Everything else — bias, references, configuration — is
on-chip.
