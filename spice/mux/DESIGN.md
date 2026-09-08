# Observation mux (2026-07-23)

## Principle: observe COPIES, never the signal path

Stealing a signal current for the pin would starve the consuming stage,
so every observable gets a **dedicated mirror copy leg** (cheap: one
W-ratioed transistor on an existing mirror gate line). The 8:1
pass-gate mux routes the selected *copy* to `ua[1]`; unselected copies
dump into a sink rail so their mirrors stay biased. The pin is read by
an SMU at virtual ground (current-mode), so pass-gate Ron (~1–2 kΩ,
g5v0 transmission gates) is irrelevant to accuracy.

## Channel map (mux select = cfg[194:192])

| ch | observable | copy source |
|---|---|---|
| 0 | iu monitor (1-unit leg) | pbias line — power-up default |
| 1 | PTAT core current | core mirror copy |
| 2 | test-cell exp branch (I ∝ e^u) | PMOS exp mirror extra leg |
| 3 | test-cell ln branch (I_pass) | NMOS sink mirror extra leg |
| 4 | test-cell output (+6 offset) | output-node copy |
| 5 | chain out_A (+6) | GB diode mirror copy |
| 6 | chain out_B (+6) | GC diode mirror copy |
| 7 | chain out_C (+6) = T reading | output copy |

All copies are unipolar by construction (offset/pedestal architecture),
so single-polarity mirrors suffice.

## Bench flow note

Every observable includes known static leg offsets (+6 outputs, +4
V→I offset, leg λ ~+10%); the bench software (descendant of
`toplevel/gen_chain.py` bookkeeping) subtracts calibrated values —
ch0/ch1 give the unit-current reference for ratiometric readout.
