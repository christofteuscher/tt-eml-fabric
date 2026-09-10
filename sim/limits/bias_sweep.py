#!/usr/bin/env python3
"""DECISIVE TEST of the bias-invariance hypothesis.

E_op = P x t_settle.  POWER.md 2.3 measured P ~ linear in pbias.  Nobody has
measured t_settle vs pbias.  If t ~ 1/I then E = P*t is INDEPENDENT of bias
current and scaling the fabric to nanoamps buys nothing.

Sweeps pbias 0.125 -> 1.0 uA (8:1), same normalised operating point at every
bias (u,v and the step are all in `units` = pbias), full-scale exp step
u: -1.5 -> +1.0 with a 10 ns edge, die context (no external IOFF2/IOFF3),
tt/27C.  Reports I_vdd, t(1%), t(0.1%), tau and E = P*t.

Run: arch -arm64 /Library/.../python3.12 bias_sweep.py
"""
import os
import subprocess
import math

HERE = os.path.dirname(os.path.abspath(__file__))
CHAR = os.environ.get("EML_CHAR_DIR", os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "silicon", "char"))
SCR = "/private/tmp/claude-501/-Users-cteusche-data-projects-eml-code/ba189052-393c-4db9-9e17-5af5ba61feed/scratchpad/bias"
os.makedirs(SCR, exist_ok=True)

DECK = r"""* settling vs bias current -- die context, tt/27C
.lib $PDK_ROOT/sky130A/libs.tech/ngspice/sky130.lib.spice tt
.include {char}/emlcell_b_sim12.inc
.param iunit={iu}
VDD  vdd   0 3.3
VRB  vrefb 0 1.2
VE   ve    0 0.55
VOUT out   0 0.9
IPB  pbias 0 {{iunit}}
XPB  pbias pbias vdd vdd sky130_fd_pr__pfet_g5v0d10v5 L=8 W=4
IVIN 0 nv {{iunit}}
* u = -(driven IUIN).  step u: -1.5 -> +1.0  (full scale, 10 ns edge)
IUIN 0 nu PWL(0 {{1.5*iunit}} {{tstep0}} {{1.5*iunit}} {{tstep0+10n}} {{-1.0*iunit}})
XDUT nu nv out vdd vrefb ve pbias 0 nb0 nc2 ndl nsv emlcell_b
.options method=gear maxord=2 reltol=1e-5 abstol=1e-15 vntol=1e-9
.param tstep0=1u
.control
set noaskquit
op
print i(VDD) > {scr}/dc_{tag}.txt
tran {dt} {tstop} 0 {dt}
let io = i(VOUT)/{iu}
wrdata {scr}/tr_{tag}.dat io
.endc
.end
"""

# bias points: 8:1 range, same as POWER.md 2.3
BIAS = [0.125e-6, 0.25e-6, 0.5e-6, 1.0e-6]
# low bias is slower: scale tstop with 1/I so we always capture settling
procs = []
for iu in BIAS:
    tag = "%.0fn" % (iu * 1e9)
    scale = 0.5e-6 / iu
    tstop = 1e-6 + 6e-6 * scale
    dt = 2e-9
    deck = DECK.format(char=CHAR, iu=iu, scr=SCR, tag=tag, tstop=tstop, dt=dt)
    p = os.path.join(SCR, "d_%s.spice" % tag)
    open(p, "w").write(deck)
    procs.append((tag, iu, subprocess.Popen(["ngspice", "-b", p],
                  stdout=open(os.path.join(SCR, "log_%s.txt" % tag), "w"),
                  stderr=subprocess.STDOUT)))
for tag, iu, pr in procs:
    pr.wait()

print("%-8s %10s %10s %10s %10s %10s %10s %10s" %
      ("pbias", "I_vdd/uA", "P/uW", "t1%/ns", "t0.1%/ns", "tau/ns", "E1%/pJ", "E.1%/pJ"))
rows = []
for tag, iu, _ in procs:
    # DC supply current
    ivdd = None
    for ln in open(os.path.join(SCR, "dc_%s.txt" % tag)):
        if "i(vdd)" in ln.lower() and "=" in ln:
            ivdd = abs(float(ln.split("=")[-1]))
    t, y = [], []
    for ln in open(os.path.join(SCR, "tr_%s.dat" % tag)):
        f = ln.split()
        if len(f) >= 2:
            try:
                t.append(float(f[0])); y.append(float(f[1]))
            except ValueError:
                pass
    t0 = 1e-6
    i0 = max(i for i, tv in enumerate(t) if tv <= t0)
    y_i, y_f = y[i0], y[-1]
    amp = y_f - y_i

    def settle(frac):
        band = abs(amp) * frac
        last = i0
        for i in range(i0, len(t)):
            if abs(y[i] - y_f) > band:
                last = i
        return (t[last] - t0) * 1e9

    t1, t01 = settle(0.01), settle(0.001)
    # dominant tau from log-linear fit over the 50% -> 0.5% residual band
    xs, ys = [], []
    for i in range(i0, len(t)):
        r = abs(y[i] - y_f) / abs(amp)
        if 0.005 < r < 0.5:
            xs.append(t[i] - t0); ys.append(math.log(r))
    n = len(xs)
    if n > 5:
        mx, my = sum(xs) / n, sum(ys) / n
        sl = sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / sum((a - mx) ** 2 for a in xs)
        tau = -1e9 / sl
    else:
        tau = float('nan')
    P = ivdd * 3.3
    rows.append((iu, ivdd, P, t1, t01, tau))
    print("%-8s %10.4f %10.3f %10.1f %10.1f %10.1f %10.2f %10.2f" %
          (tag, ivdd * 1e6, P * 1e6, t1, t01, tau, P * t1 * 1e-9 * 1e12, P * t01 * 1e-9 * 1e12))

print("\n--- SCALING EXPONENTS (fit y = a * I^p over the %d bias points) ---" % len(rows))


def fitp(idx, lbl):
    xs = [math.log(r[0]) for r in rows]
    ys = [math.log(r[idx]) for r in rows]
    n = len(xs); mx = sum(xs) / n; my = sum(ys) / n
    p = sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / sum((a - mx) ** 2 for a in xs)
    print("  %-12s  p = %+.3f   (hypothesis: %s)" % (lbl, p, {"P": "+1", "t": "-1", "E": "0"}.get(lbl.split()[0], "?")))
    return p


pP = fitp(2, "P  power")
pt = fitp(3, "t  settle(1%)")
rows_E = [(r[0], r[2] * r[3]) for r in rows]
xs = [math.log(a) for a, b in rows_E]; ys = [math.log(b) for a, b in rows_E]
n = len(xs); mx = sum(xs) / n; my = sum(ys) / n
pE = sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / sum((a - mx) ** 2 for a in xs)
print("  %-12s  p = %+.3f   (hypothesis: 0 -- energy independent of bias)" % ("E  energy", pE))
print("\n  E spread over the 8:1 bias range: %.2f pJ -> %.2f pJ  = %.2fx" %
      (rows_E[0][1] * 1e12, rows_E[-1][1] * 1e12, rows_E[-1][1] / rows_E[0][1]))
