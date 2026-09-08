#!/usr/bin/env python3
"""Energy and area per function evaluation: EML analog fabric vs digital datapath vs LUT.

All hardware inputs traced to paper/POWER.md, paper/FAB_AREA.md, paper/FAB_ERROR.md,
paper/FAB_SPICE.md and fabric_sim/RESULTS.md + results/multivar.json.
Digital inputs: Horowitz ISSCC 2014 45 nm @0.9 V; 130 nm SAR ADC FoM.
Run with: arch -arm64 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12
"""

# ---------------- FABRIC (sky130, 130 nm, 3.3 V) --------------------------
# TWO per-cell power figures circulate; both are correct, in different contexts.
#   98.566 uW  MEASURED (POWER.md 1): one emlcell_b, die context, tt/27C, nominal operating
#              point.  Use for a SINGLE ISOLATED CELL -> the 39.6 pJ figure.
#   96.95  uW  FITTED (POWER.md 4.2): mean of cell A (98.62) and cell B (95.27) in the
#              measured 2-cell chain.  It is the coefficient that makes P(N) reproduce the
#              MEASURED chain total: 96.95*2 + 85.64 + 2.09 = 281.63 uW vs 281.622 measured.
#              Substituting 98.566 would give 284.86 uW, 1.15 % ABOVE a direct measurement.
#              Use for a CELL IN A CHAIN -> the 420.8 pJ figure.  Both headlines stand.
# The gap is NOT weight-DAC inclusion: POWER.md 4.1 records the alpha MDACs drawing < 0.1 nA
# at code 0 and their power at non-zero codes as NOT MEASURED.  BOTH figures therefore
# exclude weight-DAC switching energy, so every fabric energy number here is a LOWER BOUND.
P_CELL_UW = 96.95      # chain context: the fitted P(N) slope (POWER.md 4.2)
P_CELL_SOLO_UW = 98.566  # isolated cell: the measured value (POWER.md 1)
P_LINK_UW = 85.64      # POWER.md 4.2: chainglue + mdac_gamma + 5 flops
P_DIV_UW = 2.09        # POWER.md 5.2
A_FIX_UM2 = 24972.0    # POWER.md 5.2 / FAB_AREA.md: A(N) = 24972 + 23550 N
A_CELL_UM2 = 23550.0
PEX = 1.19             # POWER.md 6: parasitics cost +19 % of settling time
T_FIRST_NS = 166.0     # POWER.md 4.3: first stage, 1 % band, full-range step
T_STAGE_NS = 65.0      # POWER.md 5.2: each further stage, 1 % band (2-point, WEAK)


def fab_power_uw(n):
    return P_CELL_UW * n + P_LINK_UW * max(n - 1, 0) + P_DIV_UW


def fab_latency_ns(depth):          # fabric-FAVOURABLE: uses the fast 166 ns stage
    return PEX * (T_FIRST_NS + T_STAGE_NS * (depth - 1))


def fab_latency_ns_pess(depth):     # fabric-UNFAVOURABLE: 402 ns PEX single cell
    return 402.0 + PEX * T_STAGE_NS * (depth - 1)


def fab(n, depth):
    p, t = fab_power_uw(n), fab_latency_ns(depth)
    return dict(n=n, depth=depth, P_mW=p / 1e3, t_ns=t, E_pJ=p * 1e-6 * t * 1e-9 * 1e12,
                E_pJ_pess=p * 1e-6 * fab_latency_ns_pess(depth) * 1e-9 * 1e12,
                A_um2=A_FIX_UM2 + A_CELL_UM2 * n, rate_MHz=1e3 / t)


# ---------------- DIGITAL (Horowitz ISSCC 2014, 45 nm, Vdd 0.9 V) ---------
ADD8, ADD32, MUL8, MUL32 = 0.03, 0.10, 0.20, 3.10   # pJ, measured/published
FP32ADD, FP32MUL = 0.90, 3.70
ADD16 = ADD8 * 2                     # adders ~linear in width
MUL16 = MUL8 * (16 / 8) ** 2         # quadratic; reproduces MUL32=3.2 vs 3.1 published
INSTR_OVERHEAD_45 = 70.0             # pJ/instruction, general-purpose 45 nm core (Horowitz)
# CTRL: no longer a guess.  Balfour & Dally, IEEE Computer Architecture Letters, Jan 2008
# (Stanford ELM): 16-bit add = 18 pJ; the three 16-entry-RF accesses it needs = 36 pJ, so
# operand delivery is 2.0x the arithmetic and the total is 3.0x raw.  Range [2, 10]:
# lower = hardwired block, no RF; upper = Hameed et al. ISCA 2010, functional units < 10 %
# of a SIMD-customised datapath's energy.  3.0 is the LOW (fabric-unfavourable) end.
CTRL = 3.0


def sram_pJ(kB):                     # power fit through Horowitz (8 kB, 5 pJ), (1 MB, 100 pJ)
    return 1.41 * kB ** 0.617


