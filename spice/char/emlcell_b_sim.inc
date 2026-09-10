* FLATTENED from lvsref/ota1b.spice lvsref/ota1vb.spice lvsref/ota2b.spice lvsref/emlcell_b.spice :: emlcell_b
.subckt emlcell_b nu nv out vdd vrefb ve pbias VSUB
XLR1 nb0 pbias vdd vdd sky130_fd_pr__pfet_g5v0d10v5 L=8 W=4
XQR nb0 nb0 VSUB VSUB sky130_fd_pr__npn_05v5_W1p00L1p00
XU_0 vb2 nu VSUB sky130_fd_pr__res_high_po_0p35 L=45.76 W=0.35
CFU vb2 nu 1e-12
XMT_OT XOT.ntail pbias vdd vdd sky130_fd_pr__pfet_g5v0d10v5 L=4 W=16
XMP1_OT XOT.n1 nu XOT.ntail vdd sky130_fd_pr__pfet_g5v0d10v5 L=2 W=32
XMP2_OT XOT.no1 nb0 XOT.ntail vdd sky130_fd_pr__pfet_g5v0d10v5 L=2 W=32
XMN1_OT XOT.n1 XOT.n1 VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 L=2 W=4
XMN2_OT XOT.no1 XOT.n1 VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 L=2 W=4
XMN3_OT vb2 XOT.no1 VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 L=1 W=16
XMS_OT vb2 pbias vdd vdd sky130_fd_pr__pfet_g5v0d10v5 L=2.67 W=16
CC_OT XOT.no1 vb2 2e-12
XQ2 nc2 vb2 VSUB VSUB sky130_fd_pr__npn_05v5_W1p00L1p00
XMPM1 nc2 nc2 vdd vdd sky130_fd_pr__pfet_g5v0d10v5 L=2 W=8
XMPM2 out nc2 vdd vdd sky130_fd_pr__pfet_g5v0d10v5 L=2 W=8
XLPA nv pbias vdd vdd sky130_fd_pr__pfet_g5v0d10v5 L=8 W=8
XQA nv oa ve VSUB sky130_fd_pr__npn_05v5_W1p00L1p00
XMT_OA XOA.ntail pbias vdd vdd sky130_fd_pr__pfet_g5v0d10v5 L=4 W=16
XMP1_OA XOA.n1 nv XOA.ntail vdd sky130_fd_pr__pfet_g5v0d10v5 L=2 W=32
XMP2_OA oa vrefb XOA.ntail vdd sky130_fd_pr__pfet_g5v0d10v5 L=2 W=32
XMN1_OA XOA.n1 XOA.n1 ve VSUB sky130_fd_pr__nfet_g5v0d10v5 L=2 W=4
XMN2_OA oa XOA.n1 ve VSUB sky130_fd_pr__nfet_g5v0d10v5 L=2 W=4
CFA nv oa 1e-12
XSA_0 nv vrefb VSUB sky130_fd_pr__res_xhigh_po_0p35 L=17.5 W=0.35
XLPB_LVR nvb pbias vdd vdd sky130_fd_pr__pfet_g5v0d10v5 L=8 W=12
XQB nvb ob ve VSUB sky130_fd_pr__npn_05v5_W1p00L1p00
XMT_OB XOB.ntail pbias vdd vdd sky130_fd_pr__pfet_g5v0d10v5 L=4 W=16
XMP1_OB XOB.n1 nvb XOB.ntail vdd sky130_fd_pr__pfet_g5v0d10v5 L=2 W=32
XMP2_OB ob vrefb XOB.ntail vdd sky130_fd_pr__pfet_g5v0d10v5 L=2 W=32
XMN1_OB XOB.n1 XOB.n1 ve VSUB sky130_fd_pr__nfet_g5v0d10v5 L=2 W=4
XMN2_OB ob XOB.n1 ve VSUB sky130_fd_pr__nfet_g5v0d10v5 L=2 W=4
CFB nvb ob 1e-12
XSB_0 nvb vrefb VSUB sky130_fd_pr__res_xhigh_po_0p35 L=17.5 W=0.35
XLN_0 oa nsv VSUB sky130_fd_pr__res_high_po_0p35 L=45.76 W=0.35
XLO2 nsv pbias vdd vdd sky130_fd_pr__pfet_g5v0d10v5 L=8 W=16
XMT_ON XON.ntail pbias vdd vdd sky130_fd_pr__pfet_g5v0d10v5 L=4 W=16
XMP1_ON XON.n1 nsv XON.ntail vdd sky130_fd_pr__pfet_g5v0d10v5 L=2 W=32
XMP2_ON gpass ob XON.ntail vdd sky130_fd_pr__pfet_g5v0d10v5 L=2 W=32
XMN1_ON XON.n1 XON.n1 VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 L=2 W=4
XMN2_ON gpass XON.n1 VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 L=2 W=4
CGP gpass VSUB 1e-12
XMNP nsv gpass ndl VSUB sky130_fd_pr__nfet_03v3_nvt L=0.5 W=4
XMNM1 ndl ndl VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 L=2 W=32
XMNM2 out ndl VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 L=2 W=32
XLO3 out pbias vdd vdd sky130_fd_pr__pfet_g5v0d10v5 L=8 W=16
.ends
