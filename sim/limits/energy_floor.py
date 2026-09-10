#!/usr/bin/env python3
"""WHY the EML analog fabric loses on energy: derivation, floor, and win-regime tests.

Takes as GIVEN (prior work, this session): the fabric loses 28-51x on energy/eval to a
matched digital datapath at every accuracy, and 7-15x on accuracy to a matched-parameter
MLP.  This file explains those numbers rather than re-deriving them.

Hardware inputs are reused verbatim from paper/POWER.md, paper/FAB_AREA.md,
paper/FAB_ERROR.md and fabric_sim/energy/energy_area_compare.py.  Nothing is re-sourced.

Run: arch -arm64 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 energy_floor.py
"""
import math

P = print
L2 = math.log2

# ===================== MEASURED INPUTS (POWER.md / FAB_AREA.md / FAB_ERROR.md) =========
VDD = 3.3                 # V            POWER.md 1
I_VDD = 29.8686e-6        # A            POWER.md 1   one cell, die context, tt/27C
P_CELL = 98.566e-6        # W            POWER.md 1
I_PBIAS = 0.5e-6          # A            POWER.md, 1 unit
T1_PEX = 402e-9           # s            POWER.md 6   post-layout, 1 %, full-scale exp step
T01_PEX = 497e-9          # s            POWER.md 6   post-layout, 0.1 %
TAU = 45.9e-9             # s            POWER.md 3.1 full-scale exp step dominant tau
E_CELL_PEX = P_CELL * T1_PEX                       # 39.6 pJ, POWER.md 6

I_TAIL = 3.96e-6          # A            POWER.md 1.1  XMT_OT, the exp servo tail
CC_OT = 2e-12             # F            emlcell_b_sim12.inc  Miller compensation cap
C_EXPLICIT = 6e-12        # F            CFU+CC_OT+CFA+CFB+CGP = 1+2+1+1+1 pF
C_PEX_TOT = 1773e-15      # F            PEX_SHIPPED.md 1  sum of 1317 extracted caps
I_CORE = 3.9619e-6        # A            POWER.md 1.1  total collector current, 4 NPNs
V_CORE = 1.2              # V            POWER.md 1.1  core collectors sit near vrefb
A_CORE_FRAC = 0.027       # FAB_AREA.md  4 NPN = 2.7 % of the cell
A_SERVO_FRAC = 0.425      # FAB_AREA.md  4 servo amps = 42.5 % of the cell
P_SERVO_FRAC = 0.745      # POWER.md 1.1 servo amps = 74.5 % of supply current

BITS_MEAS = 2.28          # FAB_ERROR.md  1.288 u swing / 0.266 u sigma, per cell
# BITS_ROOT was 4.30, cited to "FAB_ERROR.md / RESULTS.md, best achievable at a tree root".
# NEITHER FILE CONTAINS IT.  It reproduces exactly as log2(1/0.050742) from multivar.json
# rows[60]: I.9.18, hw="ideal", the best of 8 seeds (the other 7 give 2.39-3.30 bits).
# That is an ideal-hardware, cherry-picked-seed regression NRMSE, not a root accuracy.
# RE-ANCHORED on the best-sourced measurement: RESULTS.md run 3, PDK chip, all
# non-idealities on, in-situ trained, beta-model MEDIAN of 8 seeds = 5.5 K RMSE over the
# 80 K training span -> NRMSE 5.5/80 = 0.06875 -> log2(1/0.06875) = 3.86 bits.
BITS_ROOT = math.log2(80.0 / 5.5)     # = 3.86   RESULTS.md run 3 median, 5.5 K / 80 K span
BITS_ROOT_BAND = (2.28, 5.73)         # FAB_ERROR.md: raw single cell .. un-trimmable
#                                       1.88 % ln-slope ceiling.  Quote the band, not a point.
# See limits/constants_sensitivity.py for the provenance trace and the full sensitivity box.

# physical constants
K = 1.380649e-23
Q = 1.602176634e-19
T = 300.0
VT = K * T / Q            # 25.85 mV
NSUB = 1.3                # subthreshold slope factor, sky130 5V nfet (typical)

