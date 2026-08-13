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

- **The ln term is usable for `v ≥ 0.5`, and degrades below that.** Over
  `v = 0.5 … 4` the cell fits `exp(u) − 1.05·ln(v)` with a maximum residual
  of 0.02 units and a local slope holding between −1.13 and −1.00. Below
  `v ≈ 0.35` the slope collapses toward −0.05: the transdiode is carrying
  under 0.2 µA there and beta falls away, which a fixed buffer current
  cannot track. **Treat `v < 0.35` as out of range.**
  An earlier build of this design had a far worse problem — the ln term was
  not a logarithm at all, with the local slope varying 5.5× across the
  range — because the servo output drove the transdiode base directly and
  that base collapsed the open-loop gain from 112 to 3.2. A source-follower
  buffer on the servo output fixes it; the gain node is now high-Z and the
  follower supplies the base current.
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
