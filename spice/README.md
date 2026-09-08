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

## Paths

The decks are committed **exactly as they were run**, so the `.lib` and
`.include` lines still carry absolute paths from the machine that ran them.
They are left unmodified on purpose: these are the artifacts the paper's numbers
came from, not a cleaned-up reissue. To run them elsewhere, repath first:

```sh
# from this directory. set PDK_ROOT to wherever your sky130A lives.
export PDK_ROOT=${PDK_ROOT:-$HOME/.ciel}
grep -rl '/Users/cteusche' . | while read f; do
  sed -i '' "s|/Users/cteusche/.ciel|$PDK_ROOT|g;
             s|/Users/cteusche/data/projects/eml/code/silicon|$(pwd)|g" "$f"
done
```

Simulated with ngspice and the sky130A model library. Two schematic bases exist
and must never be mixed within one quantity: the **segmented**-resistor netlist
carries the polysilicon scaling resistors as series strings and is the basis for
the transfer-function coefficients and the corner campaign; the **lumped**
netlist carries them as single bodies and is the basis for power, settling and
Monte Carlo. They differ by 4.31 % in resistance.
