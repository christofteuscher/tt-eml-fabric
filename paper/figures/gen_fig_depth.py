#!/usr/bin/env python3
"""Fig. (fig:depth): precision and error against depth.

Every number is parsed from its record at run time; nothing is transcribed.

  (a) signal-to-sigma S/sigma of the v-port chain in circuit simulation, one to
      four cells; S = output swing over x = 0.35 .. 6.5 units (post-layout cell,
      sky130A tt, 27 C), sigma = 0.266 units, the single-cell level spread over
      440 Monte Carlo mismatch samples.  Bits = log2(S/sigma).
      Source: FAB_SPICE.md of the paper source (not public), sec. 4.1 (2-4 cell swings, SPICE column) and
      sec. 9 (1-cell value and sigma).
  (b) relative RMS divergence between an ideal and a mismatched fabric running
      identical frozen weights, full binary trees of depth 1-10, at 1, 3 and
      10 % gain mismatch, with the sqrt(N) growth expected of independent
      per-cell errors.  Source: sim/results/scaling_run_AB.log,
      section B.

Run:
  arch -arm64 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 \
      gen_fig_depth.py
"""
import math
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
import sys  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402
SPICE = paths.paper("FAB_SPICE.md")
LOG_B = paths.repo("sim", "results", "scaling_run_AB.log")

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
    "font.size": 8, "axes.labelsize": 8, "xtick.labelsize": 7.5,
    "ytick.labelsize": 7.5, "legend.fontsize": 7, "axes.linewidth": 0.7,
    "xtick.major.width": 0.7, "ytick.major.width": 0.7,
    "figure.facecolor": "white", "axes.facecolor": "white",
    "savefig.facecolor": "white", "pdf.fonttype": 42,
    "axes.spines.top": False, "axes.spines.right": False,
})
BLUE, ORANGE, SKY, VERM, GREY, BLACK = ("#0072B2", "#E69F00", "#56B4E9",
                                        "#D55E00", "#8C8C8C", "#000000")


def panel(ax, letter):
    ax.text(-0.2, 1.04, letter, transform=ax.transAxes, fontsize=10,
            fontweight="bold", va="bottom", ha="left")


def chain_snr():
    txt = open(SPICE).read()
    sec41 = txt.split("### 4.1 Swings")[1].split("### 4.2")[0]
    swing = {int(m.group(1)): float(m.group(2)) for m in re.finditer(
        r"\|\s*\**(\d) cells\**\s*\|\s*\**([0-9.]+) u", sec41)}
    m = re.search(r"MEASURED\s+([0-9.]+)-unit\s+per-cell\s+level\s+sigma:\s+([0-9.]+)\s+at\s+1\s+cell", txt)
    sigma, snr1 = float(m.group(1)), float(m.group(2))
    snr = {1: snr1}
    snr.update({n: s / sigma for n, s in swing.items()})
    # cross-check against the values quoted in sec. 9
    q = re.search(r"\*\*([0-9.]+) at 2, ([0-9.]+) at 3,\s*\n?\s*([0-9.]+) at 4\.\*\*", txt)
    for n, v in zip((2, 3, 4), q.groups()):
        assert abs(snr[n] - float(v)) / float(v) < 0.01, (n, snr[n], v)
    return sigma, dict(sorted(snr.items()))


def frozen_error():
    txt = open(LOG_B).read().split("=== B:")[1].split("=== A:")[0]
    rows = re.findall(r"^\s*([0-9.]+)\s+(\d+)\s+(\d+)\s+([0-9.e+-]+)\s", txt, re.M)
    out = {}
    for g, d, n, e in rows:
        out.setdefault(float(g), []).append((int(d), int(n), float(e)))
    return out


