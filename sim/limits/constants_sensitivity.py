#!/usr/bin/env python3
"""AUDIT RESPONSE: provenance + sensitivity of the three constants the central result rests on.

  BITS_ROOT  -- was 4.30, cited to RESULTS.md/FAB_ERROR.md.  TRACED here (it is neither).
  CTRL       -- was "GUESS: x3".  Published basis + range established here.
  K_NODE     -- was "first-order".  Range established here.

Then the three headlines are recomputed over the full plausible range of all three.

Run: arch -arm64 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 \
     fabric_sim/limits/constants_sensitivity.py
"""
import math

L2 = math.log2
P = print

# ---------------------------------------------------------------- 1. BITS_ROOT
P("=" * 96)
P("1.  BITS_ROOT -- PROVENANCE")
P("=" * 96)
P("""
The value 4.30 was cited to "FAB_ERROR.md / RESULTS.md  best achievable at a tree root".
Neither file contains it.  It reproduces EXACTLY from one number in the results tree:

    multivar.json rows[60]: target I.9.18 (Newtonian gravity, 9 vars), hw="ideal",
    seed 0 of 8, mesh depth 4 / width 8, test_nrmse = 0.050741663
        log2(1/0.050741663) = %.4f  bits          <-- this is the 4.30
    energy_area_compare.py:137 prints exactly this via bits(0.0507).

That is NOT "best achievable at a tree root".  It is (a) IDEAL hardware, no mismatch,
no drift, no weight quantisation; (b) the single best of 8 seeds, and an outlier -- the
other 7 seeds give NRMSE 0.102-0.191, i.e. %.2f-%.2f bits, median %.2f bits; (c) a
9-variable regression fit, not a per-node hardware SNR.  It is the single most
favourable number in the tree.  It cannot be published as the fabric's precision.
""" % (L2(1 / 0.050741663),
       L2(1 / 0.1914), L2(1 / 0.1016),
       L2(1 / 0.1330)))

P("SOURCEABLE REPLACEMENTS (arithmetic shown, every input in a named file):\n")
CAND = [
    ("HW-A  raw single cell, no cascade",
     "FAB_ERROR.md sec 9: swing S0 = 1.288 u (MEASURED), level sigma = 0.266 u (MEASURED, 440 MC)",
     L2(1.288 / 0.266)),
    ("HW-B  trimmed, as shipped, depth 1",
     "FAB_ERROR.md sec 9.1: v-path offset-trimmed reaches d=1 @ 4 bits (d=2 @ 3 bits)",
     4.00),
    ("HW-C  63-cell depth-6 tree, fixed link",
     "FAB_ERROR.md sec 9.1: 'delivers 3 bits at the root ... the honest sizing number'",
     3.00),
    ("HW-D  absolute ceiling, any design",
     "FAB_ERROR.md sec 5.1: 1.88 % un-trimmable ln-slope mismatch, log2(1/0.0188)",
     L2(1 / 0.0188)),
    ("FN-A  PDK chip, in-situ, MEDIAN of 8   *** RECOMMENDED ANCHOR ***",
     "RESULTS.md run 3: beta-model median 5.5 K RMSE over the 80 K span; 5.5/80 = 0.06875",
     L2(80.0 / 5.5)),
    ("FN-B  PDK chip, in-situ, BEST of 8",
     "RESULTS.md run 3: 0.77 K over 80 K = 0.009625",
     L2(80.0 / 0.77)),
    ("FN-C  combined realistic chip, median",
     "RESULTS.md run 2: beta-model median 6.3 K over 80 K",
     L2(80.0 / 6.3)),
    ("OLD   what 4.30 actually was",
     "multivar.json I.9.18 best-of-8 seed, IDEAL hw -- do not use",
     L2(1 / 0.050741663)),
]
for n, s, b in CAND:
    P("  %-48s %5.2f bits\n      %s" % (n, b, s))

