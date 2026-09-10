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
XQR_0 nb0 nb0 0 0 sky130_fd_pr__npn_05v5_W1p00L1p00
XQR_1 nb0 nb0 0 0 sky130_fd_pr__npn_05v5_W1p00L1p00
XQR_2 nb0 nb0 0 0 sky130_fd_pr__npn_05v5_W1p00L1p00
XQR_3 nb0 nb0 0 0 sky130_fd_pr__npn_05v5_W1p00L1p00
XQR_4 nb0 nb0 0 0 sky130_fd_pr__npn_05v5_W1p00L1p00
XQR_5 nb0 nb0 0 0 sky130_fd_pr__npn_05v5_W1p00L1p00
XQR_6 nb0 nb0 0 0 sky130_fd_pr__npn_05v5_W1p00L1p00
XQR_7 nb0 nb0 0 0 sky130_fd_pr__npn_05v5_W1p00L1p00
IUIN 0 nsum 0                     ; swept: -u*IUNIT (TIA inverts)
RU  vb2 nsum {nvt/iunit}
XOT nsum nb0 vb2 vdd ota2s        ; TIA two-stage; pins swapped (see subckt)
XQ2_0 nc2 vb2 0 0 sky130_fd_pr__npn_05v5_W1p00L1p00
XQ2_1 nc2 vb2 0 0 sky130_fd_pr__npn_05v5_W1p00L1p00
XQ2_2 nc2 vb2 0 0 sky130_fd_pr__npn_05v5_W1p00L1p00
XQ2_3 nc2 vb2 0 0 sky130_fd_pr__npn_05v5_W1p00L1p00
XQ2_4 nc2 vb2 0 0 sky130_fd_pr__npn_05v5_W1p00L1p00
XQ2_5 nc2 vb2 0 0 sky130_fd_pr__npn_05v5_W1p00L1p00
XQ2_6 nc2 vb2 0 0 sky130_fd_pr__npn_05v5_W1p00L1p00
XQ2_7 nc2 vb2 0 0 sky130_fd_pr__npn_05v5_W1p00L1p00
* exp output copy: PMOS mirror
XMPM1 nc2 nc2 vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=2
XMPM2 mpo nc2 vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=2
VSPM mpo out 0

* ---- ln path (v2a base-driven, validated) ----
IV  0 nva {vsig*iunit}
XQA_0 nva oa ve 0 sky130_fd_pr__npn_05v5_W1p00L1p00
XQA_1 nva oa ve 0 sky130_fd_pr__npn_05v5_W1p00L1p00
XQA_2 nva oa ve 0 sky130_fd_pr__npn_05v5_W1p00L1p00
XQA_3 nva oa ve 0 sky130_fd_pr__npn_05v5_W1p00L1p00
XQA_4 nva oa ve 0 sky130_fd_pr__npn_05v5_W1p00L1p00
XQA_5 nva oa ve 0 sky130_fd_pr__npn_05v5_W1p00L1p00
XQA_6 nva oa ve 0 sky130_fd_pr__npn_05v5_W1p00L1p00
XQA_7 nva oa ve 0 sky130_fd_pr__npn_05v5_W1p00L1p00
XOA nva vrefb oa vdd ve ota5tv
IVR 0 nvb {iunit}
XQB_0 nvb ob ve 0 sky130_fd_pr__npn_05v5_W1p00L1p00
XQB_1 nvb ob ve 0 sky130_fd_pr__npn_05v5_W1p00L1p00
XQB_2 nvb ob ve 0 sky130_fd_pr__npn_05v5_W1p00L1p00
XQB_3 nvb ob ve 0 sky130_fd_pr__npn_05v5_W1p00L1p00
XQB_4 nvb ob ve 0 sky130_fd_pr__npn_05v5_W1p00L1p00
XQB_5 nvb ob ve 0 sky130_fd_pr__npn_05v5_W1p00L1p00
XQB_6 nvb ob ve 0 sky130_fd_pr__npn_05v5_W1p00L1p00
XQB_7 nvb ob ve 0 sky130_fd_pr__npn_05v5_W1p00L1p00
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
