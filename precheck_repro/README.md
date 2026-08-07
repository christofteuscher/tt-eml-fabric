# hvi.5 / nsd-psd.5 around sky130_fd_sc_hvl level shifters — minimal reproducer

27.5 x 21 um GDS, flattened, self-contained.  Contents: four
sky130_fd_sc_hvl level shifters (3x lsbuflv2hv_1, 1x lsbufhv2lv_1) placed
on standard 4.07 um rows exactly as in our design (two double-height pairs,
24 sites apart), with the remaining row space filled by decap_8/decap_4
and fill_1/fill_2 from the same library.  All cells are unmodified PDK
cells; the only non-PDK geometry is their placement.

## Reproduce

Magic 8.3.623 (the librelane 3.0.5 image), sky130A at PDK commit
0536d02d875c8f67dd7cca3902ac457e62f20005, TT precheck magic_drc.tcl
(ttsky26c / mpw_precheck release 2025.10.29_01.10):

    magic -noconsole -dnull -rcfile $PDK_ROOT/sky130A/libs.tech/magic/sky130A.magicrc \
          magic_drc.tcl hvl_shifter_hvi5_repro.gds repro $PDK_ROOT out.txt out.mag

Result (also in magic_drc_report.txt):

    26  HVI to HVI spacing < 0.7um (hvi.5)
    19  MV diffusion to LV nwell spacing < 0.825um (hvi.5 + nsd/psd.5)

Each shifter cell ALONE is Magic-clean; the violations appear only in row
context.

## Why the drawn geometry cannot fix it (measured)

magic_drc.tcl sets `gds maskhints yes`.  On GDS read Magic re-derives
thick oxide from devices and keeps only the un-derivable remainder of the
drawn HVI as MASKHINTS fragments; the hvi.5 rule is
`cifspacing drawn_hvi drawn_hvi 700` over THOSE fragments, where
`templayer drawn_hvi / mask-hints HVI`.  The merged drawn HVI layer here
is gap-free (KLayout space_check(0.7) and notch_check(0.7) both report
zero), but the shifters' residual hint fragments sit 0.3-0.69 um apart in
context.  We dumped the check layer with `cif ostyle drc; cif see
drawn_hvi; feedback save` to verify.  Adding HVI cannot help: derivable
additions vanish from the hints, un-derivable additions become more
hints.  (In the full design we eliminated 133 of 161 hvi.5 this way, by
replacing fill_4/fill_8 runs with decap_4/decap_8 so their HVI derives --
what remains is the shifters' own.)

The 19 nsd/psd.5 are the shifters' internal MV diffusion 0.54 um from
their own internal LV nwell.  The deck's exemption
(`cifspacing allmvdiffnowell lvnwell 825` with
`templayer allmvdiffnowell ... and-not drawn_hvi`) appears unable to
fire: hints never survive over device diffusion, so the and-not excludes
nothing there.  These 19 were present and constant through every
arrangement we tried, including all-fill.

## Question

Are these waivable for tapeout, or is there a placement convention for
the hvl level shifters that passes this deck?
