* =====================================================================
* !! DO NOT CHARACTERISE THE CHIP WITH THIS FILE !!
*
* This is a SCHEMATIC bench, not the die.  Two independent reasons it
* gives wrong answers, both found 2026-08-14 after they had already put a
* wrong figure into the SHIPPED documentation:
*
*  1. IT SELF-OSCILLATES.  Zero stimulus, from the DC operating point, no
*     uic: a sustained relaxation limit cycle at 315.1984 ns (3.17 MHz),
*     ~180 mV pk-pk on nva.  Reproduced under Gear-2 integration and at
*     1000x timestep refinement, so it is not numerical.  Any .op you read
*     from this deck is an UNSTABLE equilibrium the circuit never occupies.
*     Time-averaged through the limit cycle it gives 0.83 - 1.38*ln(v),
*     residual 0.53 units -- nothing like the .op answer.
*
*  2. IT OMITS THE BIAS PEDESTAL.  These decks drive nva with v*500 nA
*     against a 500 nA reference, so the ln argument is exactly v.  THE
*     LAYOUT DOES NOT DO THAT: it generates bias legs internally off pbias
*     (XLPA puts 936 nA on nv, XLPB_LVR references 1394 nA), so the die's
*     argument is offset.  Fitting die behaviour against ln(v) makes a
*     perfectly good log amplifier look broken -- that mistake produced a
*     phantom "slope -0.34, varying 5.5x" defect, a buffer designed to fix
*     it, and a shipped build that oscillated at 7.2 MHz before revert.
*
* USE INSTEAD, for anything describing the chip:
*     char/emlcell_b_sim12.inc      die-matched, UNBUFFERED (what ships)
*     char/eml_ln_accuracy.spice    the harness that drives it correctly
*                                   (mind its note: the layout cell makes
*                                   several bias legs internally -- drive
*                                   them externally and the output doubles)
* Fit against ln(v + s) with s free, not ln(v).  The shipped cell measures
* 2.549 - 1.145*ln(v + 2.574), max residual 6.83e-4 units.
* (This line said 0.00023 until 2026-08-19.  That was the hand
* nominal's ADVERTISED error, ~3x tighter than its real one, re-measured
* against the actual sweep points.  The coefficients are unaffected and
* 6.83e-4 is still 14x inside the 0.01-unit limit -- do not re-fit.
* These are LUMPED-basis coefficients; the SEGMENTED basis the die
* actually draws gives 2.478 - 1.094*ln(v + 2.547), ~4% away.)
*
* These benches remain useful for TOPOLOGY experiments where the absolute
* law does not matter.  They are not evidence about silicon.
* =====================================================================
.param iunit=0.5u
.param nvt=26.9m
.param vsig=1.0

.subckt ota2s inp inn out vdd
* stage 1 = ota5t wiring (out1 = A1(inp-inn)); stage 2 = NMOS CS (inverts)
* => net out = A(inn - inp): INSTANTIATE WITH SWAPPED PINS for +(inp-inn)
ITAIL vdd ntail 4u
XMP1 n1  inp ntail vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=1
XMP2 no1 inn ntail vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=1
XMN1 n1  n1 0 0 sky130_fd_pr__nfet_g5v0d10v5 W=4 L=2
XMN2 no1 n1 0 0 sky130_fd_pr__nfet_g5v0d10v5 W=4 L=2
XMN3 out no1 0 0 sky130_fd_pr__nfet_g5v0d10v5 W=16 L=1
ISRC vdd out 6u
CC no1 out 2p
.ends

