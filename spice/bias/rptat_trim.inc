* R_ptat trim: 15k fixed + binary-weighted shorted segments.
*
* WHY IT EXISTS.  I_ptat = dV_BE / R_ptat, and high-res poly runs +-20-30%
* over process.  Measured sensitivity (bias/rptat_sens.spice):
*     R_ptat  21k    24k    27k    30k    33k    36k    39k
*     I_unit  +40%  +23%  +10%    0%   -8.6%  -15.8% -21.9%
* so an untrimmed part can sit 40% off the design current.  Absolute gain
* error IS absorbed by the two-point readout calibration, but only if the
* current lands in a workable range to begin with -- too low and the
* subthreshold mirrors degrade (char/mirror_mc: sigma 6-12% at 100 nA vs
* 2-3% at 10 uA), too high and the MDAC compliance ceiling bites.
*
* STRUCTURE.  Three binary segments (1x, 2x, 4x the 5k unit) each bridged
* by an NMOS short, over a 15k fixed base:
*     R = 15k + (1-t0)*5k + (1-t1)*10k + (1-t2)*20k
*   all shorted (t=111) -> 15k ;  none (t=000) -> 50k ;  nominal 30k at
*   t=100 (t0 shorted, t1/t2 open -> 15+10+... ) -- see the table below.
* Eight levels in 5k steps, i.e. ~8% of current each, which is coarse ON
* PURPOSE: this is a range-setter, not a precision knob, and the fine
* correction happens in readout calibration.
*
* Everything is the SAME 5k unit the bias grid already uses (res_5k), so
* the segments match each other and the existing RD/RPTAT strings.
*
* SWITCH SIZING.  A shorting switch leaves its Ron in place of the
* segment, so the step is (R_seg - Ron) not R_seg.  W=16 L=0.5 gives
* Ron ~100-200 Ohm against a 5k segment: under 4% of one step, and it
* does not affect monotonicity, which is what a trim actually needs.
* rtrim[3] is left spare.

.subckt rptat_trim ne2 VSUB t0 t1 t2
* Drawn as TEN matched res_5k units in one row (see gen_rptat_trim.py);
* declared here as the four series groups, because the extractor collapses
* a series string whose internal nodes carry nothing else.
RB  ne2 n1 15k
RT0 n1  n2  5k
XS0 n1 t0 n2 VSUB sky130_fd_pr__nfet_g5v0d10v5 W=16 L=0.5
RT1 n2  n3 10k
XS1 n2 t1 n3 VSUB sky130_fd_pr__nfet_g5v0d10v5 W=16 L=0.5
RT2 n3  VSUB 20k
XS2 n3 t2 VSUB VSUB sky130_fd_pr__nfet_g5v0d10v5 W=16 L=0.5
.ends