BITS_ANCHOR = L2(80.0 / 5.5)          # 3.86 -- the recommended re-anchor
BITS_RANGE = [L2(1.288 / 0.266), 3.00, BITS_ANCHOR, 4.30, L2(1 / 0.0188), L2(80.0 / 0.77)]

# ---------------------------------------------------------------- 2. CTRL
P("=" * 96)
P("2.  CTRL -- published basis")
P("=" * 96)
P("""
Was: 'GUESS: x3 on raw arithmetic for RF/control/clock'.  A published basis exists and
it lands on 3.0 almost exactly:

  Balfour, Dally et al., 'An Energy-Efficient Processor Architecture for Embedded
  Systems', IEEE Computer Architecture Letters, Jan 2008 (Stanford ELM):
     16-bit add                                        = 18 pJ
     three RF accesses (2 operands + 1 writeback),
        16-entry register file                         = 36 pJ
     => operand delivery alone is 2.0x the arithmetic;  total = 3.0x raw.   ==> CTRL = 3.0

  UPPER BOUND, same research line: Hameed et al., 'Understanding Sources of Inefficiency
  in General-Purpose Chips', ISCA 2010: in a datapath SIMD-customised down to 8-12 bit
  widths -- i.e. MORE specialised than the baseline used here -- 'functional unit energy
  comprises less than 10 % of the total'.  ==> CTRL <= ~10 for anything with real
  instruction/data supply.

  LOWER BOUND: a fully hardwired, hard-coded-coefficient PWL block with no register file
  and no control FSM pays pipeline registers + clock only.  ==> CTRL >= ~2.

  DEFENSIBLE RANGE: CTRL in [2, 10], central 3.0, core range [2, 5].
  NOTE THE DIRECTION: CTRL = 3.0 is at the LOW end.  It is the most FABRIC-UNFAVOURABLE
  choice in the published range -- the guess was conservative against the fabric, not for it.
""")
CTRL_NOM, CTRL_RANGE = 3.0, [2.0, 3.0, 5.0, 10.0]

# ---------------------------------------------------------------- 3. K_NODE
P("=" * 96)
P("3.  K_NODE -- 45 nm -> 130 nm energy scaling")
P("=" * 96)
K_HI = (130 / 45) * (1.8 / 0.9) ** 2
K_LO = (130 / 45) * (1.2 / 0.9) ** 2
P("""
Was: K_NODE = (130/45)*(1.8/0.9)^2 = %.2f, 'first-order'.  Decomposed:

  capacitance term  L_130/L_45 = %.3f     (C ~ gate length; the standard first-order form)
  voltage term      (V_130/V_45)^2

  V_45  = 0.9 V, the Horowitz ISSCC-2014 operating point the source data is quoted at.
  V_130 = 1.8 V if the comparator is built in sky130 std cells (sky130_fd_sc_hd nominal
          rail is 1.8 V) -> K = %.2f    <-- correct for THIS comparison, and used here
        = 1.2 V for a contemporaneous low-power 130 nm logic process (TSMC/IBM 130 nm
          core rail) -> K = %.2f
  Empirical cross-check: switching energy per gate falls ~2x per node generation;
  130 -> 90 -> 65 -> 45 is ~3 generations -> ~8x total.  Sits between the two.

  DEFENSIBLE RANGE: K_NODE in [5.1, 11.6], central ~8, best estimate %.2f for a sky130
  1.8 V comparator.  AGAIN NOTE THE DIRECTION: %.2f is the TOP of the range, i.e. the most
  expensive digital baseline, i.e. the most FABRIC-FAVOURABLE choice.
""" % (K_HI, 130 / 45, K_HI, K_LO, K_HI, K_HI))
K_NOM, K_RANGE = K_HI, [K_LO, 8.0, K_HI]