* log-amp OTA: NMOS stage referenced to the VE rail so the output
* cannot swing below VE+VDSsat -> the BJT-off latch (CB clamp below
* vrefb) is structurally impossible. NMOS bulk stays at substrate 0.
.subckt ota5tv inp inn out vdd vss
* IDEAL-ish SERVO: transconductance into a load, so it has FINITE output
* impedance.  A VCVS made out a hard source, which leaves the forced-current
* collector node with no stable operating point -- that is why the 1e6-gain
* version latched.  gm=1e-3 into 1e6 gives gain 1000 with 1 Mohm out.
VBIAS vb 0 1.25
GM 0 out inp inn 1e-3
RL out vb 1e6
.ends
.subckt ota5tv_unused inp inn out vdd vss
ITAIL vdd ntail 4u
XMP1 n1  inp ntail vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=1
XMP2 out inn ntail vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=1
XMN1 n1  n1 vss 0 sky130_fd_pr__nfet_g5v0d10v5 W=4 L=2
XMN2 out n1 vss 0 sky130_fd_pr__nfet_g5v0d10v5 W=4 L=2
.ends

.subckt ota5t inp inn out vdd
ITAIL vdd ntail 4u
XMP1 n1  inp ntail vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=1
XMP2 out inn ntail vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=1
XMN1 n1  n1 0 0 sky130_fd_pr__nfet_g5v0d10v5 W=4 L=2
XMN2 out n1 0 0 sky130_fd_pr__nfet_g5v0d10v5 W=4 L=2
.ends

VDD vdd 0 3.3
VRB vrefb 0 1.2
VE ve 0 0.55

* ---- exp path: reference + TIA level shift + exp NPN ----
IR1 vdd nb0 {iunit}
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
IUIN 0 nsum 0                     ; swept: -u*IUNIT (TIA inverts)
RU  vb2 nsum {nvt/iunit}
XOT nsum nb0 vb2 vdd ota2s        ; TIA two-stage; pins swapped (see subckt)
XQ2 nc2 vb2 0 0 sky130_fd_pr__npn_05v5_W1p00L1p00 mult=8
* exp output copy: PMOS mirror
XMPM1 nc2 nc2 vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=2
XMPM2 mpo nc2 vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=2
VSPM mpo out 0

* ---- ln path (v2a base-driven, validated) ----
IV  0 nva {vsig*iunit}
XQA nva oa ve 0 sky130_fd_pr__npn_05v5_W1p00L1p00 mult=8
XOA nva vrefb oa vdd ve ota5tv
IVR 0 nvb {iunit}
XQB nvb ob ve 0 sky130_fd_pr__npn_05v5_W1p00L1p00 mult=8
XOB nvb vrefb ob vdd ve ota5tv

* ---- ln V->I: servo nsv -> ob; R_LN from oa; +4-unit bias into nsv ----
* KCL at nsv: (oa-nsv)/R_LN + 4*IUNIT = I_pass
*   => I_pass = (ln v + 4)*IUNIT   (unipolar for v in [e^-4, ~anything])
* Pass device: native-Vt NMOS (drain=nsv, source=mirror diode) for
* headroom; NMOS mirror sinks I_pass from out; +4*IUNIT restored at out.
RLN oa nsv {nvt/iunit}
IOFF2 vdd nsv {4*iunit}
XON nsv ob gpass vdd ota5t        ; servo: nsv -> ob (out rises with nsv)
XMNP nsv gpass ndl 0 sky130_fd_pr__nfet_03v3_nvt W=4 L=0.5
XMNM1 ndl ndl 0 0 sky130_fd_pr__nfet_g5v0d10v5 W=32 L=2
XMNM2 mno ndl 0 0 sky130_fd_pr__nfet_g5v0d10v5 W=32 L=2
VSNM out mno 0
IOFF3 vdd out {4*iunit}

* compensation: feedback caps across transdiodes and RU, pole at gpass
CFA nva oa 1p
CFB nvb ob 1p
* startup bleed: resistor from each collector node to the vrefb rail.
* BJT off -> input current parks the node at vrefb + I*R (escape region,
* OTA must drive the base up). At equilibrium node == vrefb -> resistor
* carries ZERO current: startup guarantee with no in-operation cost.
RSA nva vrefb 100k
RSB nvb vrefb 100k
* startup: destroy the BJT-off latch (base low -> CB clamp holds nva
* below vrefb -> OTA stays railed). 50 nA walks the base up until the
* transdiode conducts; negligible load once alive.
CFU nsum vb2 1p
CGP gpass 0 1p
VOUT out 0 0.9