# node normalisation 45 nm @0.9 V -> 130 nm @1.8 V, E ~ C V^2, C ~ L.
# C term 130/45 = 2.89; V term 4.0 at the sky130 std-cell 1.8 V rail, 1.78 at a 1.2 V
# low-power 130 nm core rail (K = 5.14).  Empirical ~2x/generation gives ~8x.
# RANGE [5.1, 11.6]; 11.56 is the TOP end, i.e. the most fabric-FAVOURABLE choice.
K_NODE = (130 / 45) * (1.8 / 0.9) ** 2   # = 11.56

# ADC/DAC: 34 fJ/conv-step, 10-bit 6.66 MS/s SAR in 130 nm CMOS (SBCCI 2017)
FOM_FJ = 34.0


def conv_pJ(bits):
    return FOM_FJ * 2 ** bits / 1e3


# sky130 SRAM macro of record: sky130_sram_1kbyte_1rw1r_32x256_8, 479.78 x 397.5 um
SRAM_1KB_UM2 = 479.78 * 397.5


def sram_area_um2(byte):
    return max(1.0, byte / 1024.0) * SRAM_1KB_UM2      # 1 kB is the smallest macro


def dig(mul16=0, add16=0, mul8=0, add8=0, lut_kB=0.0, instrs=None):
    raw = mul16 * MUL16 + add16 * ADD16 + mul8 * MUL8 + add8 * ADD8
    mem = sram_pJ(lut_kB) if lut_kB > 0 else 0.0
    dp45 = (raw + mem) * CTRL
    cpu45 = INSTR_OVERHEAD_45 * instrs if instrs else None
    return dict(raw45=raw + mem, dp45=dp45, dp130=dp45 * K_NODE,
                cpu130=cpu45 * K_NODE if cpu45 else None)


def bits(nrmse):
    import math
    return math.log2(1.0 / nrmse)


P = print
P("=" * 100)
P("NODE NORMALISATION  45 nm @0.9 V -> 130 nm @1.8 V  factor = %.2f   (E ~ C V^2, C ~ L)" % K_NODE)
P("Analog fabric is 130 nm @3.3 V native.  Digital numbers below are SCALED UP to 130 nm.")
P("=" * 100)

# ---------------- CASE 1: 1-D thermistor ----------------------------------
P("\n### CASE 1  1-D thermistor, T = f(R) over 80 K, depth-3 fabric = 7 cells")
f1 = fab(7, 3)
adc = conv_pJ(8)
P("fabric  N=7 d=3 : P=%.3f mW  t_settle(1%%)=%.0f ns  E=%.1f pJ (pess %.1f)  A=%.3f mm2  max %.2f MHz"
  % (f1['P_mW'], f1['t_ns'], f1['E_pJ'], f1['E_pJ_pess'], f1['A_um2'] / 1e6, f1['rate_MHz']))
P("  accuracy (RESULTS.md run 3, PDK chip, in-situ): median 5.5 K = %.1f%% of span = %.1f bits"
  % (5.5 / 80 * 100, bits(5.5 / 80)))
P("                                                   best/8  0.77 K = %.2f%%        = %.1f bits"
  % (0.77 / 80 * 100, bits(0.77 / 80)))
P("  + 8-bit ADC on the analog output: %.1f pJ (a digital path needs the same ADC on the sensor -> cancels)" % adc)

d4 = dig(mul8=1, add8=1, lut_kB=0.032, instrs=4)                       # 16-seg PWL, 8-bit
d7 = dig(mul16=2, add16=2, lut_kB=0.032, instrs=6)                     # quadratic, 16-bit
d13 = dig(mul16=4, add16=5, lut_kB=0.064, instrs=9)                    # ln + cubic log-poly
for lbl, acc, d in [("16-seg PWL 8b   ", "5.5 K  (3.86 b, MATCHED to fabric median -- THE ANCHOR)", d4),
                    ("quadratic 16b   ", "0.77 K (6.7 b, MATCHED to fabric best-of-8)", d7),
                    ("ln + cubic 16b  ", "0.0078 K (13.3 b, the 4-param log-poly)", d13)]:
    P("digital datapath %s: E=%7.1f pJ @130nm   (%.2f pJ raw @45nm)   -> %s"
      % (lbl, d['dp130'], d['raw45'], acc))
    P("      same on a general-purpose core (%.0f pJ/instr @45nm): %8.0f pJ @130nm" % (INSTR_OVERHEAD_45, d['cpu130']))

lut1 = sram_pJ(0.256) * K_NODE
P("LUT 1-D 8b in/8b out (256 B): E=%.1f pJ @130nm   A=%.3f mm2 (smallest sky130 SRAM macro is 1 kB)"
  % (lut1, sram_area_um2(256) / 1e6))
P("  ratio  fabric/datapath(matched 5.5 K) = %.0fx energy, %.1fx area"
  % (f1['E_pJ'] / d4['dp130'], f1['A_um2'] / sram_area_um2(256)))

# ---------------- CASE 2: 2-D Feynman with exp ----------------------------
P("\n### CASE 2  I.6.2 Gaussian (2 vars, needs exp), 32-cell mesh depth 4")
f2 = fab(32, 4)
P("fabric N=32 d=4 : P=%.3f mW  t=%.0f ns  E=%.0f pJ (pess %.0f)  A=%.3f mm2  max %.2f MHz"
  % (f2['P_mW'], f2['t_ns'], f2['E_pJ'], f2['E_pJ_pess'], f2['A_um2'] / 1e6, f2['rate_MHz']))
