* Signed weight MDAC -- one per programmable weight (4 per cell, 12 per chip).
*
* ==============================================================
* THIS FILE DESCRIBES THE 3-DIGIT THERMOMETER PART.
* THE SILICON IS THE 2-DIGIT BINARY PART -- mdac_weight_d2.inc.
* ==============================================================
*
* THE CHAIN LINEARISATION FIGURE CAME FROM THIS FILE, NOT FROM THE SILICON
* (marked 2026-08-16).  toplevel/chain_full.spice includes THIS file, and
* it is the source of "out_C = +0.419 - 0.059*ln(x), residual 0.0027 units
* rms (1.1 % of span)" as quoted in STATUS.md 3 and tt-eml-fabric
* docs/info.md.  That figure is UNVALIDATED for the shipped part: the deck
* is 3 cells with continuous geometry-ratioed mirror couplings, the die is
* 2 cells with the quantised 2-digit binary MDAC of mdac_weight_d2.inc.
* Do not treat "1.1 % of span" as a result for this chip.
*
* What is fabricated (ttsky26c) differs in TWO ways, and the second one
* changes a design GUARANTEE:
*
*   1. TWO digits, not three -- for area (26.6 -> 15.1 kum2 for the chip's
*      weights).  16 codes, LSB 1/4 unit, full scale 3.75.
*
*   2. Each digit is BINARY, not thermometer.  The layout ties switch 2's
*      gate to switch 1's line (gen_mdac2.py), so a digit reads t0*1 + t1*2
*      over the same 0..3 range.  It HAS to: cfgdig's 2-bit -> 3-line
*      thermometer decoder no longer exists -- the config output IS the
*      flop output, which is what let re-synthesis drop 82 decode gates --
*      so a third line could not be driven even if the layout had one.
*      What it bought was config routing: 30 -> 20 nets, "exactly the
*      cfgdig->MDAC corridor deficit" (gen_topnets.py).
*
* WHY (2) MATTERS.  The argument below -- "each digit is a 3-leg
* thermometer, so every digit is monotonic BY CONSTRUCTION" -- is
* topological, and it is correct FOR THIS FILE: a thermometer step only
* ever turns an additional leg ON, so mismatch changes how big a step is,
* never its sign.  Binary gives that up.  Its 1->2 step turns leg 0 OFF as
* legs 1+2 turn ON, so the step is a DIFFERENCE between matched-but-not-
* identical devices, and enough mismatch flips it negative.  Monotonicity
* stops being a guarantee and becomes a probability.
*
* MEASURED ON THE BINARY PART (char/mdac_d2_codes.spice, tt 27 C,
* vcasc 0.85 V, iref 0.5 uA, schematic level, no parasitics):
*   nominal, 16 codes  monotonic YES, DNL -0.139/+0.057 LSB, INL +-0.118,
*                      gain +1.73%.  The three worst steps are the
*                      INTER-DIGIT carries (codes 4/8/12, b rolling 3->0);
*                      the new intra-digit binary carry is only +0.057.
*   tt_mm, 70 samples  0/70 non-monotonic.  Worst-DNL distribution across
*                      samples: mean -0.276, sigma 0.190 LSB, worst
*                      observed -0.981.  FS sigma 3.26%.
* So the -1.0 limit sits ~3.8 sigma out.  DO NOT read that as 1-in-14000:
* -0.981 turned up ONCE IN 70 samples, where a clean Gaussian at that
* sigma would put it near 1 in 3800, so the tail is heavier than normal
* and the Gaussian number understates the risk.  70 samples cannot resolve
* a 1e-4 tail in either direction; what is established is that no sample
* was non-monotonic and that the margin is real but not large.
* Treat monotonicity as LIKELY, NOT GUARANTEED.  If the learning
* experiments show weight-update pathologies, suspect a reversed code at
* an inter-digit carry before suspecting the algorithm.
*
* The DNL/INL figures further down are for the 3-digit thermometer part at
* LSB = 1/16 unit.  They are NOT comparable to the above (LSB there is 1/4
* unit, 4x coarser) and they do not describe the silicon.
*
* RADIX-4, ALL-UNIT-DEVICE.  Three base-4 digits weighted 1, 1/4, 1/16:
*   value = (a + b/4 + c/16) units,  a,b,c in 0..3
* giving 64 magnitude codes, LSB = 1/16 unit, full scale 3.9375 units.
* 6 magnitude bits + sign = 7 of the 8 bits allocated per weight.  The
* 2-bit -> 3-line thermometer decode is done in the digital block, so the
* config chain still carries 8 plain bits.
*
* WHY NOT W/L RATIOING.  The obvious design -- one unit leg plus binary
* legs at W/L = 1/2, 1/4, 1/8, 1/16 -- was built and swept in ngspice over
* all 64 codes.  It is not usable: the legs deliver 0.088 / 0.187 / 0.473 /
* 0.688 units against 0.062 / 0.125 / 0.250 / 0.500 ideal (errors of
* +41 / +50 / +89 / +38 %), giving DNL of -6.3 .. +2.2 LSB and SEVEN
* non-monotonic codes.  Current does not scale with W/L across different
* geometries here -- narrow-width and channel-length effects dominate at
* these sizes.  Monotonicity is the binding requirement for in-situ
* learning (absolute gain error is absorbed by the two-point readout
* calibration), so ratioed geometry had to go.
*
* Every current source is therefore the SAME unit device, and the sub-unit
* weights come from dividing the REFERENCE instead: N parallel diodes fed
* by one unit device each carry 1/N of it, so a unit device on that gate
* carries 1/N.  Two cascaded /4 dividers give the 1/4 and 1/16 gates.
* Each digit is a 3-leg thermometer, so every digit is monotonic by
* construction and the carries are unit-device matched.
*
* vg is the top reference gate: `pbias` for an alpha weight (reference =
* iu from the global tree), or the local input diode for a gamma weight.
* For alpha weights the whole divider chain is shared across the cell.
*
* Unit device W=8 L=2 g5v0 (measured sigma ~2-3% at uA currents, mirror_mc).
*
* CASCODES ARE NOT OPTIONAL and their bias is the tightest constraint in
* the whole block.  Without them each mirror stage carries 20-30% Vds gain
* error and the base-4 carries go non-monotonic.  With them, vcasc trades
* static linearity against multiplying range, and the divided-reference
* digits are what break in both directions:
*
*   vcasc   monotonic   DNL      INL    FS err   1/4 digit over 0.5-3.4 uA
*    0.60      no(3)   -1.41    1.09    +4.7%    0.823 .. 0.772  (+6.6%)
*    0.80      no(3)   -1.05    0.81    +2.8%    0.799 .. 0.762  (+4.8%)
*    0.85      YES     -0.96    0.74    +2.3%    0.793 .. 0.764  (+3.9%)
*    0.90      YES     -0.88    0.67    +1.8%    0.788 .. 0.715  (+10.2%)
*    0.95      YES     -0.85    0.65    +1.6%    0.782 .. 0.494  (+58.2%)
*    1.00      YES     -0.70    0.53    +0.8%    0.777 .. 0.227  (collapses)
*    1.55       --      --       --       --     both fine digits = ZERO
*
* Static linearity keeps improving with vcasc while the multiplying range
* falls off a cliff -- at 1.0 V the fine digits look perfect on a fixed
* reference and deliver a quarter of their value at 2 uA.  The chain's
* internal node currents are 0.5-3.4 uA (chain_full.csv), so the block has
* to hold across that whole range.
*
* vcasc = 0.85 V.  Generated on-chip (~vdd/4): a diode stack or a tap off
* the rail divider in the bias block.  NOTE: at 1.55 V -- the natural first
* guess for a 3.3 V rail -- both fine digits deliver exactly zero while the
* layout looks perfectly healthy and the weight silently degrades to 2-bit
* resolution.  This value is not free to round.
*
* MEASURED at vcasc = 0.85 V:
*   all 64 codes, tt 27 C, 0.5 uA reference:
*     monotonic YES, DNL -0.96 LSB, INL 0.74 LSB, full scale +2.3%
*   multiplying gain, coarse digit, 0.1-5 uA input: flat to +1.4%
*   output compliance: flat from 0.3 V to 1.9 V at every current level
*   (gain error is absorbed by the two-point readout calibration; only
*   monotonicity and the multiplying flatness actually bind)

