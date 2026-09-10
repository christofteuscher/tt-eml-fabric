# Depth and topology scaling of the analog EML fabric

Run 2026-08-07. Code: `eml_fabric_topo.py` (core), `run_scaling.py`,
`run_supplement.py`, `test_topo.py`, `make_figure.py`.
Raw data: `results/scaling_full.json`, `results/supplement.json`,
logs `results_full.log`, `results_C.log`, `results_supp.log`.
Figure: `results/fig_scaling.pdf`.

All errors are RMSE over the training range, median and best over 3 seeds.
Thermistor errors in Kelvin over the 80 K span; `osc_k3` in target units
(target RMS 0.690, so 0.69 means the fit explains nothing).

The "PDK chip" config throughout is the **corrected** one:
gain sigma 0.03 (not the 0.02 assumed in `fabric_sim` run 3), offset sigma
0.005, noise 3e-3, sat 30, 8-bit weights.

---

## What changed in the simulator

`AnalogEMLTree` is unchanged and still passes; the new `AnalogEMLFabric`
reproduces it to 0 ulp at depths 1-5 under both ideal and full-non-ideality
configs, so nothing in the existing `RESULTS.md` is invalidated.

Three differences:

Connectivity is a per-layer gather table rather than a hardwired heap
index, so `tree`, `dag` (constant width, full fan-in, subexpressions
shared) and `mesh` (constant width, local fan-in window) are one code path
with different index tensors.

Cells are evaluated a layer at a time instead of one at a time. At depth 8
this is 9.5 ms/iter against 188 ms/iter for the legacy class, about 20x.
Depth 10, 1023 cells, is 78 s per 3000-iteration run, which is what makes
the study possible at all on two cores.

A unity-gain initialisation replaces `randn * 0.7`. Derivation and the two
failure modes that had to be fixed are in the module docstring.

---

## A. The depth-4 turnover was the optimiser, not the fabric

`RESULTS.md` run 1 reported depth-3 best and depth-4 worse, annotated
"no gain, harder optimisation". That reading was right, and the effect is
larger than it looked. Extending the legacy init to depth 10 on ideal
hardware:

| depth | 1 | 2 | 3 | 4 | 6 | 8 | 10 |
|---|---|---|---|---|---|---|---|
| cells | 1 | 3 | 7 | 15 | 63 | 255 | 1023 |
| legacy init | 2.189 | 0.726 | **0.535** | 0.602 | 0.741 | 2.193 | 19.13 |
| unity-gain | 0.098 | 0.076 | 0.014 | 0.010 | 0.014 | **0.009** | 0.511 |

Per-layer output RMS at initialisation says why. The legacy init is already
railing against `sat` at depth 3:

| depth | scheme | layer 0 | mid | deepest |
|---|---|---|---|---|
| 3 | legacy | 2.0e+01 | 3.7e+11 | 9.5e+01 |
| 3 | unity-gain | 1.1e+00 | 9.9e-01 | 7.6e-01 |
| 10 | legacy | 1.9e+01 | 8.1e+11 | 1.1e+05 |
| 10 | unity-gain | 6.4e-01 | 6.1e-01 | 3.6e-01 |

Adam recovers from that at depth 3 and stops recovering at depth 4. It is
an initialisation pathology, not a statement about what the fabric can
represent.

### On the realistic chip

The same comparison at identical hardware config, identical iteration
budget (4000), thermistor Steinhart-Hart:

| depth | 3 | 4 | 6 | 8 |
|---|---|---|---|---|
| legacy init, PDK | 5.337 | 5.453 | 2.778 | 6.237 |
| unity-gain, PDK | **0.162** | **0.134** | **0.138** | **0.225** |

A factor of 33 at median from initialisation alone, on strictly harder
hardware than run 3 assumed. For reference the legacy `AnalogEMLTree` class
on this same data and config gives 8.10 median / 2.75 best at depth 3,
consistent with the 3.8 / 0.86 in run 3 given the corrected gain sigma.