# ---------------------------------------------------------------- 4. per-cell power
P("=" * 96)
P("4.  PER-CELL POWER: 96.95 uW vs 98.566 uW")
P("=" * 96)
P("""
  98.566 uW  MEASURED (POWER.md 1, 4.5): one emlcell_b, die context, tt/27 C, nominal
             operating point, 29.8686 uA off 3.3 V.  ss/ff spread 97.05-100.33 uW.
             The right number for ONE ISOLATED CELL.
  96.95  uW  INFERRED (POWER.md 4.2): mean of cell A (98.62) and cell B (95.27) in the
             MEASURED 2-cell chain, then used as the per-N coefficient of
             P(N) = 96.95 N + 85.64 (N-1) + 2.09.  The right number for a CELL IN A CHAIN.

  The audit's hypothesis (one includes weight DACs, the other does not) is WRONG.  Both
  nominally include 2 alpha MDACs + 10 flops, and POWER.md 4.1 records that the alpha
  MDACs draw < 0.1 nA from vdd at code 0 and that 'their power at non-zero codes was NOT
  measured'.  Neither figure contains any real weight-DAC power; both are lower bounds.
  The 1.6 % gap is cell B sitting 6 units low on its exp input because of the chainglue
  MPU pedestal (CHAIN.md 3c) -- a power saving caused by a design DEFECT.

  RESOLUTION: BOTH ARE CORRECT, IN DIFFERENT CONTEXTS, AND NEITHER HEADLINE CHANGES.
  The decider is that 96.95 is the coefficient that makes P(N) reproduce the MEASURED
  2-cell chain:
""")
T7 = 1.19 * (166 + 65 * 2)                     # ns, PEX-inflated N=7 settling
E_FAB_N7 = (96.95 * 7 + 85.64 * 6 + 2.09) * 1e-6 * T7 * 1e-9 * 1e12
E_FAB_N7_ALT = (98.566 * 7 + 85.64 * 6 + 2.09) * 1e-6 * T7 * 1e-9 * 1e12
E_FAB_1 = 98.566e-6 * 402e-9 * 1e12
E_CORE_1 = 13.0e-3                              # pJ, 13.0 fJ open-loop core
# ---------------------------------------------------------------------------
# CORRECTION 2026-09-05, referee report W1.
# E_CORE_7 was 7 * E_CORE_1, which charges seven bare cores ONE settling time
# each, while E_FAB_N7 above charges the fabric the FULL three-stage chain
# latency T7.  Mixing those two conventions inflated H2 and the N=7 tax by
# exactly the stage count.  The chain-consistent denominator powers all seven
# cores for the whole depth-3 chain, as the fabric term does.
# The SINGLE-CELL tax E_FAB_1/E_CORE_1 = 3046x is unaffected: both of its terms
# are one device settling once, so it is free of this convention.
# ---------------------------------------------------------------------------
CORE_STAGES = 3                                 # depth-3 task = 3 sequential stages
E_CORE_7_ONESETTLE = 7 * E_CORE_1               # OLD, inconsistent; kept for reference
E_CORE_7 = 7 * E_CORE_1 * CORE_STAGES           # chain-consistent
P("    P(2) with 96.95  = %.2f uW  ==  MEASURED chain total 281.622 uW (POWER.md 4.1). EXACT."
  % (96.95 * 2 + 85.64 + 2.09))
P("    P(2) with 98.566 = %.2f uW  -> %.2f %% ABOVE a direct measurement. Contradicts POWER.md."
  % (98.566 * 2 + 85.64 + 2.09, 100 * ((98.566 * 2 + 85.64 + 2.09) / 281.622 - 1)))