.subckt mdac_div vin vout vcasc vdd VSUB
XSRC nsc vin vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=2
XSCC nd vcasc nsc vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=1
XN0 nd nd VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=2
XN1 nd nd VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=2
XN2 nd nd VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=2
XN3 nd nd VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=2
XNO npc nd VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=2
* the PMOS diode is cascoded too, so the gate it produces is referenced to
* the same Vds the legs will see -- otherwise every mirror stage carries a
* ~20-30% gain error and the digit carries go non-monotonic
XPCC npc vcasc vout vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=1
XPD vout vout vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=2
.ends

* ---- one radix-4 digit: 3 thermometer legs off gate vg ----
.subckt mdac_digit vg nsum vcasc vdd VSUB t0 t1 t2
XL0 s0 vg vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=2
XL1 s1 vg vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=2
XL2 s2 vg vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=2
XK0 n0 vcasc s0 vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=1
XK1 n1 vcasc s1 vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=1
XK2 n2 vcasc s2 vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=1
XS0 nsum t0 n0 VSUB sky130_fd_pr__nfet_g5v0d10v5 W=4 L=0.5
XS1 nsum t1 n1 VSUB sky130_fd_pr__nfet_g5v0d10v5 W=4 L=0.5
XS2 nsum t2 n2 VSUB sky130_fd_pr__nfet_g5v0d10v5 W=4 L=0.5
.ends

