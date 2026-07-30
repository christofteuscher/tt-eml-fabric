## How it works

This is an analog computing tile: a chain of two **EML cells**, each
computing `exp(u) − ln(v)` in current mode using translinear NPN loops
(the "single operator" of Odrzywołek's EML formulation).  Weighted
connections between cells are radix-4, all-unit-device current MDACs
(4 magnitude bits + sign per weight), and the whole fabric is biased from
an on-chip PTAT core with a 3-bit trimmed reference resistor.

The demonstration function is thermistor linearisation: with the weights
programmed, `out = a + b·ln(x)` over about 1.5 decades of input current
(measured in simulation: residual 1.1 % of span, monotonic).

Configuration is a 64-bit scan chain (3.3 V logic, `sky130_fd_sc_hvl`):

| bits | function |
|---|---|
| `[54:0]` | eleven 5-bit signed weights (2-cell build uses the first five: A.u, A.v, B.u, B.v, B.gamma) |
| `[57:55]` | observation-mux channel select (one of 8 internal currents to `mux_out`) |
| `[61:58]` | R_ptat trim (build uses 3 of 4 bits) |
| `[63:62]` | spare |

Each 5-bit weight is `w[4]` = sign, `w[3:0]` = magnitude m, value = m/4
(full scale ±3.75 in unit currents).  The chain is **latchless**: the
analog follows the shift register directly, so program first, then
measure — values wiggle harmlessly while a word shifts.

The three analog pins carry currents, not voltages: `x_in` sources the
input, `mux_out` sinks the selected observable into your meter, and
`iref_in` can override/augment the internal bias reference (the chip
self-biases; this pin is for characterisation).

## How to test

1. Power up (1.8 V digital + 3.3 V VAPWR).  Release `rst_n` — the config
   chain resets to a safe all-zero state (all weights off).
2. Shift 64 configuration bits into `ui[0]` (scan_data), clocked on the
   rising edge of `ui[1]` (scan_clk).  `uo[0]` (scan_out) echoes the
   chain 64 clocks later — shift 128 clocks and compare the second 64 to
   verify programming.
3. Drive `ua[0]` (x_in) with the input current: unit current is 0.5 µA,
   useful range roughly 0.1–6.5 µA.
4. Select an observation channel via bits `[57:55]` and measure the
   current at `ua[1]` (mux_out) with an SMU or transimpedance stage
   (channel currents are ~0.1–5 µA; unselected channels park on an
   internal dump rail so their mirrors stay biased).
5. Optionally trim the PTAT current via bits `[61:58]` (8 monotonic codes
   spanning ~127 % of design current; nominal at code 100) and observe
   the effect on any channel.

No clock is required beyond the scan clock you provide; the analog is
continuous-time.

## External hardware

A source-measure unit (or one current source + one current meter) for the
analog pins.  Everything else — bias, references, configuration — is
on-chip.
