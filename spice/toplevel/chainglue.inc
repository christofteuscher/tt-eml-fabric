* Inter-cell glue: everything in chain_full.spice that no laid-out block
* owns.  One instance per chain LINK (A->B, B->C, C->T).
*
* Most of chain_full's 16 top-level devices are replaced by the MDACs --
* that is the point of the fabric:
*   XGOG* fixed coupling mirrors -> the GAMMA MDACs
*   XPA*  fixed offset legs      -> the ALPHA MDACs
* What genuinely remains is this block.
*
* 1. PEDESTAL PULL-UPS (XPU, XPO).  The architecture is offset/pedestal:
*    every value is a unipolar current about a pedestal, which is what lets
*    the observation mux read single-polarity copies (mux/DESIGN.md).  One
*    pedestal into the next cell's input node, one into this cell's output.
*
* 2. GAMMA REFERENCE CONVERSION.  mdac_gamma takes `vg`, a PMOS gate --
*    but the cell produces a CURRENT at its output.  mdac_weight.inc's
*    XIC/XID would do the conversion, except the gamma MDAC block
*    deliberately does not contain them (its `vg` is a pin).  Nothing owned
*    that diode until now; this block does.  Chain:
*       cell out -> NMOS diode (XGDG) -> NMOS mirror leg (XGML)
*                -> cascoded PMOS diode (XIC/XID) -> vg
*    The PMOS diode is cascoded so the gate it produces is referenced to
*    the same Vds the MDAC legs will see -- the same reason mdac_div
*    cascodes its own diode.
*
* W=24 L=8 pedestals: W/L=3 off pbias.  Unlike the OTA tail, this current
* source faces a node whose voltage SWINGS, so its ro is a linearity term,
* not just a matching one -- see chainglue_dc.spice before shrinking it.

.subckt chainglue vdd VSUB pbias vcasc nout nu_next vg
* --- pedestals ---
XPU nu_next pbias vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=24 L=8
XPO nout    pbias vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=24 L=8
* --- output diode + mirror leg (sinks the copy from vg) ---
XGDG nout nout VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 W=16 L=2
XGML vg   nout VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 W=16 L=2
* --- cascoded PMOS diode: turns that current into the gamma MDAC's vg ---
XID nid vg    vdd vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=2
XIC vg  vcasc nid vdd sky130_fd_pr__pfet_g5v0d10v5 W=8 L=1
.ends
