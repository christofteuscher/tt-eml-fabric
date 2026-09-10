* Shared reference chain as laid out in refchain.gds: the unit gate vgu
* plus the /4 and /16 divider stages.  Extracted from ptat_bias.inc so the
* block can be verified on its own; `pbias` and `vcasc` arrive as pins.
* XDUM is the layout's odd-leg dummy, held off with gate and drain on vdd.
.subckt refchain vdd VSUB pbias vcasc vgu vg4 vg16
XREFP  nref pbias vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=4 L=8
XREFN  nref nref  VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=2
XREFM  vgu  nref  VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 W=8 L=2
* CASCODED diode: the legs it references are cascoded, so the reference
* has to see the same Vds or the unit current is off by the mirror gain
* error the cascodes exist to remove.
XREFPDs nrpd vgu   vdd  vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=2
XREFPDc vgu  vcasc nrpd vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=1
* the dummy is a real cascoded PAIR in the layout -- source device and
* cascode with a mid node between them -- not two devices with every
* terminal shorted to vdd
XDUMs  ndum vdd   vdd  vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=2
XDUMc  vdd  vdd   ndum vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=1
XDIV4  vgu  vg4  vcasc vdd VSUB mdac_div
XDIV16 vg4  vg16 vcasc vdd VSUB mdac_div
.ends
