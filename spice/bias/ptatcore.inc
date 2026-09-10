* PTAT core as laid out in bias_core.gds: dVBE loop, startup chain and the
* rail divider.  The shared MDAC reference chain is a SEPARATE block
* (refchain.inc / refchain.gds), so it is not instantiated here.
* RD2 is two resistors with vcasc tapped between them.
.subckt ptatcore vdd VSUB pbias nd12 nd055 vcasc ne2
XMPP1 nb  pbias vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=16 L=8
XMPP2 pbias pbias vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=16 L=8
XQP1 nb nb VSUB VSUB sky130_fd_pr__npn_05v5_W1p00L1p00
* ONE device, not four.  The placement deliberately pitches the four QP2
* cells at 7.8 um so their deep n-wells TOUCH and merge -- that is what
* buys the area -- so the extractor sees a single large NPN.  This is a
* physical merge, not the deck's device combining: it is still there with
* combine=false.  The 8x emitter area is carried by the merged geometry;
* the PDK NPN has no area parameter for LVS to compare anyway.
XQP2 pbias nb ne2 VSUB sky130_fd_pr__npn_05v5_W1p00L2p00 ne=4
* R_ptat is NOT here any more: it moved to the rptat_trim block, which
* provides 15k fixed + binary-weighted shorted segments (5k/10k/20k) so
* the PTAT current can be pulled back onto the design point.  Untrimmed
* poly runs +-20-30%, which is +40/-22% of core current
* (bias/rptat_sens.spice).  ne2 is now a PIN.
XSL1 nsl1 nsl1 pbias vdd sky130_fd_pr__pfet_g5v0d10v5 W=4 L=8
XSL2 nsl2 nsl2 nsl1 vdd sky130_fd_pr__pfet_g5v0d10v5 W=4 L=8
XSL3 nsl3 nsl3 nsl2 vdd sky130_fd_pr__pfet_g5v0d10v5 W=4 L=8
XSL4 nd12 nd12 nsl3 vdd sky130_fd_pr__pfet_g5v0d10v5 W=4 L=8
RD1 vdd nd12 210k
RD2A nd12 vcasc 35k
RD2B vcasc nd055 30k
RD3 nd055 VSUB 55k
* startup kick cap -- it IS in the layout, so it belongs in the reference
CST vdd nb 1p
.ends