**This changes the paper's realistic-chip number.** Run 2's "qualified GO"
rested on sub-1 K being reachable only in the best seed of 8. Sub-0.2 K is
now the median at depth 3-6, and the restart budget stops being load-bearing
for the calibration claim.

### What depth actually buys

On the thermistor the answer is nothing beyond depth 3-4: the curve flattens
at ~0.01 K ideal and ~0.14 K on the PDK chip, which is far below any
physically meaningful thermistor accuracy. The honest statement is that
extra depth does not *hurt* once the init is fixed, not that it helps.

On `osc_k3` (= sin(3 ln x), not exactly representable in a real-valued
fabric) depth does buy accuracy, and the median/best split is informative:

| depth | 1 | 2 | 3 | 4 | 6 | 8 | 10 |
|---|---|---|---|---|---|---|---|
| median | 0.644 | 0.359 | 0.158 | 0.127 | 0.251 | 0.357 | 0.638 |
| best of 3 | 0.644 | 0.354 | 0.131 | **0.049** | **0.027** | 0.339 | 0.276 |

Median turns over at depth 4 while best keeps improving to depth 6. Beyond
that the optimiser loses even the best seed. So restart-and-select is still
the operative technique at large cell counts, exactly as run 2 concluded,
but the crossover has moved from depth 3 to roughly depth 6.

### A capability ceiling worth reporting

`sin(5 ln x)` and `sin(8 ln x)` are not learned at any depth tried, by any
init, at any budget: RMSE stays at 0.61-0.68 against target RMS 0.71, i.e.
the fit explains essentially nothing. The cliff between k=3 and k=5 is
sharp. This is consistent with Odrzywolek's trigonometric construction
requiring complex intermediates, which a real-valued analog fabric cannot
provide. It is a clean limitation to state rather than to discover in
review.

---

## B. Error accumulation with depth, no training involved

Freeze one weight set, run it on an ideal chip and on a mismatched chip,
measure relative RMS divergence at the output. This isolates the device
physics from anything the optimiser does.

| gain sigma | d=1 | d=2 | d=3 | d=4 | d=6 | d=8 | d=10 |
|---|---|---|---|---|---|---|---|
| 1 % | 1.09e-2 | 6.18e-3 | 7.21e-3 | 7.57e-3 | 8.75e-3 | 9.87e-3 | 1.08e-2 |
| 3 % | 3.23e-2 | 1.79e-2 | 2.09e-2 | 2.18e-2 | 2.55e-2 | 2.95e-2 | 3.29e-2 |
| 10 % | 1.04e-1 | 5.31e-2 | 6.12e-2 | 6.57e-2 | 1.18e-1 | 2.14e-1 | 4.57e+11 |

Fitting error ~ d^p from depth 2 upward:

    p(1 %)  = ln(1.080/0.618) / ln 5 = 0.35
    p(3 %)  = ln(3.288/1.793) / ln 5 = 0.38
    p(10 %) = ln(2.138/0.531) / ln 4 = 1.01

Two regimes. At and below the corrected 3 %, error accumulates as roughly
d^0.38, *slower* than the sqrt(d) of independent per-stage errors, because
a unity-gain cell averages its children and leaf errors partly cancel.
Going from 7 cells to 1023 cells costs 57 % more output error, not 12x.
At 10 % accumulation is linear in depth and then diverges outright past
depth 8, railing against `sat`.

The paper sentence: the corrected 3 % mirror mismatch does not by itself
limit fabric depth. The instability threshold lies between 3 % and 10 %
and locating it is a cheap follow-up.

Caveat for methods, not to be buried: sub-sqrt(d) scaling is a property of
the unity-gain regime the fabric is initialised into. A configuration with
per-cell gain well above 1 compounds differently.

---

## C. Topology

