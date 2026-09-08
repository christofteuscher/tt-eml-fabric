.lib /Users/cteusche/.ciel/sky130A/libs.tech/ngspice/sky130.lib.spice tt

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
XQA nva oa 0 0 sky130_fd_pr__npn_05v5_W1p00L1p00 mult=8
XOA nva vrefb oa vdd ota5t
IVR 0 nvb {iunit}
XQB nvb ob 0 0 sky130_fd_pr__npn_05v5_W1p00L1p00 mult=8
XOB nvb vrefb ob vdd ota5t

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

VOUT out 0 0.9
