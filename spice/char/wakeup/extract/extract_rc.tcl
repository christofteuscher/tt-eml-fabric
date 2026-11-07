# Parasitic extraction for post-layout simulation.
# Invoked as: magic ... extract_rc.tcl <gds> <topcell> <pdk>
#
# INDEX FROM THE END.  Magic's Tcl `argv` holds MAGIC'S OWN command line,
# not the script's arguments -- [lindex $argv 0] came back "-nowrapper"
# and [lindex $argv 1] "-noconsole".  So `gds read` was handed a flag, no
# cell was ever loaded, and `extract all` correctly refused with "Please
# name the cell before extracting" -- while this script's own puts still
# printed EXTRACT_DONE and the wrapper reported success.  Post-layout
# extraction has therefore never run on this design.
set pdk  [lindex $argv end]
set top  [lindex $argv end-1]
set gds  [lindex $argv end-2]

gds read $gds
load $top
# fail loudly rather than extracting nothing
if {[cellname list self] eq "(UNNAMED)"} {
    puts "EXTRACT_FAIL: no cell named $top in $gds"
    quit -noprompt
}
select top cell
extract do local
# RESISTANCE NEEDS THREE THINGS, and the original had none of them:
#   extract do resistance   -- ask for R at all
#   extresist all           -- bare `extresist` does nothing here
#   ext2spice extresist on  -- tell ext2spice to read the .res.ext view
# Without them `extract all` yields capacitance only: the first working
# run gave 163 C and ZERO R.  With them, mdac_gamma produced .res.ext and
# .nodes views and 1302 R cards, 22 of 31 nets resistance-extracted.
extract do resistance
feedback clear
extract all
# SURFACE THE ERRORS.  extract prints "N errors" to the log but the detail
# lives in magic's feedback entries, which are silent unless asked for.
# emlcell_b reported 303 and ptatcore 25 while both yielded R=0 -- a failing
# extraction, not a clean zero.  Dump a bounded sample with coordinates.
# `feedback why` reports areas under the cursor box, NOT an index -- looping it
# with $i silently reports the same (or no) entry.  `feedback save` dumps every
# entry with its coordinates, so save and read it back.
set _nfb [feedback count]
puts "EXTRACT_FEEDBACK $_nfb"
if {$_nfb > 0} {
    feedback save fb_$top
    if {[file exists fb_$top]} {
        set _f [open fb_$top r]
        set _n 0
        while {[gets $_f _line] >= 0} {
            if {[incr _n] > 60} { puts "FB ... ($_nfb total)"; break }
            puts "FB $_line"
        }
        close $_f
    }
}
# RESISTANCE NEEDS ITS OWN PASS.  `extract all` yields capacitance only --
# the first working run gave 163 parasitic C and ZERO R, which for this
# fabric is the wrong half: the summing node is high impedance and series
# R along the MDAC legs is exactly what perturbs weight accuracy.
# extresist needs the .sim view, so ext2sim first.
ext2sim labels on
ext2sim
extresist tolerance 10
extresist all
ext2spice lvs
ext2spice extresist on
ext2spice cthresh 0.01
ext2spice rthresh 100
ext2spice format ngspice
ext2spice
puts "EXTRACT_DONE [cellname list self]"
quit -noprompt
