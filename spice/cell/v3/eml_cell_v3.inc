* =========================================================================
* EML cell v3 -- clean consolidation of the v1/v2 campaign (2026-07-23).
* Computes: I_out/IU = exp(u) - ln(v_eff/3),  u = -I(nu)/IU,
*           v_eff = I(nv)/IU + 2   (2-unit internal pedestal, see below)
* IU = 0.5 uA. Output must sit at 0.35..2.4 V compliance (drive ~0.9 V).
*
* Design rules baked in (silicon/README.md has the full history):
*  - base-driven transdiodes, emitters on VE=0.55 V rail
*  - log-amp OTA output stage referenced to VE (low-side latch impossible)
*  - 100k bleed from each collector node to VREFB (startup escape,
*    zero current at equilibrium)
*  - 2-unit pedestal into both transdiode collectors: gm floor at all
*    programmed v, extends ln domain to v > -2; constant absorbed by
*    the alpha weight (compiler subtracts 2; ref divisor 3 -> -ln3 const)
*  - two-stage TIA (NMOS CS 2nd stage, Miller comp); exp MDACs invert
*  - V->I: OTA-servoed native pass + g5v0 sink mirror, +4-unit offset
*    restored at output; self-starting via RLN DC path
*  - compensation: 2p transdiode feedback, 2p Miller, 1p pass gate,
*    1p across RU
*  - input pairs W32 L2 (3x lower offset; residual absorbed by alpha)
* Ideal-for-now (W2 bias tree): all current sources, VREFB/VE rails.
* =========================================================================

* ---- single-stage OTA, ground-referenced (V->I servo) ----
.subckt ota1 inp inn out vdd
ITAIL vdd ntail 4u
XMP1 n1  inp ntail vdd sky130_fd_pr__pfet_g5v0d10v5 W=32 L=2
XMP2 out inn ntail vdd sky130_fd_pr__pfet_g5v0d10v5 W=32 L=2
XMN1 n1  n1 0 0 sky130_fd_pr__nfet_g5v0d10v5 W=4 L=2
XMN2 out n1 0 0 sky130_fd_pr__nfet_g5v0d10v5 W=4 L=2
.ends

* ---- single-stage OTA, vss-referenced output (log amps) ----
.subckt ota1v inp inn out vdd vss
ITAIL vdd ntail 4u
XMP1 n1  inp ntail vdd sky130_fd_pr__pfet_g5v0d10v5 W=32 L=2
XMP2 out inn ntail vdd sky130_fd_pr__pfet_g5v0d10v5 W=32 L=2
XMN1 n1  n1 vss 0 sky130_fd_pr__nfet_g5v0d10v5 W=4 L=2
XMN2 out n1 vss 0 sky130_fd_pr__nfet_g5v0d10v5 W=4 L=2
.ends

* ---- two-stage OTA (TIA): net out = A(inn - inp); WIRE SWAPPED ----
.subckt ota2 inp inn out vdd
ITAIL vdd ntail 4u
XMP1 n1  inp ntail vdd sky130_fd_pr__pfet_g5v0d10v5 W=32 L=2
XMP2 no1 inn ntail vdd sky130_fd_pr__pfet_g5v0d10v5 W=32 L=2
XMN1 n1  n1 0 0 sky130_fd_pr__nfet_g5v0d10v5 W=4 L=2
XMN2 no1 n1 0 0 sky130_fd_pr__nfet_g5v0d10v5 W=4 L=2
XMN3 out no1 0 0 sky130_fd_pr__nfet_g5v0d10v5 W=16 L=1
ISRC vdd out 6u
CC no1 out 2p
.ends

* ---- the EML cell ----
.subckt emlcell nu nv out vdd vrefb ve
.param iu=0.5u
.param nvt=26.9m

* exp path: reference transdiode + 2-stage TIA + exp NPN + PMOS mirror
IR1 vdd nb0 {iu}
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
XOT nu nb0 vb2 vdd ota2          ; ota2 inverts: out = A(nb0 - nu)
XQ2 nc2 vb2 0 0 sky130_fd_pr__npn_05v5_W1p00L1p00 mult=8
XMPM1 nc2 nc2 vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=2
XMPM2 mpo nc2 vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=2
VSPM mpo out 0

* ln path: pedestal + base-driven transdiodes + VE-referenced OTAs
IPEDA vdd nv {2*iu}
XQA nv oa ve 0 sky130_fd_pr__npn_05v5_W1p00L1p00 mult=8
XOA nv vrefb oa vdd ve ota1v
* CFA/CFB reduced 2p -> 1p: compensation reduced after measuring
* no ringing at 1p and clean settling at 0.5p across tt/ff/ss x
* -20/60 C (2x margin).  Costs +8% noise at the loop node.  This
* is what lets the matched pair share one strip column.
CFA nv oa 1p
RSA nv vrefb 100k
IPEDB vdd nvb {2*iu}
IVR vdd nvb {iu}
XQB nvb ob ve 0 sky130_fd_pr__npn_05v5_W1p00L1p00 mult=8
XOB nvb vrefb ob vdd ve ota1v
CFB nvb ob 1p
RSB nvb vrefb 100k

* ln V->I: servo nsv->ob, RLN from oa, +4-unit bias, native pass,
* g5v0 sink mirror, +4-unit restore at out
RLN oa nsv {nvt/iu}
IOFF2 vdd nsv {4*iu}
XON nsv ob gpass vdd ota1        ; out rises with nsv
CGP gpass 0 1p
XMNP nsv gpass ndl 0 sky130_fd_pr__nfet_03v3_nvt W=4 L=0.5
XMNM1 ndl ndl 0 0 sky130_fd_pr__nfet_g5v0d10v5 W=32 L=2
XMNM2 mno ndl 0 0 sky130_fd_pr__nfet_g5v0d10v5 W=32 L=2
VSNM out mno 0
IOFF3 vdd out {4*iu}
.ends