.subckt mdac_weight vg iout_p iout_n vcasc vdd VSUB
+ a0 a1 a2 b0 b1 b2 c0 c1 c2 sgn sgnb
XDIV4  vg  vg4  vcasc vdd VSUB mdac_div
XDIV16 vg4 vg16 vcasc vdd VSUB mdac_div
XDA vg   nsum vcasc vdd VSUB a0 a1 a2 mdac_digit
XDB vg4  nsum vcasc vdd VSUB b0 b1 b2 mdac_digit
XDC vg16 nsum vcasc vdd VSUB c0 c1 c2 mdac_digit
* ---- sign steering: direct path adds, mirror path subtracts ----
* W=4: shares the strip with the nine digit switches (see mdac_alpha)
XSP nsum sgn iout_p VSUB sky130_fd_pr__nfet_g5v0d10v5 W=4 L=0.5
XSN nsum sgnb nmir VSUB sky130_fd_pr__nfet_g5v0d10v5 W=4 L=0.5
* W=8, not W=16: measured -4.0302 vs -4.0334 units at full scale on the
* negative path (0.08% apart), and W=8 lets the mirror share a layout band
* with the switch row instead of taking one of its own.
XMD nmir nmir VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=2
XMO iout_n nmir VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=2
.ends

* ---- gamma wrapper: a MULTIPLYING DAC whose reference is an input current
* Converts I_in to a gate voltage with a cascoded unit diode, so the legs
* see the same structure the dividers were characterised with.  alpha
* weights skip this and drive vg from the global `pbias` line instead,
* which also lets all alpha weights share one divider chain chip-wide.
.subckt mdac_gamma iin iout_p iout_n vcasc vdd VSUB
+ a0 a1 a2 b0 b1 b2 c0 c1 c2 sgn sgnb
XIC iin vcasc nid vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=1
XID nid vg vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=2
VTIEG vg iin 0
XW vg iout_p iout_n vcasc vdd VSUB
+ a0 a1 a2 b0 b1 b2 c0 c1 c2 sgn sgnb mdac_weight
.ends

* ---- alpha variant: reference comes from the global pbias tree, so the
* divider chain is shared chip-wide and this block has none.  vg/vg4/vg16
* arrive as pins.  XDUM is the layout's odd-leg dummy, held off with gate
* and drain on vdd; it is here so the reference matches the layout.
.subckt mdac_alpha vg vg4 vg16 iout_p iout_n vcasc vdd VSUB
+ a0 a1 a2 b0 b1 b2 c0 c1 c2 sgn sgnb
XDA vg   nsum vcasc vdd VSUB a0 a1 a2 mdac_digit
XDB vg4  nsum vcasc vdd VSUB b0 b1 b2 mdac_digit
XDC vg16 nsum vcasc vdd VSUB c0 c1 c2 mdac_digit
* The dummy is a real CASCODED PAIR in the layout -- source device and
* cascode in series with a mid node between them -- not two devices with
* every terminal shorted to vdd.  Modelling it the lazy way put 8 pins on
* vdd where the layout has 6, and no mid node at all.
XDUMs ndum vdd vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=2
XDUMc vdd vdd ndum vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=1
* W=4: the sign switches ride the same strip as the nine digit switches,
* and for a DC-programmed steering switch the width is irrelevant --
* W=4 L=0.5 carrying a few uA drops single-digit mV.
XSP nsum sgn iout_p VSUB sky130_fd_pr__nfet_g5v0d10v5 W=4 L=0.5
XSN nsum sgnb nmir VSUB sky130_fd_pr__nfet_g5v0d10v5 W=4 L=0.5
XMD nmir nmir VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=2
XMO iout_n nmir VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=2
.ends
