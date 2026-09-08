* lvshift: custom level-shifter block replacing the four sky130_fd_sc_hvl
* lsbuf cells in cfgdig.  ALL-MV: no LV device, no LV nwell, so the two
* Magic classes the PDK cells could not escape (hint-fragment hvi.5 and
* nsd/psd.5) cannot exist here by construction.  Verified in
* char/lvshift.spice at tt/sf/ss/ff/fs with rails at 3.63/1.62: full-rail
* outputs, tp 1.3-6.6 ns.
* PMOS bodies: keepers/buffers at vddh, input-inverter and hv2lv at vddl
* -- TWO nwell islands.

.subckt lv2hv in out vddh vddl vss
XIN1 inb in vddl vddl sky130_fd_pr__pfet_g5v0d10v5 W=2 L=0.5
XIN2 inb in vss  vss  sky130_fd_pr__nfet_g5v0d10v5 W=1 L=0.5
XMP1 n1  n2 vddh vddh sky130_fd_pr__pfet_g5v0d10v5 W=0.5 L=0.5
XMP2 n2  n1 vddh vddh sky130_fd_pr__pfet_g5v0d10v5 W=0.5 L=0.5
XMN1 n1  in  vss vss  sky130_fd_pr__nfet_g5v0d10v5 W=8 L=0.5
XMN2 n2  inb vss vss  sky130_fd_pr__nfet_g5v0d10v5 W=8 L=0.5
XB1p outb n2 vddh vddh sky130_fd_pr__pfet_g5v0d10v5 W=2 L=0.5
XB1n outb n2 vss  vss  sky130_fd_pr__nfet_g5v0d10v5 W=1 L=0.5
XB2p out outb vddh vddh sky130_fd_pr__pfet_g5v0d10v5 W=2 L=0.5
XB2n out outb vss  vss  sky130_fd_pr__nfet_g5v0d10v5 W=2 L=0.5
.ends

.subckt hv2lv in out vddl vss
XA1p m in vddl vddl sky130_fd_pr__pfet_g5v0d10v5 W=2 L=0.5
XA1n m in vss  vss  sky130_fd_pr__nfet_g5v0d10v5 W=1 L=0.5
XB1p out m vddl vddl sky130_fd_pr__pfet_g5v0d10v5 W=2 L=0.5
XB1n out m vss  vss  sky130_fd_pr__nfet_g5v0d10v5 W=1 L=0.5
.ends

.subckt lvshift a_sdata a_sclk a_rstn x_sdata x_sclk x_rstn a_sout x_sout vddh vddl vss
XLS0 a_sdata x_sdata vddh vddl vss lv2hv
XLS1 a_sclk  x_sclk  vddh vddl vss lv2hv
XLS2 a_rstn  x_rstn  vddh vddl vss lv2hv
XLS3 a_sout  x_sout  vddl vss hv2lv
.ends