P("""
    So 96.95 is not a competing estimate of the same quantity: it is the fitted per-cell
    slope of a 2-point measured power model, and substituting 98.566 would break the fit.
    CORRECT USAGE:
      one isolated cell, nominal operating point   -> 98.566 uW  -> 39.6 pJ  (UNCHANGED)
      cell inside an N-cell chain, via P(N)        -> 96.95  uW  -> 420.8 pJ (UNCHANGED)
    NO HEADLINE CHANGES.  What must change is the LABELLING, in three places:
      (i)  POWER.md 4.2's caption 'per cell (emlcell_b + 2 alpha + 10 flops)' implies the
           96.95 figure adds weight DACs to the 98.566 one.  It does not -- it is a
           chain-average, and it is LOWER, not higher.
      (ii) energy_area_compare.py's duty-cycle section says 'the cell burns 98.57 uW' while
           the N=7 numbers on the same page use 96.95.  Mixed basis on one screen.
      (iii) BOTH exclude weight-DAC switching power entirely (POWER.md 4.1: alpha MDACs
           draw < 0.1 nA at code 0, 'power at non-zero codes was NOT measured').  Every
           fabric energy figure in the paper is therefore a LOWER BOUND, and that has to
           be said -- it is a larger caveat than the 1.6 %% the audit was chasing.""")
P("    (for reference, an all-98.566 N=7 fabric would be %.1f pJ, +%.1f %%.)"
  % (E_FAB_N7_ALT, 100 * (E_FAB_N7_ALT / E_FAB_N7 - 1)))

# ---------------------------------------------------------------- 5. recompute
ADD8, MUL8 = 0.03, 0.20


def sram_pJ(kB):
    return 1.41 * kB ** 0.617


def e_dig_fixed(ctrl, k):
    """The AS-PUBLISHED baseline: 8-bit mul + 8-bit add + 32 B LUT (16-seg PWL)."""
    return (MUL8 + ADD8 + sram_pJ(0.032)) * ctrl * k


def e_dig_matched(b, ctrl, k):
    """Width-scaled to b bits -- the only form in which BITS_ROOT can reach a headline.
    Same expression energy_floor.py:317 already uses for its own bisection."""
    return (MUL8 * (b / 8) ** 2 + ADD8 * (b / 8) + sram_pJ(0.032 * b / 8)) * ctrl * k


P("=" * 96)
P("5.  THE THREE HEADLINES, RECOMPUTED")
P("=" * 96)
P("  H1 fabric loses      = E_fab(N=7) / E_dig")
P("  H2 primitive wins    = E_dig / E_core(7)")
P("  H3 composability tax = H1 x H2 = E_fab / E_core   <-- CTRL, K_NODE and BITS_ROOT CANCEL\n")
P("  E_fab(N=7) = %.1f pJ   E_core(7) = %.4f pJ   =>  H3 = %.0fx  (N=7 fabric)"
  % (E_FAB_N7, E_CORE_7, E_FAB_N7 / E_CORE_7))
P("  E_fab(1)   = %.2f pJ   E_core(1) = %.4f pJ   =>  H3 = %.0fx  (single cell; the '3046x')\n"
  % (E_FAB_1, E_CORE_1, E_FAB_1 / E_CORE_1))
P("  AS PUBLISHED (fixed 8-bit baseline, CTRL=3.0, K=11.56): E_dig = %.2f pJ" % e_dig_fixed(3.0, K_HI))
P("      H1 = %.0fx   H2 = %.0fx   H1 x H2 = %.0fx  (published: 30x, 152x, '~3000x')"
  % (E_FAB_N7 / e_dig_fixed(3.0, K_HI), e_dig_fixed(3.0, K_HI) / E_CORE_7,
     E_FAB_N7 / E_CORE_7))
P("      NOTE the published pair 30 x 152 = 4624, NOT 3046.  3046 is the SINGLE-CELL tax")
P("      (39.6 pJ / 13.0 fJ); the N=7 tax is %.0fx because links add 88 %% per cell."
  % (E_FAB_N7 / E_CORE_7))
P("      '~3000x' and 'the ratio between them' are two different quantities in the record.\n")

