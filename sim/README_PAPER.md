# Behavioral simulation code and benchmark harness

The Tier-1 evidence behind *What is a universality theorem worth once someone
has to build it? The composability cost of an EML analog fabric*: a
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
