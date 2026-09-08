# MDAC design + chip area estimate (2026-07-23)

## DECIDED 2026-07-25: 3 cells x 4 programmable weights

Floorplan closes at 90% of the die with this configuration (6 weights was
97% = unroutable). The four programmable weights per cell are:

| weight | drives | why programmable |
|---|---|---|
| `u.alpha` | exp-path constant | calibration trim -- what in-situ learning adjusts |
| `v.alpha` | ln-path constant  | calibration trim |
| `u.gamma` | child -> exp input | chain coupling / reconfiguration |
| `v.gamma` | child -> ln input  | chain coupling / reconfiguration |

`beta` is NOT a DAC: x enters cell A's ln input through a fixed 1:1
mirror. Its scale is absorbed by the two-point readout calibration, and
the single-cell test still works (set gamma = 0, drive x, trim with the
alphas). The large +6 unit offsets stay as always-on legs inside the
cell, which is why a +-4 unit DAC range suffices.

Range +-4 units (2-bit thermometer coarse + 4-bit binary fine), measured
0.90 kum2 per weight -> 3.6 kum2 per cell, 10.8 kum2 for the chip.

## SUPERSEDED 2026-07-25: the segmentation below did not survive SPICE

The plan was 3 thermometer MSBs + 5 binary LSBs with legs ratioed by W/L.
Built and swept over all 64 codes in ngspice, it is unusable: the ratioed
legs deliver 0.088 / 0.187 / 0.473 / 0.688 units against 0.062 / 0.125 /
0.250 / 0.500 ideal (+41 / +50 / +89 / +38 %), giving DNL -6.3 .. +2.2 LSB
and **seven non-monotonic codes**. Current does not scale with W/L across
different geometries in this PDK at these sizes.

**Replaced by a radix-4, all-unit-device DAC** (`mdac_weight.inc`): three
base-4 digits weighted 1, 1/4, 1/16, each a 3-leg thermometer of identical
unit devices. Sub-unit weights come from dividing the *reference* (N
parallel NMOS diodes split a unit current N ways, mirrored back to a PMOS
gate) rather than from device geometry, so every ratio is a device count.

Measured, all 64 codes, tt 27 C, vcasc = 1.0 V:
**monotonic, DNL -0.70/+0.09 LSB, INL +-0.53 LSB, gain error +0.84%.**

Resolution was chosen by measurement too: sweeping `weight_bits` in
fabric_sim over the thermistor chain gives 5.55 K unquantized, 7.17 K at
LSB 1/16 unit, 8.9 K at LSB 1/2 and 10.6 K at LSB 1. The knee is at
1/16 unit, which is what the three digits provide.

New requirement for the bias block: **vcasc = 0.85 V** (~vdd/4).

That value is the tightest constraint in the block and it is not free to
round. Static linearity improves monotonically with vcasc, but the
multiplying range falls off a cliff: at 1.0 V the fine digits measure
perfectly against a fixed reference and deliver a QUARTER of their value
at 2 uA; at 1.55 V (the natural first guess for a 3.3 V rail) both fine
digits deliver exactly zero while the layout looks perfectly healthy.
0.85 V is the only value that is both monotonic and flat over the chain's
actual 0.5-3.4 uA node currents.

| vcasc | monotonic | DNL | 1/4 digit over 0.5-3.4 uA |
|---|---|---|---|
| 0.80 | no (3) | -1.05 | +4.8% |
| **0.85** | **YES** | **-0.96** | **+3.9%** |
| 0.90 | YES | -0.88 | +10.2% |
| 1.00 | YES | -0.70 | collapses (0.777 -> 0.227) |

Also measured: multiplying gain flat to +1.4% over a 50x input range
(0.1-5 uA) on the coarse digit, and output compliance flat from 0.3 V to
1.9 V at every current level.

## Weight MDAC architecture (original plan, superseded above)

Each cell input (u and v) sums three weighted currents by KCL:
`α·iu + β·I_x + γ·I_child` — one plain DAC (α, reference = iu from the
pbias tree) and two multiplying DACs (β, γ; reference = the input
current itself, copied through an input mirror). All three are signed.

Per weight (8-bit signed):
- Input diode + current-steering mirror bank, unit device
  **W=8 L=2 g5v0** (measured σ ≈ 2–3% at µA currents — mirror_mc).
- **Segmentation: 3 thermometer MSBs (7 segments of 32 u) + 5 binary
  LSBs** — at 2–3% segment σ the worst-case major-carry DNL is
  ~0.03·32u ≈ 1 LSB: monotonic. Plain 8-bit binary would not be
  (2.5%·128u ≈ 3 LSB at the MSB carry). Monotonicity is the binding
  requirement for in-situ learning; absolute gain error is absorbed.
- **Sign: complementary steering** — every branch switches between an
  NMOS-mirror return path (subtract) and a direct path (add), i.e. the
  sign bit steers the whole bank, avoiding a duplicate PMOS bank.
  exp-path MDACs invert overall (TIA inverts — established rule).
- Weight range ±8 units (±4 µA FS), LSB = 1/16 unit ≈ 31 nA.
- Switches: minimum-size g5v0; cascode on the output side of each bank
  (output compliance 0.7–1.2 V established).

## Area arithmetic (sky130, conservative layout factors)

Per 8-bit signed weight DAC:
- total mirror width ≈ 2× MSB-bank ≈ 256 units of W/32... in practice
  ~510 µm·µm² of gate area equivalent → with switches, contacts,
  spacing: **≈ 400–600 µm²**
- 4 weights per cell (see the decision above) → **3.6 kµm²/cell** (measured, not estimated)

Per cell (from the v3/v3b netlists):
- 4 OTAs (tails W32L8 = 256 µm² gate each, pairs W32L2) ≈ 2.5 kµm²
- 9 NPNs (~150 µm² each with guard rings) ≈ 1.4 kµm²
- resistors (RU, RLN, 2×100k bleed; high-res poly) ≈ 0.3 kµm²
- mirrors/misc ≈ 0.5 kµm²
- compensation caps 8 pF: **MiM (M3–M4) stacks OVER active area — no
  floorplan cost** (≈4 kµm² of MiM plate, placed over the OTAs/MDACs)
- **cell total ≈ 7–8 kµm² incl. MDACs**

Chip totals (2×2 analog = 334×225 µm ≈ 75 kµm², minus 3v3 power-gate
strip, usable ≈ 70 kµm²):
| block | area |
|---|---|
| 4 × cell (incl. MDACs) | ~30 kµm² |
| PTAT bias + rails + distribution | ~3 kµm² |
| analog output mux (pass-gate tree + buffer) | ~1.5 kµm² |
| config shift register (~250 bits, 1.8 V std cells) | ~4 kµm² |
| ESD/pin interface, decap fill | ~5 kµm² |
| subtotal | ~44 kµm² |
| ×1.5 routing/spacing factor | **~66 kµm²** |

**Verdict: 4 cells FIT with ~6% margin — thin but viable.** Fallback
that costs nothing to keep open: cell 4 (the standalone test cell) is
the drop candidate; the 3-cell chain + bias + mux is ~52 kµm² and
comfortable. Decide at floorplan, not now.

## Config bit budget (shift register)

4 weights × 8 bits × 3 cells = 96 b, + mux select (3 b), + R_ptat trim
(4 b), + spare (25 b) = **128 bits** → daisy-chained DFF scan through
`ui[0]` (data), `ui[1]` (clk), `ui[2]` (latch), `rst_n` — matches the
3-pin digital interface plan with pins to spare.