# ===================== DIGITAL BASELINE (energy_area_compare.py, unchanged) ============
ADD8, ADD16, MUL8 = 0.03, 0.06, 0.20        # pJ @45nm, Horowitz ISSCC 2014
MUL16 = 0.20 * 4
# CTRL: RF/control/clock overhead on raw arithmetic.  Was disclosed as a GUESS; a published
# basis exists and lands on 3.0.  Balfour & Dally, "An Energy-Efficient Processor Architecture
# for Embedded Systems", IEEE CAL, Jan 2008: a 16-bit add costs 18 pJ, while the three
# accesses to a 16-entry register file it needs (2 operands + writeback) cost 36 pJ -- operand
# delivery is 2.0x the arithmetic, total 3.0x.  UPPER BOUND: Hameed et al., ISCA 2010, report
# functional-unit energy at < 10 % of total in a datapath SIMD-customised to 8-12 bit widths,
# i.e. CTRL ~ 10.  LOWER BOUND ~2 for a hardwired block with no RF.  RANGE [2, 10].
# 3.0 is the LOW end = the most fabric-UNFAVOURABLE choice in the published range.
CTRL = 3.0
# K_NODE: 45 nm @0.9 V -> 130 nm.  C ~ L gives 130/45 = 2.89; the voltage term is
# (1.8/0.9)^2 = 4.0 for a sky130 std-cell comparator (sky130_fd_sc_hd nominal rail 1.8 V),
# but only (1.2/0.9)^2 = 1.78 for a contemporaneous low-power 130 nm core rail -> K = 5.14.
# Empirical cross-check: ~2x energy/gate per node generation, 130->90->65->45 ~ 8x.
# RANGE [5.1, 11.6].  11.56 is the TOP end = the most fabric-FAVOURABLE choice.
K_NODE = (130 / 45) * (1.8 / 0.9) ** 2      # 11.56, 45nm@0.9V -> 130nm@1.8V
FOM_FJ = 34.0                               # fJ/conv-step, 130 nm SAR


def sram_pJ(kB):
    return 1.41 * kB ** 0.617


def dig130(raw45):
    return raw45 * CTRL * K_NODE


def conv_pJ(bits):
    return FOM_FJ * 2 ** bits / 1e3


E_DIG_4B = dig130(MUL8 + ADD8 + sram_pJ(0.032))   # 16-seg PWL 8b, the MATCHED baseline
E_FAB_N7 = (96.95 * 7 + 85.64 * 6 + 2.09) * 1e-6 * 1.19 * (166 + 65 * 2) * 1e-9 * 1e12

P("=" * 92)
P("PART 1  THE DERIVATION:  why bias current cancels out of energy per evaluation")
P("=" * 92)
P("""
A translinear cell is a current-mode circuit held at its operating point by servo
amplifiers.  Two facts fix its energy per evaluation:

  (a) POWER is proportional to bias current.   MEASURED, POWER.md 2.3:
      P_vdd = 204.4 * pbias[uA] - 2.9 uW  over an 8:1 range, i.e. P = k_I * I.
      Every leg is a fixed-ratio mirror of pbias, so k_I = V_dd * (I_vdd/I_pbias).

  (b) SETTLING TIME is proportional to C / gm, and in the subthreshold /
      translinear regime gm = I_branch / (n V_T).   Therefore

          t_settle = N_tau * C / gm = N_tau * C * n V_T / I_branch    ~  1/I.

  Multiply:   E = P * t = [V_dd * I_vdd] * [N_tau * C * n V_T / I_branch]

          +--------------------------------------------------------+
          |   E_op  =  F * N_tau * C * V_dd * n * V_T               |
          |   with  F = I_vdd / I_branch   (the scaffolding fanout) |
          +--------------------------------------------------------+

  The bias current CANCELS EXACTLY.  Not approximately -- it appears once in the
  numerator (power) and once in the denominator (bandwidth) with the same exponent.
  Scaling the whole fabric to nanoamps buys nothing: it buys proportionally less
  power and proportionally more time.  Note the form is C*V_dd*(n V_T), NOT C*V^2:
  analog settling is exponential, so the second voltage is the thermal voltage times
  the number of e-folds you demand, not the supply rail.
""")

F = I_VDD / (I_TAIL / 2)          # input-pair branch current is I_tail/2
N_TAU_MEAS = T1_PEX / TAU
P("  FORWARD PREDICTION from device physics, nothing fitted:")
P("    C  = CC_OT (Miller comp. on the exp servo)          = %.2f pF" % (CC_OT * 1e12))
P("    I_branch = I_tail/2 (XMT_OT input pair)             = %.3f uA" % (I_TAIL / 2 * 1e6))
gm_pred = (I_TAIL / 2) / (NSUB * VT)
tau_pred = CC_OT / gm_pred
P("    gm = I_branch/(n V_T), n=%.1f, V_T=%.2f mV          = %.1f uS" % (NSUB, VT * 1e3, gm_pred * 1e6))
P("    tau = C/gm                             PREDICTED    = %.1f ns" % (tau_pred * 1e9))
P("    tau                                    MEASURED     = %.1f ns  (POWER.md 3.1, 38-57 ns range)" % (TAU * 1e9))
P("    ratio predicted/measured = %.2f  -- a forward prediction good to %.0f %%\n"
  % (tau_pred / TAU, abs(tau_pred / TAU - 1) * 100))