P("  accuracy (multivar.json, IDEAL hw, best of 3 seeds): NRMSE 0.0379 = %.1f bits  [ideal FAVOURS fabric]"
  % bits(0.0379))
d2 = dig(mul8=5, add8=3, lut_kB=0.256, instrs=8)      # sub, sq, scale, exp-LUT, scale
P("digital datapath 8b (exp via 256-B LUT): E=%.1f pJ @130nm, exact to 8 b = 7.8 bits" % d2['dp130'])
lut2 = sram_pJ(64) * K_NODE
P("LUT 2-D 8b axes (256x256 = 64 kB): E=%.0f pJ @130nm  A=%.2f mm2" % (lut2, sram_area_um2(65536) / 1e6))
P("  + 2 DAC in + 1 ADC out for the fabric if the system is digital: %.1f pJ" % (3 * adc))
P("  ratio  fabric/datapath = %.0fx energy, %.1fx area vs LUT" % (f2['E_pJ'] / d2['dp130'], f2['A_um2'] / sram_area_um2(65536)))

# ---------------- CASE 3: 5-D and 9-D -------------------------------------
P("\n### CASE 3  II.11.20 (5 vars) and I.9.18 Newtonian gravity (9 vars), 32-cell mesh depth 4")
for tgt, nv, best, med, ols, nmul, nadd in [("II.11.20", 5, 0.0735, 0.0948, 0.339, 4, 0),
                                            ("I.9.18  ", 9, 0.0507, 0.0738, 0.127, 9, 5)]:
    dd = dig(mul8=nmul, add8=nadd, lut_kB=0.256, instrs=nmul + nadd + 2)
    lut_bytes = 256 ** nv
    P("%s nv=%d : fabric E=%.0f pJ A=%.3f mm2, NRMSE best %.4f / med %.4f (IDEAL) = %.1f bits; OLS baseline %.3f"
      % (tgt, nv, f2['E_pJ'], f2['A_um2'] / 1e6, best, med, bits(best), ols))
    P("            digital datapath 8b, exact formula: E=%.0f pJ @130nm (%.0fx less) -> 7.8 bits"
      % (dd['dp130'], f2['E_pJ'] / dd['dp130']))
    P("            LUT 8b/axis: 256^%d = %.2e bytes  -> INFEASIBLE" % (nv, lut_bytes))
    P("            LUT 16 levels/axis (4 b, coarser than the fabric): 16^%d = %.2e bytes" % (nv, 16.0 ** nv))
    P("            + %d DAC in + 1 ADC out: %.1f pJ" % (nv, (nv + 1) * adc))

# ---------------- DUTY CYCLE ----------------------------------------------
P("\n### THE DUTY-CYCLE TEST -- static power, not switched charge (POWER.md 5.1)")
P("An isolated cell burns 98.57 uW (MEASURED) whether or not the input moves; a cell in a chain")
P("is fitted at 96.95 uW, which is what P(N) and the N=7 numbers above use. Both exclude weight-DAC")
P("switching power (unmeasured), so these are lower bounds. E/eval = P x (time you own the fabric).")
P("%-14s %14s %14s %14s" % ("eval rate", "fabric N=7 (J)", "datapath (J)", "fabric/datapath"))
for r, lbl in [(1, "1 Hz"), (1e3, "1 kHz"), (1e6, "1 MHz"), (f1['rate_MHz'] * 1e6, "2.84 MHz (max)")]:
    ef = f1['P_mW'] * 1e-3 / r
    ed = d4['dp130'] * 1e-12
    P("%-14s %14.3e %14.3e %14.0fx" % (lbl, ef, ed, ef / ed))
P("Break-even rate against the matched 8-b datapath: %.2e Hz -- i.e. the fabric must be re-evaluated"
  % (f1['P_mW'] * 1e-3 / (d4['dp130'] * 1e-12)))
P("faster than physically possible (%.2f MHz max) to break even. It never does." % f1['rate_MHz'])

# ---------------- CALIBRATION ---------------------------------------------
P("\n### CALIBRATION OVERHEAD (RESULTS.md: 8 seeds x 3000 Adam iters, best-of-8 required)")
cal = 8 * 3000 * 512 * 2 * f1['E_pJ'] * 1e-12
P("8 seeds x 3000 iters x 512 pts x 2 (fwd+grad) x %.0f pJ = %.2e J of fabric time alone (host cost excluded)"
  % (f1['E_pJ'], cal))
P("amortises below 1%% of operating energy after %.2e evaluations = %.1f s at max rate, %.0f days at 1 Hz"
  % (cal / (0.01 * f1['E_pJ'] * 1e-12), cal / (0.01 * f1['E_pJ'] * 1e-12) / (f1['rate_MHz'] * 1e6),
     cal / (0.01 * f1['E_pJ'] * 1e-12) / 86400))
