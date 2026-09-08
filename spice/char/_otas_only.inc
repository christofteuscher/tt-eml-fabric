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

