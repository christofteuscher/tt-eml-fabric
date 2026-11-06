#!/usr/bin/env python3
"""Deck generator for the wake-up study.  All decks: die context (no IOFF2/IOFF3),
tt, 27 C, ideal 0.5 uA pbias reference into the harness diode XPB (as every
char/ bench), out clamped at 0.9 V by VOUT, ve=0.55 V, vrefb=1.2 V.
Cell vdd is metered by VAMC (cell only); the harness reference diode XPB by VAMR.
Integrator settings as in ../ (step settling and power decks):
  .options method=gear maxord=2 reltol=1e-5 abstol=1e-15 vntol=1e-9"""
import sys, os
PDK = "$PDK_ROOT/sky130A/libs.tech/ngspice/sky130.lib.spice"  # ngspice expands $PDK_ROOT
NET = {"pex": "extract/pex_ship.inc", "ctrl": "extract/pex_ctrl.inc", "sch": "emlcell_b_sim12.inc"}
IU = 0.5e-6

def deck(name, net, kind, u0=-1.5, u1=1.0, v=1.0, t0=1e-6, edge=10e-9, tstop=40e-6,
         tstep=5e-9, tmax=None, corner="tt", temp=27, vpre=2.0591, tpre=20e-9):
    iu0, iu1 = -u0 * IU, -u1 * IU          # true u = -(driven IUIN)
    if kind == "step":                      # baseline: input step, cell powered
        vdd = "VDD vdd 0 3.3"
        ipb = f"IPB pbias 0 {IU}"
        iuin = f"IUIN 0 nu PWL(0 {iu0} {t0} {iu0} {t0+edge} {iu1})"
    elif kind == "bias":                    # bias gating: VDD on, Iref 0 -> 0.5 uA
        vdd = "VDD vdd 0 3.3"
        ipb = f"IPB pbias 0 PWL(0 0 {t0} 0 {t0+edge} {IU})"
        iuin = f"IUIN 0 nu {iu1}"
    elif kind == "supply":                  # supply gating: VDD 0 -> 3.3, Iref ramps with it
        vdd = f"VDD vdd 0 PWL(0 0 {t0} 0 {t0+edge} 3.3)"
        ipb = f"IPB pbias 0 PWL(0 0 {t0} 0 {t0+edge} {IU})"
        iuin = f"IUIN 0 nu {iu1}"
    elif kind == "supply_refon":            # supply gating, reference current kept on
        vdd = f"VDD vdd 0 PWL(0 0 {t0} 0 {t0+edge} 3.3)"
        ipb = f"IPB pbias 0 {IU}"
        iuin = f"IUIN 0 nu {iu1}"
    elif kind == "header":                  # supply gating through a pfet header:
        # rail stays at 3.3 V; header = sky130 pfet_g5v0d10v5 W=20 L=0.5, gate ramped
        # 3.3 -> 0 V over `edge`; cell AND harness ref diode XPB sit on the gated rail
        # vddg; Iref is gated with the same edge.  When off, vddg floats (no hard sink).
        vdd = (f"VDD vdd 0 3.3\nVG ctl 0 PWL(0 3.3 {t0} 3.3 {t0+edge} 0)\n"
               f"XHDR vddg ctl vdd vdd sky130_fd_pr__pfet_g5v0d10v5 L=0.5 W=20")
        ipb = f"IPB pbias 0 PWL(0 0 {t0} 0 {t0+edge} {IU})"
        iuin = f"IUIN 0 nu {iu1}"
    elif kind == "biasfast":                # bias gating + IDEALISED fast-start: pbias is
        # forced to its settled value (vpre, from the converged run) through a 100 ohm
        # switch for tpre after t0, then released to the mirror.  Lower bound on any
        # bias-start circuit; everything else (comp caps, servo nodes) starts discharged.
        vdd = (f"VDD vdd 0 3.3\nVPRE pre 0 {vpre}\nVPC pc 0 PWL(0 0 {t0} 0 {t0+1e-9} 1 {t0+tpre} 1 {t0+tpre+1e-9} 0)\n"
               f"SPRE pbias pre pc 0 swpre\n.model swpre sw vt=0.5 vh=0.1 ron=100 roff=1e12")
        ipb = f"IPB pbias 0 PWL(0 0 {t0} 0 {t0+edge} {IU})"
        iuin = f"IUIN 0 nu {iu1}"
    else:
        raise ValueError(kind)
    g = "vddg" if kind == "header" else "vdd"
    tm = f" {tmax}" if tmax else ""
    s = f"""* {name}: kind={kind} net={NET[net]} u0={u0} u1={u1} v={v} edge={edge} {corner}/{temp}C
.lib {PDK} {corner}
.include {NET[net]}
.temp {temp}
.options method=gear maxord=2 reltol=1e-5 abstol=1e-15 vntol=1e-9
{vdd}
VAMC {g} vddc 0
VAMR {g} vddr 0
VRB  vrefb 0 1.2
VE   ve    0 0.55
VOUT out   0 0.9
{ipb}
XPB  pbias pbias vddr vddr sky130_fd_pr__pfet_g5v0d10v5 L=8 W=4
IVIN 0 nv {v*IU}
{iuin}
XDUT nu nv out vddc vrefb ve pbias 0 nb0 nc2 ndl nsv emlcell_b
.control
set noaskquit
tran {tstep} {tstop} 0{tm}
let io = i(VOUT)/0.5u
let icell = i(VAMC)
let iref = i(VAMR)
let vd = v(vdd)
let vpb = v(pbias)
wrdata runs/{name}.dat io icell iref vd vpb
.endc
.end
"""
    open(f"{name}.spice", "w").write(s)

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    for a in sys.argv[1:]:
        kw = dict(x.split("=") for x in a.split(",")[1:])
        for k in list(kw):
            if k not in ("net", "kind", "corner"): kw[k] = float(kw[k])
        deck(a.split(",")[0], **kw)