N_TAU = 8.75                       # e-folds actually needed to 1 % (see below)
E_pred = F * N_TAU_MEAS * CC_OT * VDD * NSUB * VT
P("    F = I_vdd / I_branch                                = %.1f  (scaffolding fanout)" % F)
P("    N_tau = t_1%%/tau                                    = %.1f e-folds" % N_TAU_MEAS)
P("    E = F * N_tau * C * V_dd * n V_T       PREDICTED    = %.1f pJ" % (E_pred * 1e12))
P("    E = P_cell * t_1%% (post-layout)        MEASURED     = %.1f pJ  (POWER.md 6)" % (E_CELL_PEX * 1e12))
P("    ratio = %.2f  -> THE DERIVATION IS CONFIRMED to %.0f %%\n" % (E_pred / E_CELL_PEX, abs(E_pred / E_CELL_PEX - 1) * 100))

P("=" * 92)
P("PART 1b  DIRECT TEST OF BIAS INVARIANCE  (NEW MEASUREMENT, bias_sweep.py)")
P("=" * 92)
P("""
POWER.md 2.3 measured P vs pbias.  Nobody had measured t_settle vs pbias, so E(I) was
never tested.  bias_sweep.py does it: same netlist, same die context, same normalised
operating point and same full-scale exp step at 4 bias points over an 8:1 range,
tt/27C, gear/maxord=2, 2 ns grid.  MEASURED:
""")
SW = [(0.125, 7.1346, 23.544, 821.0, 121.0, 19.33),
      (0.250, 14.5270, 47.939, 458.9, 61.0, 22.00),
      (0.500, 29.5979, 97.673, 342.9, 45.9, 33.49),
      (1.000, 60.2693, 198.889, 342.8, 49.2, 68.17)]
P("  %-10s %10s %9s %9s %8s %10s" % ("pbias/uA", "I_vdd/uA", "P/uW", "t1%/ns", "tau/ns", "E1%/pJ"))
for r in SW:
    P("  %-10.3f %10.4f %9.3f %9.1f %8.1f %10.2f%s" % (r + ("   <-- as shipped" if r[0] == 0.5 else "",)))
P("""
  Piecewise log-log exponents (E ~ I^p):

    bias range        tau exponent      E exponent     regime
    0.125 -> 0.25 uA     -0.99            +0.19        SUBTHRESHOLD: hypothesis HOLDS
    0.25  -> 0.50 uA     -0.41            +0.61        knee
    0.50  -> 1.00 uA     +0.10            +1.03        RC-LIMITED: hypothesis FAILS

  THE HYPOTHESIS IS CONFIRMED EXACTLY -- BUT ONLY BELOW A KNEE, AND THE SHIPPED PART
  SITS ON THE WRONG SIDE OF IT.

  * Below 250 nA the cancellation is essentially perfect: tau ~ I^-0.99 against the
    predicted I^-1.0, and energy moves only 19.33 -> 22.00 pJ (I^+0.19) for a 2x change
    in bias.  Scaling to nanoamps buys nothing, exactly as predicted.
  * Above 500 nA the cancellation BREAKS: tau stops falling (+0.10, i.e. flat) and energy
    becomes strictly proportional to bias current (I^+1.03).  Extra current buys zero
    speed and costs proportional power.  This is pure waste.
  * WHY: a current-INDEPENDENT pole takes over.  The exp path runs through RU
    (res_high_po, L=45.76, = 51.5 kohm, POWER.md 3.4) into CFU = 1 pF.
    RU * CFU = 51.5 ns -- and the measured tau floors at 45.9-49.2 ns.  Once C/gm falls
    below the fixed RC of the signal path, gm no longer sets the bandwidth and the
    denominator of E = P*t stops tracking I.  The floor is a RESISTOR, not a transistor.
  * CONSEQUENCE: the shipped 500 nA bias is at or past the knee.  The cell would be
    %.2fx CHEAPER per evaluation at 125 nA (19.33 vs 33.49 pJ) at the price of 2.4x
    latency -- and POWER.md 2.3 notes bias current is the paper's accuracy lever, so
    that saving is paid for in bits.  Even so: 19.33 pJ is still %.1fx a whole
    %.1f pJ digital datapath, for ONE of the seven cells the task needs.
  * So the practical statement is stronger than the hypothesis, not weaker:
    THERE IS NO BIAS CURRENT AT WHICH THIS FABRIC IS CHEAP.  Lowering bias hits a
    floor of ~19 pJ/cell; raising it is strictly wasted energy.  The lever does not exist.
""" % (33.49 / 19.33, 19.33 / E_DIG_4B, E_DIG_4B))

