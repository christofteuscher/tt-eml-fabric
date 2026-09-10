* 8:1 observation mux -- steers ONE copy current to ua[1], dumps the rest.
*
* Principle (mux/DESIGN.md): never steal from the signal path.  Every
* observable is a dedicated mirror COPY leg, so the mux only ever handles
* copies.  Unselected copies must keep conducting -- if a copy leg were
* simply disconnected its mirror would fall out of bias and the NEXT
* selection would read a settling transient -- so every channel has TWO
* transmission gates: one to mux_out, one to a dump rail at the same
* potential.  The channel current therefore always flows somewhere.
*
* The pin is read by an SMU at virtual ground (current mode), so pass-gate
* Ron (~1-2 kOhm) does not affect accuracy; it only has to be small
* against the copy leg's output resistance.  Full CMOS transmission gates
* rather than single NMOS: the copies span 0.3-1.9 V of compliance and a
* lone NMOS pinches off at the top of that range.
*
* Select is ONE-HOT plus complement (mux_oh / mux_ohb), decoded in the
* digital block -- 16 lines instead of 3, which is routing, not silicon,
* and it keeps logic gates out of the analog tile.
*
* W=8/W=16: the PMOS is 2x the NMOS for roughly equal Ron.  Sizes are not
* critical here (see the virtual-ground note) but the gates are DC-static,
* so there is no dynamic-charge argument for making them small either.

.subckt obsmux mux_out dump vdd VSUB
+ ch0 ch1 ch2 ch3 ch4 ch5 ch6 ch7
+ moh0 moh1 moh2 moh3 moh4 moh5 moh6 moh7
+ mohb0 mohb1 mohb2 mohb3 mohb4 mohb5 mohb6 mohb7

* ---- channel 0
XNO0 ch0 moh0  mux_out VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=0.5
XPO0 ch0 mohb0 mux_out vdd  sky130_fd_pr__pfet_g5v0d10v5 W=16 L=0.5
XND0 ch0 mohb0 dump    VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=0.5
XPD0 ch0 moh0  dump    vdd  sky130_fd_pr__pfet_g5v0d10v5 W=16 L=0.5
* ---- channel 1
XNO1 ch1 moh1  mux_out VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=0.5
XPO1 ch1 mohb1 mux_out vdd  sky130_fd_pr__pfet_g5v0d10v5 W=16 L=0.5
XND1 ch1 mohb1 dump    VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=0.5
XPD1 ch1 moh1  dump    vdd  sky130_fd_pr__pfet_g5v0d10v5 W=16 L=0.5
* ---- channel 2
XNO2 ch2 moh2  mux_out VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=0.5
XPO2 ch2 mohb2 mux_out vdd  sky130_fd_pr__pfet_g5v0d10v5 W=16 L=0.5
XND2 ch2 mohb2 dump    VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=0.5
XPD2 ch2 moh2  dump    vdd  sky130_fd_pr__pfet_g5v0d10v5 W=16 L=0.5
* ---- channel 3
XNO3 ch3 moh3  mux_out VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=0.5
XPO3 ch3 mohb3 mux_out vdd  sky130_fd_pr__pfet_g5v0d10v5 W=16 L=0.5
XND3 ch3 mohb3 dump    VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=0.5
XPD3 ch3 moh3  dump    vdd  sky130_fd_pr__pfet_g5v0d10v5 W=16 L=0.5
* ---- channel 4
XNO4 ch4 moh4  mux_out VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=0.5
XPO4 ch4 mohb4 mux_out vdd  sky130_fd_pr__pfet_g5v0d10v5 W=16 L=0.5
XND4 ch4 mohb4 dump    VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=0.5
XPD4 ch4 moh4  dump    vdd  sky130_fd_pr__pfet_g5v0d10v5 W=16 L=0.5
* ---- channel 5
XNO5 ch5 moh5  mux_out VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=0.5
XPO5 ch5 mohb5 mux_out vdd  sky130_fd_pr__pfet_g5v0d10v5 W=16 L=0.5
XND5 ch5 mohb5 dump    VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=0.5
XPD5 ch5 moh5  dump    vdd  sky130_fd_pr__pfet_g5v0d10v5 W=16 L=0.5
* ---- channel 6
XNO6 ch6 moh6  mux_out VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=0.5
XPO6 ch6 mohb6 mux_out vdd  sky130_fd_pr__pfet_g5v0d10v5 W=16 L=0.5
XND6 ch6 mohb6 dump    VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=0.5
XPD6 ch6 moh6  dump    vdd  sky130_fd_pr__pfet_g5v0d10v5 W=16 L=0.5
* ---- channel 7
XNO7 ch7 moh7  mux_out VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=0.5
XPO7 ch7 mohb7 mux_out vdd  sky130_fd_pr__pfet_g5v0d10v5 W=16 L=0.5
XND7 ch7 mohb7 dump    VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=0.5
XPD7 ch7 moh7  dump    vdd  sky130_fd_pr__pfet_g5v0d10v5 W=16 L=0.5
.ends
