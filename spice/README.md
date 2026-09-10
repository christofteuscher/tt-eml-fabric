# SPICE decks, netlists and post-layout extractions

These are the circuit-level sources behind the results in *What is a
universality theorem worth once someone has to build it? The composability cost
of an EML analog fabric*. **No device was fabricated.** Every number in that
paper is a simulator output on a netlist that LVS-matches the submitted layout,
or a quantity extracted from that layout.

| directory | holds |
|---|---|
| `cell/` | the EML cell. `cell/v3/eml_cell_v3b.inc` is the netlist the paper's transfer functions and non-ideality parameters come from |
| `char/` | characterisation decks: DC sweeps per port, step-settling, kick-response stability, the corner campaign |
| `bias/` | PTAT bias core and reference-resistor trim |
| `mdac/`, `mux/` | radix-4 signed current MDACs and the port multiplexing |
| `toplevel/` | the assembled two-cell chain |
| `extracted/` | post-layout netlists with parasitic R and coupling C, extracted in Magic after flattening. `emlcell_b_flat_rc.spice` is the single cell; `chainglue_flat_rc.spice` the two-cell assembly |

## Running these decks

The decks need the sky130A PDK. Point `PDK_ROOT` at the directory that
*contains* `sky130A` (a ciel or volare install puts it in `~/.ciel`, which is
the default if the variable is unset):

```sh
export PDK_ROOT=$HOME/.ciel
cd char && ngspice -b eml_layout_accuracy.spice
```

That is the whole setup. Every `.lib` line reads `$PDK_ROOT/sky130A/...`, which
ngspice expands, and every internal `.include` is relative to the deck that
contains it, which ngspice resolves against the deck's own directory rather than
your working directory. Decks therefore run from anywhere and on any machine
with a PDK.

Note that ngspice expands `$PDK_ROOT` but **not** `${PDK_ROOT}` — the braced
form silently fails to resolve. If you edit these decks, keep the bare form.

Simulated with ngspice and the sky130A model library. Two schematic bases exist
and must never be mixed within one quantity: the **segmented**-resistor netlist
carries the polysilicon scaling resistors as series strings and is the basis for
the transfer-function coefficients and the corner campaign; the **lumped**
netlist carries them as single bodies and is the basis for power, settling and
Monte Carlo. They differ by 4.31 % in resistance.