P("=" * 92)
P("PART 2  IS THE FLOOR SET BY kT/C NOISE?   -- the hypothesis fails here")
P("=" * 92)
P("""
The hypothesis says C is bounded below by kT/C noise at the required SNR, giving a
hard thermodynamic floor.  Evaluate it: a sampled node with swing V_sig has
v_n^2 = kT/C, so SNR = 2^b demands  C >= kT * 2^(2b) / V_sig^2.
""")
P("  %-8s %14s %14s %14s" % ("bits", "C_min (kT/C)", "vs CC_OT=2pF", "E floor if C=C_min"))
for b in [2.28, 4.3, 8, 10, 12, 14, 16, 18]:
    Cmin = K * T * 4 ** b / 1.0 ** 2          # V_sig = 1 V, the cell's actual swing
    Ef = F * N_TAU_MEAS * Cmin * VDD * NSUB * VT
    P("  %-8.2f %11.3e F %13.1e %13.3e J" % (b, Cmin, Cmin / CC_OT, Ef))
b_bind = 0.5 * math.log2(CC_OT * 1.0 ** 2 / (K * T))
P("""
  VERDICT: THE kT/C HALF OF THE HYPOTHESIS IS WRONG, AND WRONG BY 6 ORDERS OF MAGNITUDE.
  At the fabric's actual precision (%.2f-%.2f bits) kT/C permits C = %.1e F -- ATTOFARADS.
  The 2 pF that is actually there is %.0e times larger than noise requires.
  kT/C does not bind until b = %.1f bits with a 1 V swing.
""" % (BITS_MEAS, BITS_ROOT, K * T * 4 ** BITS_ROOT, CC_OT / (K * T * 4 ** BITS_ROOT), b_bind))
P("""  So what DOES set C?  Three things, all architectural, none thermodynamic:
    1. STABILITY.  CC_OT = 2 pF is a Miller compensation capacitor.  It exists to give
       the servo loop phase margin.  Its size is set by the loop's non-dominant pole,
       not by noise.  PEX_CHAIN/PEX_SHIPPED record that the BUFFERED variant rang in
       15 of 25 corners; the shipped cell is stable, and 2 pF is what bought that.
    2. PARASITICS.  The extracted cell carries 1773 fF over 1317 capacitors
       (PEX_SHIPPED.md 1) before any deliberate cap, and parasitics cost +19 %% of
       settling time (POWER.md 6).  That is a lithographic floor, not a noise floor.
    3. MATCHING, not noise, sets the precision.  FAB_ERROR.md measures 1.288 u of
       swing against 0.266 u of LEVEL SIGMA = 2.28 bits.  That sigma is device
       mismatch and servo offset -- static, uncorrelated with bandwidth, and NOT
       reducible by spending charge.  A 1.88 %% ln-slope mismatch caps the root at
       5.73 bits and "no offset trim removes" it.  The fabric is mismatch-limited,
       not noise-limited, so the kT/C argument never engages.
""")

P("=" * 92)
P("PART 3  THE REAL FLOOR, AND HOW FAR ABOVE IT THE FABRIC SITS")
P("=" * 92)
P("""
The correct fundamental floor for a current-mode translinear circuit is SHOT noise on
the delivered charge, not kT/C on a stored voltage.  Deliver charge Q = I_sig * t through
a junction; Poisson statistics give sigma_Q = sqrt(q Q), so SNR = sqrt(Q/q).  Hence

        Q_min = q * 4^b      and      E_min = V_swing * q * 4^b.

This is Sarpeshkar's scaling: analog cost grows as 4^b (2 bits per 4x charge), while a
digital datapath's cost grows roughly LINEARLY in bit width for adders and quadratically
for multipliers -- i.e. polynomially in b, against the analog exponential.  That is
exactly why he concludes analog is more efficient at LOW precision and digital wins at
HIGH precision, with the crossover at intermediate precision (his stated figure is of
order 8-10 bits for the technologies he analysed; the qualitative claim -- exponential
vs polynomial in b -- is the load-bearing part and is reproduced below).
""")
P("  %-8s %14s %16s %16s" % ("bits", "E_min shot (J)", "E_dig130 (J)", "analog/digital"))
for b in [2.28, 4.3, 8, 10, 12, 13, 14, 16]:
    Emin = 1.0 * Q * 4 ** b
    # digital: b-bit multiply+add+small LUT, width-scaled off the Horowitz points
    raw = MUL8 * (b / 8) ** 2 + ADD8 * (b / 8) + sram_pJ(0.032 * (b / 8))
    Ed = dig130(raw) * 1e-12
    P("  %-8.2f %11.3e   %13.3e   %14.1e" % (b, Emin, Ed, Emin / Ed))
# crossover
lo, hi = 2.0, 24.0
for _ in range(200):
    m = (lo + hi) / 2
    raw = MUL8 * (m / 8) ** 2 + ADD8 * (m / 8) + sram_pJ(0.032 * (m / 8))
    if 1.0 * Q * 4 ** m < dig130(raw) * 1e-12:
        lo = m
    else:
        hi = m
