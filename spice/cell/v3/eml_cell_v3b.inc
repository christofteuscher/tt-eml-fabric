* OTA CURRENT SOURCES SHRUNK (2026-07-26) -- netlist follows the layout.
* Tails W32L8 -> W16L4 and ota2b's XMS W48L8 -> W16L2.67, both at CONSTANT
* W/L so the bias currents are unchanged.  Measured before committing:
*   tail: input-referred offset sigma 3.70 mV vs 3.43 baseline (1.08x) and
*         follower error identical to three digits -- tail mismatch is
*         COMMON to both pair legs, so it barely refers to the input
*         (char/ota_shrink_mc.spice, char/ota_shrink_dc.spice)
*   XMS:  DC gain 10442 -> 13177, follower error -0.61 -> -0.53 mV, because
*         XMN3 is L=1 and already dominates ro(XMN3)||ro(XMS)
*         (char/ota2b_shrink.spice)
* The INPUT PAIR is untouched: it sets offset, and offset is the binding
* mismatch term in this system.
* emlcell_b: v3 cell with ALL bias currents from the pbias PMOS line
* (W ratio = current ratio; diode leg W=8 <=> 2 uA = 4 units).
* OTA variants take pbias for their tails / 2nd-stage loads.

.subckt ota1b inp inn out vdd pbias
XMT ntail pbias vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=16 L=4
XMP1 n1  inp ntail vdd sky130_fd_pr__pfet_g5v0d10v5 W=32 L=2
XMP2 out inn ntail vdd sky130_fd_pr__pfet_g5v0d10v5 W=32 L=2
XMN1 n1  n1 0 0 sky130_fd_pr__nfet_g5v0d10v5 W=4 L=2
XMN2 out n1 0 0 sky130_fd_pr__nfet_g5v0d10v5 W=4 L=2
.ends

.subckt ota1vb inp inn out vdd vss pbias
XMT ntail pbias vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=16 L=4
XMP1 n1  inp ntail vdd sky130_fd_pr__pfet_g5v0d10v5 W=32 L=2
XMP2 out inn ntail vdd sky130_fd_pr__pfet_g5v0d10v5 W=32 L=2
XMN1 n1  n1 vss 0 sky130_fd_pr__nfet_g5v0d10v5 W=4 L=2
XMN2 out n1 vss 0 sky130_fd_pr__nfet_g5v0d10v5 W=4 L=2
* NO OUTPUT BUFFER.  A source follower (XMSF W16 L1 + XMBM W4 L8 sink off
* n1) was added on 2026-08-13 and REVERTED: it makes the ln servo loop
* oscillate -- ~7.2 MHz in schematic, 5.8 MHz post-layout, up to 3.5x the
* signal amplitude at v=4, confirmed under Gear-2 integration and by active
* perturbation.  Parasitics reduce the amplitude but do not stop it.
*
* The defect it was built to fix was not real.  The "slope -0.34 varying
* 5.5x" figure came from schematic benches that drive nv with v*500 nA
* against a 500 nA reference, so their ln argument is exactly v.  The
* LAYOUT generates its bias legs internally off pbias (XLPA puts 936 nA on
* nv, XLPB_LVR references 1394 nA), so the die's argument is offset and
* must be fitted against ln(v + s) with s free.  Fitted that way the
* UNBUFFERED cell measures 2.549 - 1.145*ln(v + 2.574).
*
* RESIDUAL CORRECTED 2026-08-19.  This comment used to claim "max residual
* 0.00023 units".  That number is the HAND nominal's advertised error, not
* its actual one: re-measured against the real sweep points the fit above
* deviates by up to 6.83e-4 units, ~3x looser than advertised.  The exp
* fit is off the same way -- 1.101*exp(0.927*u) - 0.010 deviates 5.73e-4,
* advertised 4.0e-4.  Two independently written least-squares fits agree
* with each other to 0.00% while both sit 0.5-0.9% off these hand values,
* so the discrepancy belongs to the hand nominal -- probably a minimax
* rather than least-squares criterion, compounded by the k/s correlation.
* NOTHING DOWNSTREAM CHANGES: 6.83e-4 is still 14x inside the 0.01-unit
* limit, and the coefficients themselves are unaffected.  Do not re-fit on
* account of this.  (paper/CHARACTERISATION.md section on the tt/27 nominal.)
*
* These coefficients are on the LUMPED resistor basis (the LVS reference
* netlist, one R per path).  The SEGMENTED basis -- 4x L=11.44, which is
* what the die actually draws -- gives 2.478 - 1.094*ln(v + 2.547), about
* 4% away.  Quote the basis whenever you quote the numbers.
*
* See the warning headers in char/_v2d_*.inc and use
* char/emlcell_b_sim12.inc for anything describing the chip.
.ends

