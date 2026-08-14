![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg)

# EML Fabric — an analog "single operator" computing tile

A 2×2 Tiny Tapeout analog tile (SKY26c, sky130A) implementing a chain of
two **EML cells**, each computing `exp(u) − ln(v)` in current mode using
translinear NPN loops — the "single operator" of Odrzywołek's EML
formulation. Weighted connections between cells are radix-4,
all-unit-device current MDACs, and the whole fabric is biased from an
on-chip PTAT core with a trimmed reference resistor.

📖 **[Full bringup guide → docs/info.md](docs/info.md)** — pinout, scan
chain format, test procedure, and known limitations. **Read it before
probing anything**: two pins do not do what their names suggest at first
glance, and one measured limitation affects how results should be
interpreted.

## At a glance

| | |
|---|---|
| tile | 2×2 analog, `uses_vapwr` (3.3 V VAPWR + 1.8 V VDPWR) |
| analog pins | 3 — `ua[0]` x_in, `ua[1]` iref_in, `ua[2]` out_CELLB |
| digital | 29-bit scan chain, `ui[0]` data, **`ui[2]` clock**, `uo[0]` out |
| cells | 2 EML cells + 5 programmable weights (4 magnitude bits + sign) |
| unit current | 0.5 µA; useful input range ≈ 0.1–6.5 µA |

## Verification status

Everything below is **simulation**; nothing has been measured on silicon.

| check | result |
|---|---|
| top-level routing | 57 / 57 nets, pad access 7 / 7 |
| DRC (KLayout, TT deck) | 0 |
| DRC (Magic, on the shipped GDS) | 0 |
| LVS (full assembly) | MATCH |
| power connectivity | 23 / 23 pins |
| TT precheck | pass |

## Known limitations

Measured, not suspected, and described in detail in
[docs/info.md](docs/info.md):

- **The ln argument is shifted and scaled: the cell computes
  `ln(v + 2.57)` up to scale, not `ln(v)`.** This is the single most important
  thing to know before driving the `v` input.
  Against its true argument the logarithm is excellent — measured on the
  layout-matched netlist over `v = 0.5 … 4`:

  | fitted against | result | max residual |
  |---|---|---|
  | `ln(v + 2.57)` | `2.55 − 1.145·ln(v + 2.57)` | **0.0002 units** |
  | `ln(v)` | `1.05 − 0.416·ln(v)` | 0.078 units |

  So the cell is a near-ideal log amplifier whose input is offset. The
  cause is a bias pedestal: the layout hard-wires 936 nA onto the `nv`
  transdiode (`XLPA`) against a 1394 nA reference (`XLPB_LVR`), which
  accounts for roughly 1.87 units of the offset. The measured offset is
  2.57, so the pedestal explains most but **not all** of it — the remainder
  is not yet accounted for.
  **To get `ln(v)`, pre-map the input as `v_ext = a·v_eff − 2.57`**
  (in units of the 0.5 µA reference). This *must* be done in the compiler
  or the drive electronics: `ln(v + 2.57)` is **not** `k·ln(v)` for any
  `k`, so no gain or offset trim on the output can recover it.
  Without the mapping the apparent local slope rises smoothly from −0.15
  at `v = 0.35` to −0.63 at `v = 4` and never reaches −1.
  Earlier revisions of this file quoted `−1.05·ln(v)` with a 0.019 residual.
  That figure was measured on a schematic bench that (a) omits the pedestal
  legs the layout generates internally and (b) self-oscillates, so it was
  read off an equilibrium the bench does not occupy. It was wrong; this
  supersedes it.
- **Per-cell output level varies by 24 % (1σ)** — mean 1.098 units, σ 0.266,
  range 0.446–1.838 over 440 Monte Carlo samples. Mismatch-limited, so it does
  **not** average out across cells. The *shape* is unaffected (fits still hold
  to ~2.5e-4 units), so each cell is an excellent log amplifier with an
  uncertain gain and offset. **Every cell output needs per-cell calibration.**
- **Useful temperature window ≈ −8 °C to +54 °C.** No thermal-voltage
  compensation, so the scale factor is PTAT by construction: `k_ln` runs
  0.887 at −40 °C to 1.520 at +125 °C (tracks `T` to within 0.6 %). Only
  0.54 % of that swing is process. A design limit, not a defect.
- **Stable across the full box** — `i(VOUT)` pk-pk = 0.000e+00 at all 25
  corner × temperature conditions and all 440 Monte Carlo samples.
- **Only the final output is observable.** With three analog pins there is
  no room for stage taps, so a wrong answer cannot be localised to CELL A,
  the coupling, or CELL B.
- **All figures are simulation**, at schematic-level sizing with
  layout-verified topology. `emlcell_b`'s parasitic extraction is blocked
  (Magic mis-recognises its poly resistors and shorts them), so the ln
  numbers above are **not** parasitic-annotated. For reference, adding
  parasitics to the MDAC moved its DNL by 0.005 LSB — reassuring, but not
  evidence about the servo loop.

## Repository layout

| path | contents |
|---|---|
| `gds/`, `lef/` | the hardened analog macro |
| `src/` | `cfgdig.v` (config scan chain) and the TT wrapper |
| `docs/info.md` | bringup guide — pinout, scan format, test steps |
| `test/` | decode testbench |

The layout **generators** (scripted GDS, LVS references, characterisation
benches) live in a separate repository; this one carries only the
submitted artefacts.

## What is Tiny Tapeout?

Tiny Tapeout is an educational project that makes it easier and cheaper
than ever to get your designs manufactured on a real chip.
See https://tinytapeout.com and the
[analog specs page](https://tinytapeout.com/specs/analog/).