P("\n  CROSSOVER (fundamental analog floor = this 130 nm digital datapath): b* = %.1f bits" % lo)
P("  Sarpeshkar's regime claim is REPRODUCED: below b* analog is fundamentally cheaper.")
P("  The fabric operates at %.2f-%.2f bits -- 9 to 11 bits INSIDE the analog-wins regime." % (BITS_MEAS, BITS_ROOT))
E_floor_root = 1.0 * Q * 4 ** BITS_ROOT
P("""
  AND YET IT LOSES.  Quantify the gap:
    fundamental shot-noise floor at %.2f bits          = %.2e J  (%.3f fJ)
    what one cell actually costs (POWER.md 6)         = %.2e J  (%.1f pJ)
    ratio                                             = %.1e
    equivalently: the cell spends the charge of a %.1f-bit computation to deliver %.2f bits.
""" % (BITS_ROOT, E_floor_root, E_floor_root * 1e15, E_CELL_PEX, E_CELL_PEX * 1e12,
       E_CELL_PEX / E_floor_root, 0.5 * L2(E_CELL_PEX / (1.0 * Q)), BITS_ROOT))

P("=" * 92)
P("PART 4  THE RECONCILIATION:  what would it cost if the scaffolding were free?")
P("=" * 92)
P("""
The measured asymmetry (POWER.md 1.1 / FAB_AREA.md): the four bipolar junctions that
actually evaluate eml are 2.7 %% of cell area and draw 0 %% DIRECTLY from the 3.3 V rail
(13.3 %% of supply current, at 1.2 V collectors).  The four servo amplifiers that exist
only to hold their operating points are 42.5 %% of area and 74.5 %% of supply current.

Price the bare translinear core.  It carries I_core = %.3f uA at V_core = %.1f V.  Its own
capacitance is junction + local wiring only -- no Miller compensation, because with no
servo loop there is no loop to compensate.  Take C_core from the extracted total scaled
by the core's area share, a deliberately PESSIMISTIC estimate (the core is resistors and
NPNs, which are not the capacitive part of the cell).
""" % (I_CORE * 1e6, V_CORE))
C_core = C_PEX_TOT * A_CORE_FRAC          # 47.9 fF, pessimistic
gm_core = I_CORE / VT                      # BJT: gm = Ic/VT, no n
tau_core = C_core / gm_core
t_core = N_TAU_MEAS * tau_core
E_core = V_CORE * I_CORE * t_core
P("    C_core = C_pex * 2.7 %%                 = %.1f fF" % (C_core * 1e15))
P("    gm_core = I_c / V_T  (BJT, n = 1)     = %.1f uS" % (gm_core * 1e6))
P("    tau_core                              = %.2f ns   (vs %.1f ns for the servoed cell)" % (tau_core * 1e9, TAU * 1e9))
P("    t_settle = %.1f tau                    = %.1f ns   (vs %.0f ns measured)" % (N_TAU_MEAS, t_core * 1e9, T1_PEX * 1e9))
P("    E_core = V_core * I_core * t_settle   = %.1f fJ   (vs %.0f fJ measured)" % (E_core * 1e15, E_CELL_PEX * 1e15))
P("\n    ---> THE SCAFFOLDING TAX IS %.0fx IN ENERGY PER CELL." % (E_CELL_PEX / E_core))
P("         (compare: %.0fx in area, %.1fx in supply current -- energy is the harshest of the three)"
  % (A_SERVO_FRAC / A_CORE_FRAC, P_SERVO_FRAC / 0.133))

P("\n  Does the scaffolding-free fabric beat digital?  Use the same 7-cell, %.2f-bit task" % BITS_ROOT)
P("  (RESULTS.md run 3 median, 5.5 K over an 80 K span -- see BITS_ROOT above)")
P("  that the matched comparison used (energy_area_compare.py CASE 1):")
P("    fabric as built,   N=7 d=3        = %8.1f pJ" % E_FAB_N7)
P("    digital datapath, 8b PWL baseline = %8.2f pJ   -> fabric loses %.0fx  [PRIOR RESULT, reproduced]"
  % (E_DIG_4B, E_FAB_N7 / E_DIG_4B))
E_ideal7 = 7 * E_core * 1e12
P("    7 bare translinear cores          = %8.4f pJ   -> IDEAL CORE BEATS DIGITAL BY %.0fx"
  % (E_ideal7, E_DIG_4B / E_ideal7))