P("-" * 96)
P("5a. SENSITIVITY: H1 / H2 over CTRL x K_NODE   (fixed 8-bit baseline, as published)")
P("-" * 96)
P("%-10s" % "CTRL \\ K" + "".join("%22s" % ("K=%.2f" % k) for k in K_RANGE))
for c in CTRL_RANGE:
    row = "%-10.1f" % c
    for k in K_RANGE:
        e = e_dig_fixed(c, k)
        row += "%22s" % ("H1=%.0fx  H2=%.0fx" % (E_FAB_N7 / e, e / E_CORE_7))
    P(row)
P("  span: H1 %.0f-%.0fx,  H2 %.0f-%.0fx.  Product fixed at %.0fx everywhere."
  % (E_FAB_N7 / e_dig_fixed(10, K_HI), E_FAB_N7 / e_dig_fixed(2, K_LO),
     e_dig_fixed(2, K_LO) / E_CORE_7, e_dig_fixed(10, K_HI) / E_CORE_7, E_FAB_N7 / E_CORE_7))

P("\n" + "-" * 96)
P("5b. SENSITIVITY: BITS_ROOT, using a digital baseline WIDTH-MATCHED to the fabric's bits")
P("    (CTRL=3.0, K=11.56.  This is the only way BITS_ROOT touches a headline.)")
P("-" * 96)
P("%-9s %-42s %10s %9s %9s" % ("bits", "source", "E_dig pJ", "H1", "H2"))
for b in sorted(BITS_RANGE):
    lbl = {L2(1.288 / 0.266): "FAB_ERROR raw single cell (MEASURED)",
           3.00: "FAB_ERROR 63-cell tree root",
           BITS_ANCHOR: "RESULTS.md run3 median 5.5K/80K  ANCHOR",
           4.30: "the old untraceable value",
           L2(1 / 0.0188): "FAB_ERROR slope ceiling, any design",
           L2(80.0 / 0.77): "RESULTS.md run3 best-of-8 0.77K/80K"}[b]
    e = e_dig_matched(b, 3.0, K_HI)
    P("%-9.2f %-42s %10.2f %8.0fx %8.0fx" % (b, lbl, e, E_FAB_N7 / e, e / E_CORE_7))

P("\n" + "-" * 96)
P("5c. FULL RANGE, all three constants at once (width-matched baseline)")
P("-" * 96)
lo1 = hi1 = lo2 = hi2 = None
for b in BITS_RANGE:
    for c in CTRL_RANGE:
        for k in K_RANGE:
            e = e_dig_matched(b, c, k)
            h1, h2 = E_FAB_N7 / e, e / E_CORE_7
            lo1 = h1 if lo1 is None else min(lo1, h1)
            hi1 = h1 if hi1 is None else max(hi1, h1)
            lo2 = h2 if lo2 is None else min(lo2, h2)
            hi2 = h2 if hi2 is None else max(hi2, h2)
P("  H1  fabric loses to digital by      %.0fx  ..  %.0fx      (never < 1: conclusion (a) HOLDS)" % (lo1, hi1))
P("  H2  bare primitive beats digital by %.0fx  ..  %.0fx      (never < 1: conclusion (b) HOLDS)" % (lo2, hi2))
P("  H3  composability tax               %.0fx exactly, at every point in the box" % (E_FAB_N7 / E_CORE_7))
P("      (H3 = E_fab/E_core: no digital constant appears in it at all)")

# worst case for each conclusion
P("\n  Worst case for (a): b=%.2f, CTRL=%.0f, K=%.2f -> fabric still loses %.1fx"
  % (max(BITS_RANGE), 10.0, K_HI, E_FAB_N7 / e_dig_matched(max(BITS_RANGE), 10.0, K_HI)))
P("  Worst case for (b): b=%.2f, CTRL=%.0f, K=%.2f -> primitive still wins %.0fx"
  % (min(BITS_RANGE), 2.0, K_LO, e_dig_matched(min(BITS_RANGE), 2.0, K_LO) / E_CORE_7))
