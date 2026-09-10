* TWO-DIGIT (radix-4) weight variant -- reduced precision, for area.
*
* Same architecture as mdac_weight.inc, with the 1/16 digit removed:
*   value = (a + b/4) units,  a,b in 0..3
* 16 magnitude codes, LSB = 1/4 unit, full scale 3.75 units.
* 4 magnitude bits + sign instead of 6 + sign.
*
* WHY: the 3-digit block does not fit three cells on the die.  Measured
* (gen_mdac2.py, NDIG=2 vs 3):
*   alpha  39.1 x 59.2 = 2.31 kum2  ->  39.1 x 36.3 = 1.42 kum2
*   gamma  53.6 x 59.2 = 3.17 kum2  ->  27.9 x 59.2 = 1.65 kum2
* i.e. 26.6 -> 15.1 kum2 for the chip's ten weights.  The saving is
* larger than the leg count suggests because dropping the digit also
* drops a whole PMOS row from alpha and an entire /4 divider stage from
* gamma -- the 1/16 gate needs a second divider that nothing else uses.
*
* COST: 16 levels per weight instead of 64.  Whether 4 bits of weight
* resolution is enough for the learning task is a fabric_sim question, NOT
* a circuit question, and has not been answered here.
*
* THE MONOTONICITY CLAIM THAT USED TO SIT HERE WAS WRONG BY 2026-08-12.
* It read "Monotonicity is unaffected (each digit is still a 3-leg
* thermometer, still all-unit-device)".  The digit is no longer a
* thermometer: switch 2's gate is tied to switch 1's line, so the digit
* reads t0*1 + t1*2 and the 1->2 step turns leg 0 OFF as legs 1+2 turn ON.
* Under thermometer, monotonicity is TOPOLOGICAL -- a step only ever adds a
* leg, so mismatch changes how big the step is, never its sign.  Under
* binary it is STATISTICAL: the step is a difference between matched-but-
* not-identical devices, and a large enough mismatch flips it negative.
* That is a real guarantee downgraded to a probability, and it was bought
* to save config routing (30 -> 20 nets, "exactly the cfgdig->MDAC corridor
* deficit" -- gen_topnets.py).  Measured numbers: see char/mdac_d2_codes.spice.
*
* Unit device and cascode bias (vcasc = 0.85 V) carry over unchanged from
* mdac_weight.inc.  The DNL/INL figures there do NOT: they were measured on
* the 3-digit thermometer part and are not valid for this circuit.

.subckt mdac_div vin vout vcasc vdd VSUB
XSRC nsc vin vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=2
XSCC nd vcasc nsc vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=1
XN0 nd nd VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=2
XN1 nd nd VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=2
XN2 nd nd VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=2
XN3 nd nd VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=2
XNO npc nd VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=2
XPCC npc vcasc vout vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=1
XPD vout vout vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=2
.ends

* BINARY, NOT THERMOMETER (2026-08-12) -- this is what is on the die.
* gen_mdac2.py ties switch 2's gate to switch 1's line, so the digit reads
* t0*1 + t1*2 over the same 0..3 range using three IDENTICAL unit devices
* grouped 1+2.  cfgdig's thermometer decoder no longer exists (it was
* deleted when the config output became the flop output), so a third line
* could not be driven even if the layout had one.  NOTE this is NOT the
* ratioed binary rejected in mdac_weight.inc -- that failure came from
* W/L-scaled legs; every leg here is still W=8 L=2.
.subckt mdac_digit vg nsum vcasc vdd VSUB t0 t1
XL0 s0 vg vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=2
XL1 s1 vg vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=2
XL2 s2 vg vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=2
XK0 n0 vcasc s0 vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=1
XK1 n1 vcasc s1 vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=1
XK2 n2 vcasc s2 vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=1
XS0 nsum t0 n0 VSUB sky130_fd_pr__nfet_g5v0d10v5 W=4 L=0.5
XS1 nsum t1 n1 VSUB sky130_fd_pr__nfet_g5v0d10v5 W=4 L=0.5
XS2 nsum t1 n2 VSUB sky130_fd_pr__nfet_g5v0d10v5 W=4 L=0.5
.ends

* ---- alpha: both reference gates arrive as pins from the shared chain.
* NO dummy leg: with two digits the leg count is even (6), so unlike the
* 3-digit block the layout has no odd leg to pad.
.subckt mdac_alpha_d2 vg vg4 iout_p iout_n vcasc vdd VSUB
+ a0 a1 b0 b1 sgn sgnb
XDA vg  nsum vcasc vdd VSUB a0 a1 mdac_digit
XDB vg4 nsum vcasc vdd VSUB b0 b1 mdac_digit
XSP nsum sgn iout_p VSUB sky130_fd_pr__nfet_g5v0d10v5 W=4 L=0.5
XSN nsum sgnb nmir VSUB sky130_fd_pr__nfet_g5v0d10v5 W=4 L=0.5
XMD nmir nmir VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=2
XMO iout_n nmir VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=2
.ends

* ---- gamma: carries its own /4 divider (one stage now, not two).
* As in the 3-digit block, the input diode that turns I_in into vg is NOT
* part of this cell -- `vg` is a pin and the diode lives outside.
.subckt mdac_gamma_d2 vg iout_p iout_n vcasc vdd VSUB
+ a0 a1 b0 b1 sgn sgnb
XDIV4 vg vg4 vcasc vdd VSUB mdac_div
XDA vg  nsum vcasc vdd VSUB a0 a1 mdac_digit
XDB vg4 nsum vcasc vdd VSUB b0 b1 mdac_digit
XSP nsum sgn iout_p VSUB sky130_fd_pr__nfet_g5v0d10v5 W=4 L=0.5
XSN nsum sgnb nmir VSUB sky130_fd_pr__nfet_g5v0d10v5 W=4 L=0.5
XMD nmir nmir VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=2
XMO iout_n nmir VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=2
.ends