P("""
  So Sarpeshkar is not contradicted -- he is CONFIRMED, on this very circuit.  The
  primitive is %.0fx cheaper than the digital datapath at 4 bits, exactly as his argument
  predicts for the low-precision regime.  The fabric loses anyway because it pays a
  %.0fx tax to make that primitive addressable, composable and stable.

  SENSITIVITY (constants_sensitivity.py):  the 30x and the 152x are NOT robust point values.
  Over CTRL in [2,10] x K_NODE in [5.1,11.6] x BITS_ROOT in [2.28,5.73] they range 12-404x
  and 12-402x respectively.  Their PRODUCT is invariant -- it is E_fab/E_core, in which no
  digital constant appears at all.  The composability tax (3046x per cell, 4624x for the
  N=7 fabric) is the only one of the three headlines that is assumption-free.  It should be
  the stated central result, with the other two given as ranges rather than point estimates.

  THE CENTRAL RESULT:  a single-primitive analog fabric pays a COMPOSABILITY OVERHEAD
  that swamps the primitive's efficiency.  The overhead is not a defect of this layout;
  it is what the primitive needs in order to be a fabric element rather than a curiosity:
    - servo amplifiers, because a translinear loop only holds its law if its collector
      voltages are pinned (42.5 %% of area, 74.5 %% of current, and they set F = %.1f);
    - Miller caps, because the servos are feedback loops that must not ring
      (2 pF each, and C is the OTHER term in E = F*N_tau*C*V_dd*n*V_T);
    - weight DACs and config flops, because a fabric must be programmable
      (27.4 %% of fabric area, FAB_AREA.md; and the LINK costs 88 %% of a cell in power
      against 28 %% in area, POWER.md 4.2).
  Every one of those is a consequence of composability, not of the exp/ln primitive.
  Both terms in the energy law -- F and C -- are scaffolding terms.  The primitive
  contributes NEITHER.
""" % (E_DIG_4B / E_ideal7, E_CELL_PEX / E_core, F))

# at what precision does the SCAFFOLDED cell beat digital?
P("  At what precision would the fabric AS BUILT beat digital?  Solve E_fab(N=7) = E_dig(b):")
lo, hi = 2.0, 64.0
for _ in range(300):
    m = (lo + hi) / 2
    raw = MUL8 * (m / 8) ** 2 + ADD8 * (m / 8) + sram_pJ(0.032 * (m / 8))
    if dig130(raw) < E_FAB_N7:
        lo = m
    else:
        hi = m
P("    b = %.1f bits.  The fabric delivers %.2f.  It would have to be %.0f bits more accurate"
  % (lo, BITS_ROOT, lo - BITS_ROOT))
P("    than it is, in a design whose mismatch caps it at 5.73 bits (FAB_ERROR.md).  Unreachable.\n")

P("=" * 92)
P("PART 5  WHERE COULD IT WIN?  Each regime as an inequality, then evaluated.")
P("=" * 92)
E_FAB_1 = E_CELL_PEX * 1e12
RATE_MAX_1 = 1 / T1_PEX
RATE_MAX_7 = 1e9 / (1.19 * (166 + 65 * 2))
P_FAB_7 = (96.95 * 7 + 85.64 * 6 + 2.09) * 1e-6

res = []


def verdict(name, cond, lhs, rhs, ok, note):
    res.append((name, ok))
    P("\n[%d] %s" % (len(res), name))
    P("    condition : %s" % cond)
    P("    evaluated : %s  vs  %s" % (lhs, rhs))
    P("    VERDICT   : %s -- %s" % ("WIN" if ok else "FAIL", note))


# --- R1 very low precision
raw2 = MUL8 * (2 / 8) ** 2 + ADD8 * (2 / 8) + sram_pJ(0.032 * (2 / 8))
E_dig_2b = dig130(raw2)
verdict("VERY LOW PRECISION (< 4 bits): digital still pays a full datapath",
        "E_fab(1 cell) < E_dig(b)   for b < 4",
        "E_fab = %.1f pJ (ONE cell, the indivisible quantum)" % E_FAB_1,
        "E_dig(2 b) = %.3f pJ" % E_dig_2b,
        E_FAB_1 < E_dig_2b,
        "digital gets CHEAPER as precision falls (a 4-entry LUT is nearly free) while the\n"
        "                fabric does not: 98.57 uW and 402 ns are fixed costs paid at ANY precision.\n"
        "                Analog has no sub-linear low-precision mode here. Loses by %.0fx." % (E_FAB_1 / E_dig_2b))

# --- R2 always-on continuous-time
f_break_1 = P_CELL / (E_DIG_4B * 1e-12)
f_break_7 = P_FAB_7 / (E_DIG_4B * 1e-12)
verdict("ALWAYS-ON CONTINUOUS-TIME MONITORING (neither side can duty-cycle)",
        "P_fab < E_dig * f_required   AND   f_required <= 1/t_settle (feasibility)",
        "f_break-even = P_fab/E_dig = %.1f MHz (1 cell) / %.1f MHz (N=7)" % (f_break_1 / 1e6, f_break_7 / 1e6),
        "f_max = 1/t_settle = %.2f MHz (1 cell) / %.2f MHz (N=7)" % (RATE_MAX_1 / 1e6, RATE_MAX_7 / 1e6),
        f_break_1 < RATE_MAX_1,
        "the two conditions are MUTUALLY EXCLUSIVE. The fabric must be re-evaluated\n"
        "                %.1fx (1 cell) to %.0fx (N=7) faster than it can physically settle. Its own\n"
        "                bandwidth ceiling closes the door its static power opens. This is structural:\n"
        "                E = P*t means break-even rate = 1/t_dig, and t_dig << t_analog always."
        % (f_break_1 / RATE_MAX_1, f_break_7 / RATE_MAX_7))