.subckt ota2b inp inn out vdd pbias
XMT ntail pbias vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=16 L=4
XMP1 n1  inp ntail vdd sky130_fd_pr__pfet_g5v0d10v5 W=32 L=2
XMP2 no1 inn ntail vdd sky130_fd_pr__pfet_g5v0d10v5 W=32 L=2
XMN1 n1  n1 0 0 sky130_fd_pr__nfet_g5v0d10v5 W=4 L=2
XMN2 no1 n1 0 0 sky130_fd_pr__nfet_g5v0d10v5 W=4 L=2
XMN3 out no1 0 0 sky130_fd_pr__nfet_g5v0d10v5 W=16 L=1
XMS out pbias vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=16 L=2.67
CC no1 out 2p
.ends

.subckt emlcell_b nu nv out vdd vrefb ve pbias
.param iu=0.5u
.param nvt=26.9m

* exp path
XLR1 nb0 pbias vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=4 L=8
* ----------------------------------------------------------------------
* mult=8 ON THE X-CARD(S) BELOW IS INERT -- IT IS NOT A DEVICE MULTIPLIER.
* ngspice SILENTLY ignores `mult=` on a subcircuit call; only `m=` works.
* Measured 2026-08-16, one sky130_fd_pr__npn_05v5_W1p00L1p00 at Vc=1.0 /
* Vb=0.75, .op, collector current vs the un-annotated card:
*     mult=8 -> ratio 1.000000   (ignored, and with NO warning printed)
*     m=8    -> ratio 8.000000   (honoured)
* So every number ever produced in this tree was computed with 1x
* transdiodes, not 8x.
*
* DO NOT "FIX" THIS TO m=8.  The LAYOUT is 1x per transdiode too:
* char/emlcell_b_sim12.inc -- the netlist that LVS-matches the shipped
* layout/emlcell2.gds -- carries these same NPNs with no multiplier at
* all.  Simulation and silicon therefore AGREE today, and there is no bug
* to fix.  Changing mult= to m= here would CREATE an 8x sim/silicon
* mismatch that does not currently exist.  The annotation records an
* INTENT that reached neither the netlist nor the mask; if 8x is wanted,
* change the LAYOUT first and the netlist with it.
* ----------------------------------------------------------------------
XQR nb0 nb0 0 0 sky130_fd_pr__npn_05v5_W1p00L1p00 mult=8
RU  vb2 nu {nvt/iu}
CFU vb2 nu 1p
XOT nu nb0 vb2 vdd pbias ota2b
XQ2 nc2 vb2 0 0 sky130_fd_pr__npn_05v5_W1p00L1p00 mult=8
XMPM1 nc2 nc2 vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=2
XMPM2 mpo nc2 vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=2
VSPM mpo out 0

* ln path (2-unit pedestals, base-driven transdiodes, VE-ref OTAs)
XLPA nv pbias vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=8
XQA nv oa ve 0 sky130_fd_pr__npn_05v5_W1p00L1p00 mult=8
XOA nv vrefb oa vdd ve pbias ota1vb
* CFA/CFB reduced 2p -> 1p: compensation reduced after measuring
* no ringing at 1p and clean settling at 0.5p across tt/ff/ss x
* -20/60 C (2x margin).  Costs +8% noise at the loop node.  This
* is what lets the matched pair share one strip column.
CFA nv oa 1p
RSA nv vrefb 100k
XLPB nvb pbias vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=8
XLVR nvb pbias vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=4 L=8
XQB nvb ob ve 0 sky130_fd_pr__npn_05v5_W1p00L1p00 mult=8
XOB nvb vrefb ob vdd ve pbias ota1vb
CFB nvb ob 1p
RSB nvb vrefb 100k

* ln V->I
RLN oa nsv {nvt/iu}
XLO2 nsv pbias vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=16 L=8
XON nsv ob gpass vdd pbias ota1b
CGP gpass 0 1p
XMNP nsv gpass ndl 0 sky130_fd_pr__nfet_03v3_nvt W=4 L=0.5
XMNM1 ndl ndl 0 0 sky130_fd_pr__nfet_g5v0d10v5 W=32 L=2
XMNM2 mno ndl 0 0 sky130_fd_pr__nfet_g5v0d10v5 W=32 L=2
VSNM out mno 0
XLO3 out pbias vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=16 L=8
.ends
