# Figure scripts, revision 1

The scripts that draw the new and redrawn figures of the revised paper
(November 2026). Every number in a figure is read from its source file at run
time, and the scripts assert that the numbers they read are mutually
consistent.

| script | figure | reads |
|---|---|---|
| `gen_fig_overview.py` | Fig. 1, overview | the manuscript source (block-budget table, core energy) |
| `gen_fig_grammar.py` | Fig. 2, grammar | `sim/corpus/corpus_stats_exact.json`, `sim/bench/feynman_equations.json` |
| `gen_fig_topologies.py` | Fig. 3, topologies | `sim/eml_fabric_topo.py` (connection tables, parameter counts) |
| `gen_fig_cell.py` | Fig. 5, cell | `spice/char/emlcell_b_sim12.inc`; leg currents from the paper's power record |
| `gen_fig_depth.py` | Fig. 6, depth | `sim/results/scaling_run_AB.log`; chain swings from the paper's SPICE record |

Figs. 2 and 3 run from this repository alone. Figs. 1, 5 and 6 also read
files of the paper source that are not public (the simulation records
`POWER.md` and `FAB_SPICE.md`, and the manuscript); with those available, set
`EML_PAPER` to the directory that holds them. Without it, these three scripts
stop with a message saying which file is missing.

`paths.py` locates the inputs. Needs matplotlib and numpy; Fig. 5 also needs
pdflatex with circuitikz.