def fig():
    sigma, snr = chain_snr()
    err = frozen_error()
    f, (a, b) = plt.subplots(1, 2, figsize=(7.1, 2.7),
                             gridspec_kw=dict(width_ratios=[0.85, 1.15], wspace=0.42))

    # (a) ---------------------------------------------------------------------
    n = np.array(list(snr))
    s = np.array(list(snr.values()))
    a.axhline(1.0, color=GREY, lw=0.8, ls="--")
    a.text(4.5, 1.12, "signal = 1$\\sigma$ mismatch", ha="right", va="bottom",
           fontsize=6.6, color="#555555")
    a.plot(n, s, color=ORANGE, lw=1.2, marker="o", ms=4.5, mfc="white", mew=1.2)
    for ni, si in zip(n, s):
        bits = math.log2(si)
        lab = ("%.3g\n%.1f bits" % (si, bits)) if bits > 0 else ("%.3g" % si)
        right = ni < 4
        a.text(ni + (0.12 if right else -0.12), si * 1.15, lab, fontsize=6.6,
               va="bottom", ha="left" if right else "right", linespacing=1.0)
    a.set_yscale("log")
    a.set_ylim(0.02, 30)
    a.set_xlim(0.6, 4.6)
    a.set_xticks(n)
    a.set_xlabel("cells in the $v$-port chain")
    a.set_ylabel("signal / mismatch $\\sigma$")
    ax2 = a.twinx()
    ax2.set_yscale("log", base=2)
    ax2.set_ylim(a.get_ylim())
    from matplotlib.ticker import FixedLocator, FixedFormatter, NullLocator
    ks = [-4, -2, 0, 2, 4]
    ax2.yaxis.set_major_locator(FixedLocator([2.0 ** k for k in ks]))
    ax2.yaxis.set_major_formatter(FixedFormatter([str(k) for k in ks]))
    ax2.yaxis.set_minor_locator(NullLocator())
    ax2.spines["right"].set_visible(True)
    ax2.spines["top"].set_visible(False)
    ax2.set_ylabel("bits, $\\log_2(S/\\sigma)$")
    a.text(0.75, 0.2, "below the line:\nnot resolved", fontsize=6.8, color=VERM, ha="left")
    panel(a, "a")

    # (b) ---------------------------------------------------------------------
    style = {0.01: (SKY, "1 %"), 0.03: (BLUE, "3 %"), 0.10: (BLACK, "10 %")}
    ymax = 1.0
    for g, rows in sorted(err.items()):
        col, lab = style[g]
        d = np.array([r[0] for r in rows])
        e = np.array([r[2] for r in rows])
        ok = e < ymax
        a_d, a_e = d[ok], e[ok]
        b.plot(a_d, a_e, color=col, lw=1.2, marker="o", ms=3.5, label=lab)
        if not ok.all():
            b.annotate("diverges at $d = %d$" % d[~ok][0], xy=(9.7, 0.85),
                       xytext=(a_d[-1] - 0.3, 0.5), fontsize=6.6, ha="right",
                       va="center", arrowprops=dict(arrowstyle="->", lw=0.7,
                                                    shrinkA=1))
        # exponent p of err ~ d^p, from depth 2 to the last finite point (as in Results)
        i2, iL = list(d).index(2), len(a_d) - 1
        p = math.log(a_e[iL] / a_e[i2]) / math.log(a_d[iL] / a_d[i2])
        b.text(a_d[iL] + 0.25, a_e[iL], "$p = %.2f$" % p, fontsize=6.6,
               va="center", color=col)
    # sqrt(N) reference, anchored at depth 3 (7 cells) on the 3 % curve
    rows3 = err[0.03]
    d3 = np.array([r[0] for r in rows3])
    N3 = np.array([r[1] for r in rows3])
    e_anchor = [r[2] for r in rows3 if r[0] == 3][0]
    keep = d3 >= 3
    ref = e_anchor * np.sqrt(N3[keep] / 7)
    b.plot(d3[keep], ref, color=GREY, lw=0.9, ls="--",
           label="independent errors,\n$\\propto\\sqrt{N}$ from $d = 3$")
    b.set_yscale("log")
    b.set_ylim(1e-3, ymax)
    b.set_xlim(0.5, 11.9)
    b.set_xticks([1, 2, 3, 4, 6, 8, 10])
    b.set_xlabel("tree depth $d$ (cells $= 2^{d}-1$)")
    b.set_ylabel("relative output error")
    b.legend(title="gain mismatch", loc="lower right", frameon=False, ncol=2,
             title_fontsize=7, handlelength=1.4, columnspacing=1.0)
    panel(b, "b")

    f.subplots_adjust(left=0.085, right=0.985, top=0.92, bottom=0.17)
    f.savefig(os.path.join(HERE, "fig_depth.pdf"))
    f.savefig(os.path.join(HERE, "fig_depth_preview.png"), dpi=170)
    print("sigma", sigma, "snr", {k: round(v, 4) for k, v in snr.items()})
    print("err", {g: [(r[0], r[2]) for r in rows] for g, rows in err.items()})


if __name__ == "__main__":
    fig()
