# SUPERSEDED by ../STATUS.md (2026-07-26)
#
# Every block listed below is now built and verified except where STATUS.md
# says otherwise:
#   obs mux      -> obsmux.gds      30.7 x 48.3   DRC 0, LVS MATCH
#   chain glue   -> chainglue.gds   48.0 x 39.6   DRC 0, LVS MATCH
#   R_ptat trim  -> rptat_trim.gds  27.0 x 36.6   DRC 0, LVS MATCH
#   raildrv      -> still unbuilt (2 x ota2b + 10 pF decap, ~5.0 k)
#   ESD          -> still undecided
# Kept for the enumeration method and the gate-area arithmetic.

# Silicon with NO layout (enumerated 2026-07-26)

Definitive list from diffing chain_full.spice + ptat_bias.inc against the
laid-out blocks (emlcell2, mdac2_*, bias_core, refchain).  Everything below
was absent from every floorplan and utilization number reported before this
date — the "78% fits" figure did not include any of it.

## 1. raildrv — 2 x ota2b + 10 pF decap          (~5.0 kum2)
`ptat_bias.inc` line 89: the ve/vrefb cell references are ota2b unity
buffers on the rail-divider taps.  Top-level block by design ("neither
fits the 34 um bias strip").  ota2b = 2.48 kum2 each.
OPTION: buffer with ota1b (1.17 k) instead — saves 2.6 k, needs a check
that ota1b drives 5 pF stably.

## 2. Chain glue                                  (~2 - 2.5 kum2, layout to confirm)
16 top-level devices in chain_full.spice, 1544 um2 of gate.  In the REAL
chip a large part is replaced by MDACs (that is the point of the fabric):
  - XGOG* fixed coupling mirrors  -> gamma MDACs (already laid out)
  - XPA*  fixed offset legs       -> alpha MDACs (already laid out)
What remains genuinely unplaced:
  - per-cell pedestal pull-ups XPU*/XPO* (W=24 L=8, 192 um2 gate EACH,
    2 per cell = 8 for 4 cells)
  - per-link gamma-reference conversion: cell output -> NMOS diode
    (XGDG W=16 L=2) -> NMOS leg -> cascoded PMOS diode -> vg pin of the
    gamma MDAC.  The PMOS half is mdac_weight.inc's XIC/XID, which the
    gamma block deliberately does NOT contain.  NEW DESIGN, ~5 devices/link.
  - cell-A input structure XPSAV/XN1AV/XN2AV (V->I with offset)
  - XLMON iu monitor leg (mux ch0)

## 3. Observation mux + copy legs                 (task 3, ~1.5-2 kum2 est)
mux/DESIGN.md: 8:1 g5v0 transmission-gate tree + one mirror copy leg per
observable + sink rail.  No netlist, no layout.

## 4. iref input interface (ua[2])                 (part of task 3)
External I_ref into the bias domain.  No netlist.

## 5. R_ptat trim, 4 bits                          (task 5)
cfg[trim] shorts R_ptat segments via NMOS switches.  No netlist.
NOTE: switch gates are 3.3 V domain lines (same as MDAC config).

## 6. Decap: CVC 2 p (vcasc), CVE/CVRB 5 p each
MiM stacks over active — no floor cost, but pockets must be assigned at
top level.  12 pF total = ~6 kum2 of plate.

## 7. ESD
TT analog pins are raw.  Decision needed: bare + guard rings (typical for
SMU-driven analog TT projects) vs series-R + diodes.  Old floorplan
reserved 2.7 k for this.

## Corrected whole-chip arithmetic (2-digit MDACs, hvl digital)
The previously reported config table understates every configuration by
roughly +7-10 k (items 1-5 above).  The 4-cell + OTA-shrink target of
~91% is therefore really ~100% unless raildrv uses small buffers and the
glue is lean.  This file exists so that never happens silently again:
any block added here must be added to gen_toplevel.py PLACED accounting.