# --- R3 analog-in analog-out
deficit = E_FAB_N7 - E_DIG_4B
for badc in [4, 8, 10, 12]:
    n_need = deficit / conv_pJ(badc)
    if badc == 8:
        n8 = n_need
P("\n[%d] ANALOG-IN / ANALOG-OUT: the fabric skips conversion the digital path must pay" % (len(res) + 1))
P("    condition : n_ports * E_conv(b_sensor) > E_fab - E_dig")
P("    evaluated : deficit to make up = %.0f pJ;  E_conv = %.1f fJ/conv-step x 2^b" % (deficit, FOM_FJ))
for badc in [4, 8, 10, 12]:
    P("                b_sensor=%2d b: E_conv=%8.2f pJ -> need %7.1f conversions/eval" % (badc, conv_pJ(badc), deficit / conv_pJ(badc)))
P("                a 7-cell fabric HAS AT MOST 14 input ports (2 per cell, FAB_AREA 1.2)")
res.append(("ANALOG-IN/ANALOG-OUT", False))
P("    VERDICT   : FAIL -- at a FAIR converter width (the fabric answers to %.2f bits, so a" % BITS_ROOT)
P("                4-6 bit converter is what the digital path needs) you would need %.0f to %.0f" % (deficit / conv_pJ(6), deficit / conv_pJ(4)))
P("                conversions per evaluation against 14 available ports: short by %.0f-%.0fx." % (deficit / conv_pJ(6) / 14, deficit / conv_pJ(4) / 14))
P("                It only closes if you grant the digital side 10-12 bit converters it does")
P("                not need (%.0f-%.0f conversions), which is not a fair comparison." % (deficit / conv_pJ(10), deficit / conv_pJ(12)))

# --- R4 expensive digital: CORDIC
P("\n[%d] EXPENSIVE TRANSCENDENTALS (CORDIC: ~1 iteration per bit)" % (len(res) + 1))
P("    condition : E_fab(1 cell) < 2 * b * E_cordic_iter    [one eml cell = exp AND ln, so 2 CORDICs]")
E_iter45 = 2 * ADD16      # shift is free, 1 add + 1 compare
E_cordic = lambda b: dig130(2 * b * E_iter45)
P("    evaluated : E_fab = %.1f pJ (ONE cell)" % E_FAB_1)
for b in [2.28, 3, 4, 4.3, 6, 8, 16]:
    P("                b=%5.2f: 2 CORDICs = %7.1f pJ  -> fabric %s by %.2fx"
      % (b, E_cordic(b), "WINS" if E_cordic(b) > E_FAB_1 else "loses",
         max(E_cordic(b) / E_FAB_1, E_FAB_1 / E_cordic(b))))
b_x = E_FAB_1 / dig130(2 * E_iter45)
E_lut4 = dig130(sram_pJ(0.016) + ADD8)     # 16-entry exp LUT + interpolation add
res.append(("EXPENSIVE TRANSCENDENTALS (CORDIC)", False))
P("    crossover : b* = %.2f bits.  The fabric delivers %.2f at a tree root -- it MISSES the"
  % (b_x, BITS_ROOT))
P("                crossover by %.2f bits and loses by %.2fx, its narrowest defeat anywhere."
  % (b_x - BITS_ROOT, E_FAB_1 / E_cordic(BITS_ROOT)))
P("    VERDICT   : FAIL, but this is the CLOSEST regime and it is worth stating precisely why.")
P("                (i) The margin is only %.2fx -- inside the +-19 %% parasitic and +-4.6 %% corner" % (E_FAB_1 / E_cordic(BITS_ROOT)))
P("                     spread, so this regime is a genuine near-miss rather than a rout.  IN FACT")
P("                     IT IS NOT ROBUST AT ALL: over the published ranges CTRL in [2,10] and")
P("                     K_NODE in [5.1,11.6] and BITS_ROOT in [2.28,5.73], the fabric WINS this")
P("                     regime in 24 of 72 corners (constants_sensitivity.py 5d).  This verdict")
P("                     therefore rests entirely on (ii), not on the CORDIC arithmetic.")
P("                (ii) It vanishes the instant digital is allowed a LUT instead of CORDIC:")
P("                     a 16-entry exp LUT + interpolation costs %.2f pJ, and the fabric loses %.0fx."
  % (E_lut4, E_FAB_1 / E_lut4))
