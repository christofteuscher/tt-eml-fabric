# Behavioral simulation code and benchmark harness

The Tier-1 evidence behind *Composability rather than computation sets the
cost of an analog EML fabric*: a
differentiable model of the EML network in PyTorch, evaluated in double
precision, into which hardware-derived non-idealities enter as explicit
forward-model terms.

| path | holds |
|---|---|
| `eml_fabric_sim.py`, `eml_fabric_topo.py` | the network model and its topologies |
| `bench/` | the benchmark harness, the AI Feynman transcription and the thermistor task |
| `limits/` | the energy analysis. `energy_floor.py` produces the composability overhead; `constants_sensitivity.py` produces the 72-corner box and Figure 5 |
| `ml/`, `ode/`, `operators/`, `extend/` | regression, closed-loop dynamics, operator variants and the third-port study |
| `physical/`, `ratio/`, `energy/` | non-ideality parameters, port-ratio and energy studies |
| `ratio/run_elm.py` | the random-feature (ELM) study: interior frozen, ridge readout |
| `results/` | derived datasets |
| `test_*.py` | fixed-seed regression tests |

`RESULTS.md` and `RESULTS_SCALING.md` are the printed records.

## Note on `constants_sensitivity.py`

`E_CORE_7` was corrected on 2026-09-05. It previously charged seven bare cores
one settling time each while the fabric term charges all seven cells the full
three-stage chain latency; mixing those conventions inflated the
primitive-versus-digital ratio and the seven-cell overhead by exactly the stage
count. The old value is retained as `E_CORE_7_ONESETTLE`. The paper's headline
per-cell overhead is unaffected, both of its terms being one device settling
once.

Set `PDK_ROOT` before anything that shells out to ngspice; `limits/bias_sweep.py`
finds the characterisation decks relative to the repository, or from
`EML_CHAR_DIR` if you keep them elsewhere.

numpy and torch here need an arm64 interpreter on Apple silicon.

## The random-feature (ELM) study

Added 2026-09-10. Every other benchmark here trains all of the fabric's
weights and requires each interior cell to hold a particular value.
`ratio/run_elm.py` removes that requirement: the interior weights are drawn
once and frozen, every cell output is a feature, and only a linear readout is
fitted, by ridge regression with the penalty chosen by generalised
cross-validation.

**It is an extreme learning machine, not a reservoir.** The fabric is
feedforward and has no fading memory; the recurrence in the closed-loop column
belongs to the ODE, not to the device.

Everything except the fitting rule is imported from `run_ratio.py` rather than
reimplemented -- the same 16 systems, initial conditions, training box, 768
samples, closed-loop substitution, blow-up guard and NRMSE definitions -- so
the rows pool with `results/ratio_all.json` and are scored by the same
criterion. `run_ratio.py` itself is unchanged.

| script | produces |
|---|---|
| `ratio/run_elm.py` | `results/elm.json`, 224 rows: frozen fabric at 4 cell counts x 3 hw configs, the layer-0 control, and a tanh ELM baseline |
| `ratio/run_ratio_silicon.py` | `results/ratio_silicon.json`, the trained x silicon cell that the published study never ran |
| `ratio/summarise_elm.py` | `results/elm_summary.txt`, all of it scored |
| `ratio/test_elm_headline.py` | recomputes every ELM number the paper states and exits non-zero on drift; needs no torch and runs in about a second |

To reproduce from scratch:

    cd sim/ratio
    python3 run_elm.py --seeds 5
    python3 run_ratio_silicon.py --seeds 3 --iters 3000
    python3 summarise_elm.py > results/elm_summary.txt
    python3 test_elm_headline.py --verbose

The first takes a few minutes and the second about ten.

### Two results that are easy to misread

**The headline is the 2x2, not the win counts.** The extracted non-idealities
cost the trained fabric 2.56x on pointwise fit and 1.92x in closed loop, and
cost the frozen fabric 0.95 and 0.99 -- nothing. The same silicon is expensive
when interior values must mean something and free when they need only be
repeatable. That comparison contains no energy model, no digital baseline and
no node-scaling factor.

**Freezing is not what makes the frozen fabric better.** It beats the trained
fabric by roughly an order of magnitude at matched cells, but it also reads
every cell where the trained fabric reads only layer 0. The `elm0_*` rows hold
the readout fixed and isolate the training effect: the two come out level,
median ratios 0.82--1.95, the frozen variant winning 4 to 10 of 16. Gradient
descent through the behavioural model is therefore **not** what limits the
trained fabric, and the paper's median 21.5x is not an optimisation artifact.
An earlier reading of these runs said otherwise and was wrong;
`test_elm_headline.py` pins the correction so it cannot silently revert.