P("  Margin to flip (a): CTRL x K would have to reach %.0f (published max %.0f) -- %.0fx beyond."
  % (10 * K_HI * E_FAB_N7 / e_dig_matched(max(BITS_RANGE), 10.0, K_HI), 10 * K_HI,
     E_FAB_N7 / e_dig_matched(max(BITS_RANGE), 10.0, K_HI)))

P("\n" + "-" * 96)
P("5d. A CONCLUSION THAT DOES FLIP: regime [4], expensive transcendentals (CORDIC)")
P("-" * 96)
ADD16 = 0.06
n_win = n_tot = 0
for b in BITS_RANGE:
    for c in CTRL_RANGE:
        for k in K_RANGE:
            n_tot += 1
            if 2 * b * 2 * ADD16 * c * k > E_FAB_1:
                n_win += 1
P("  E_cordic(b) = 2b x 2 x ADD16 x CTRL x K  vs  E_fab(1 cell) = %.1f pJ" % E_FAB_1)
P("  Published verdict: FAIL by 1.11x at b=4.30, CTRL=3, K=11.56 -- 'its narrowest defeat'.")
P("  Across the box the fabric WINS this regime in %d of %d points (e.g. b=5.73/CTRL=5/K=11.56"
  % (n_win, n_tot))
P("  -> wins 2.0x; b=3.86/CTRL=10/K=11.56 -> wins 2.7x).  The 1.11x defeat is NOT robust.")
lut16 = lambda c, k: (sram_pJ(0.016) + ADD8) * c * k
P("  It survives ONLY on the argument the file already gives: against a 16-entry exp LUT +")
P("  interpolation (%.2f-%.2f pJ across the box) the fabric loses %.1fx-%.0fx everywhere."
  % (lut16(2, K_LO), lut16(10, K_HI), E_FAB_1 / lut16(10, K_HI), E_FAB_1 / lut16(2, K_LO)))
P("  => 'the fabric fails in every regime' must be stated as 'fails in every regime against")
P("     the baseline a designer would actually build'; the CORDIC comparison is not load-bearing.")

P("\n" + "=" * 96)
P("6.  WHAT SURVIVES")
P("=" * 96)
P("""
  (a) 'the fabric loses to digital at every accuracy it can reach'  -- SURVIVES.
      Range %.0f-%.0fx over the entire box.  The floor is %.1fx, reached only by granting
      digital the Hameed 10x overhead AND the 5.73-bit slope ceiling the fabric never
      demonstrates.  Publish as: 'the fabric loses by one to two orders of magnitude
      (%.0f-%.0fx across the plausible range of digital-overhead and node-scaling
      assumptions)', not as a single 30x.

  (b) 'the bare primitive beats digital'  -- SURVIVES, range %.0f-%.0fx.  But 152x is the
      TOP of the range, obtained at CTRL=3/K=11.56 with the generous fixed 8-bit baseline.
      Publish as 'beats it by two orders of magnitude, %.0f-%.0fx'.

  (c) 'the gap between them is orders of magnitude'  -- SURVIVES UNCONDITIONALLY, and it is
      the ONLY one of the three that does.  H3 = E_fab/E_core contains no digital constant:
      it is 98.566 uW x 402 ns / (V_core I_core t_core), all from POWER.md and PEX_SHIPPED.
      It does not move by one part in a thousand across the whole box.  Quote %.0fx per cell
      (39.6 pJ / 13.0 fJ) or %.0fx for the N=7 fabric -- and say which.

  The paper's central result should be re-centred on (c), which is measurement-anchored and
  assumption-free, with (a) and (b) as ranges rather than point estimates.  BITS_ROOT should
  be replaced by %.2f bits (RESULTS.md run 3 median, 5.5 K over an 80 K span) and the fabric's
  reachable band stated as %.2f-%.2f bits.
""" % (lo1, hi1, lo1, lo1, hi1, lo2, hi2, lo2, hi2,
       E_FAB_1 / E_CORE_1, E_FAB_N7 / E_CORE_7,
       BITS_ANCHOR, L2(1.288 / 0.266), L2(1 / 0.0188)))