P("                     NOBODY COMPUTES A 4-BIT EXPONENTIAL WITH CORDIC. At 4 bits a LUT has 16")
P("                     entries. CORDIC is only the right baseline at >=12 bits -- precisely where")
P("                     the fabric cannot go (mismatch caps it at 5.73 bits, FAB_ERROR.md).")
P("                (iii) It holds for ONE cell only. Any real function needs a tree, and each link")
P("                     costs 85.64 uW = 88 %% of a cell (POWER.md 4.2), so N=7 loses %.0fx." % (E_FAB_N7 / E_cordic(BITS_ROOT)))

# --- R5 high-dimensional interpolation, LUT blow-up
P("\n[%d] HIGH-DIMENSIONAL INTERPOLATION (LUT cost N^d)" % (len(res) + 1))
P("    condition : E_fab < min( E_LUT(N^d), E_closedform, E_MLP )")
P("    evaluated : d=9, 8b axes -> 256^9 = %.1e bytes: LUT INFEASIBLE, as claimed." % (256.0 ** 9))
d9 = dig130(9 * MUL8 + 5 * ADD8 + sram_pJ(0.256))
P("                BUT the digital escape hatch is not a LUT, it is the closed form:")
P("                I.9.18 (9 vars) as 9 mul + 5 add = %.1f pJ, exact to 8 bits." % d9)
E_f32 = (96.95 * 32 + 85.64 * 31 + 2.09) * 1.19 * (166 + 65 * 3) * 1e-3   # uW x ns -> pJ
P("                fabric N=32 d=4 = %.0f pJ at 4.7 bits (IDEAL hw) -> loses %.0fx." % (E_f32, E_f32 / d9))
res.append(("HIGH-DIM INTERPOLATION", False))
P("    VERDICT   : FAIL -- the LUT^d blow-up is real but it is a straw man: digital only")
P("                uses a LUT when no closed form exists, and when none exists the comparison")
P("                is against an MLP, where PRIOR WORK ALREADY MEASURED the fabric losing")
P("                7-15x on ACCURACY at matched parameter count. Both exits are closed.")

# --- R6 my own: the scaffolding-free successor
P("\n[%d] [OWN] A SCAFFOLDING-FREE SUCCESSOR -- the only regime the derivation actually opens" % (len(res) + 1))
P("    condition : E = F*N_tau*C*V_dd*n*V_T  <  E_dig.  Three levers, all architectural.")
P("    evaluated : as built  F=%.1f, C=%.0f fF, V_dd=%.1f V   -> %.1f pJ/cell" % (F, CC_OT * 1e15, VDD, E_FAB_1))
for lbl, f2, c2, v2 in [("open-loop core, no servo   ", 1.0, C_core, V_CORE),
                        ("+ 1.2 V rail               ", 1.0, C_core, 1.2),
                        ("F=3 (partial servo), 100 fF", 3.0, 100e-15, 1.8),
                        ("F=15 but C=100 fF (no comp)", F, 100e-15, VDD)]:
    e2 = f2 * N_TAU_MEAS * c2 * v2 * (1.0 if c2 == C_core else NSUB) * VT
    P("                %s F=%4.1f C=%5.0f fF V=%.1f -> %8.4f pJ/cell (7 cells: %7.3f pJ, vs digital %.1f pJ)"
      % (lbl, f2, c2 * 1e15, v2, e2 * 1e12, 7 * e2 * 1e12, E_DIG_4B))
res.append(("SCAFFOLDING-FREE SUCCESSOR", True))
P("    VERDICT   : WIN, by up to %.0fx -- BUT the levers are exactly the composability" % (E_DIG_4B / E_ideal7))
P("                machinery. F=1 means no servo, so collector voltages float and the")
P("                translinear law fails (POWER.md: the ln port IS a servo-held node).")
P("                C=50 fF means no Miller compensation, and PEX_SHIPPED records the")
P("                uncompensated variant RINGING in 15 of 25 corners. The win is available")
P("                only to a circuit that is no longer a programmable fabric.")

P("\n" + "=" * 92)
P("SUMMARY OF REGIME TESTS")
P("=" * 92)
for i, (n, ok) in enumerate(res, 1):
    P("  [%d] %-45s %s" % (i, n, "WIN" if ok else "FAIL"))
P("""
  5 of 6 regimes fail on measured numbers. The 6th wins only by deleting the scaffolding,
  which is the same as saying: THE PRIMITIVE WINS, THE FABRIC LOSES, AND THE DIFFERENCE
  BETWEEN THEM IS THE PAPER. The fabric's energy law contains no term belonging to eml.
""")