Corrected-PDK chip, 3000 iterations, 3 seeds. Thermistor Steinhart-Hart:

| topology | depth | width | cells | params | median | best |
|---|---|---|---|---|---|---|
| tree | 4 | - | 15 | 92 | 0.129 | 0.127 |
| DAG | 4 | 4 | 16 | 173 | 0.369 | 0.157 |
| mesh | 4 | 4 | 16 | 149 | 0.089 | 0.046 |
| DAG | 4 | 8 | 32 | 537 | 1.635 | 0.209 |
| mesh | 4 | 8 | 32 | 297 | **0.044** | **0.033** |
| tree | 6 | - | 63 | 380 | 0.278 | 0.173 |
| DAG | 6 | 8 | 48 | 857 | 0.663 | 0.211 |
| mesh | 6 | 8 | 48 | 457 | 0.170 | 0.107 |
| DAG | 6 | 10 | 60 | 1271 | 0.489 | 0.414 |
| mesh | 6 | 10 | 60 | 571 | 0.087 | 0.052 |
| tree | 8 | - | 255 | 1532 | 0.213 | 0.105 |
| DAG | 8 | 8 | 64 | 1177 | 5.191 | 1.907 |
| mesh | 8 | 8 | 64 | 617 | 0.349 | 0.150 |
| DAG | 8 | 32 | 256 | 15457 | 10.503 | 8.611 |
| mesh | 8 | 32 | 256 | 2465 | 4.490 | 0.348 |

On the sensor curve the ordering is mesh < tree < DAG, and it is not close.
A 32-cell depth-4 mesh reaches 0.044 K against 0.213 K for a 255-cell
depth-8 tree: 5x better accuracy on one eighth the cells. Since local
nearest-neighbour routing is also the cheapest thing to lay out, the
architectural recommendation and the silicon-cost recommendation agree,
which is a convenient result.

Full fan-in DAG is consistently worst and degrades as width grows. With
F = width the unity-gain split makes each connection weight 1/(2F) while
the exp-path coefficient scales as 1/(2F e0), and the parameter count grows
as width squared with no corresponding gain in expressible functions,
because all cells in a layer see identical inputs.

**The ordering reverses on the oscillatory target.** For `osc_k3` the tree
wins (0.313 / 0.354 / 0.319 at depths 4/6/8) and mesh and DAG sit at
0.46-0.68, i.e. near-total failure. A tree's disjoint subtrees produce more
diverse features than a constant-width layer where every cell sees the same
inputs. So the recommendation is target-dependent and should be stated that
way: local mesh routing for smooth calibration-style targets, tree
structure where feature diversity matters more than cell efficiency.

---

## Threats to validity

Gradient training through the non-ideal forward model remains a proxy for
hardware in-situ training (SPSA and friends), and `rail_leak = 0.02` is
where that proxy is most optimistic. Unchanged from the earlier runs.

Three seeds. Medians over three are noisy; the median/best splits above are
directional, not precise.

The single scalar input means layer-0 features are ~0.999 correlated in any
constant-width topology, because smooth functions of one variable are
mutually correlated almost by construction. The readout is ridge-regularised
(lambda = 1e-6 relative) to keep this from producing enormous cancelling
coefficients. Plain least squares gave readout weights of 5e4 and fabric
outputs of 2349 K on a 298 K target. Multivariate inputs would change this
picture and are not implemented.

Schematic-level device numbers throughout, as everywhere else in this
project.

---

## Suggested next runs

Locate the stability threshold between 3 % and 10 % gain sigma (experiment
B at sigma = 0.04, 0.05, 0.07). Cheap, no training, and it converts
"somewhere between" into a number.

Re-run the mesh topology at depth 4-6 with more seeds. It is the best
configuration found and rests on 3 seeds.

Multivariate input. Everything above is a 1-D approximation study, which is
the real limit on what this fabric-scale claim can currently say.
