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

Both are measured, not suspected, and both are described in detail in
[docs/info.md](docs/info.md):

- **The ln term is ~0.34 of nominal.** The cell computes approximately
  `exp(u) − 0.34·ln(v)`. The cause is servo gain: the transdiode base
  loads the servo amplifier and collapses its open-loop gain from 112 to
  3.2, so it cannot hold the transdiode collector still. This is a
  design-level limit present since the original schematic — it was never
  caught because every characterisation sweep held `v = 1`, which zeroes
  the ln term. The **exp path is correct** and behaves as designed.
- **Only the final output is observable.** With three analog pins there is
  no room for stage taps, so a wrong answer cannot be localised to CELL A,
  the coupling, or CELL B.

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
