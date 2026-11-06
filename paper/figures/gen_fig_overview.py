#!/usr/bin/env python3
"""Fig. 1 (fig:overview): from primitive to fabric, and where the energy goes.

Every number is read at run time; nothing is transcribed.

  (a) the operator and three worked trees, each checked numerically
  (b) the cell as blocks, with each block's share of the supply current
  (c) a fabric of cells with weighted interconnect (mesh wiring of Fig. 3)
  (d) energy of one evaluation, core against cell, by block

Sources
  v7_results_clean.tex, Table tab:blockbudget (block currents, energies)
  v7_methods_clean.tex, core energy (\\SI{13.0}{\\femto\\joule})
  v7_results_clean.tex, composability overhead (\\num{3046})
Run revision/build.sh first so the clean files are current.

Run:
  arch -arm64 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 \
      gen_fig_overview.py
"""
import math
import os
import re
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sys  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402
from gen_fig_grammar import parse, depth, draw_tree  # noqa: E402

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
    "font.size": 8, "axes.labelsize": 8, "xtick.labelsize": 7.5,
    "ytick.labelsize": 7.5, "axes.linewidth": 0.7,
    "xtick.major.width": 0.7, "ytick.major.width": 0.7,
    "figure.facecolor": "white", "axes.facecolor": "white",
    "savefig.facecolor": "white", "pdf.fonttype": 42,
    "axes.spines.top": False, "axes.spines.right": False,
})
BLUE, ORANGE, VERM, GREEN, GREY, BLACK = ("#0072B2", "#E69F00", "#D55E00",
                                          "#009E73", "#6F6F6F", "#000000")
# block colors as in Fig. (fig:cell)
COL = {"core": GREEN, "servo": VERM, "bias": BLUE, "mirr": GREY}


def panel(ax, letter, x=0.0, y=1.0):
    ax.text(x, y, letter, transform=ax.transAxes, fontsize=10,
            fontweight="bold", va="top", ha="left")


# ------------------------------------------------------------------ records
def records():
    res = open(paths.paper("v7_results_clean.tex")).read()
    met = open(paths.paper("v7_methods_clean.tex")).read()
    tab = res.split(r"\label{tab:blockbudget}")[1].split(r"\end{tabular}")[0]

    def row(name):
        i = tab.index(name)
        return [c.strip() for c in tab[i:tab.index("\\\\", i)].split("&")]
    out = {}
    for key, name in (("core", "Translinear core"), ("servo", "Servo amplifiers"),
                      ("bias", "Bias network"), ("mirr", "Output mirrors"),
                      ("total", "Total, one cell")):
        c = row(name)
        out[key] = dict(i=float(c[3].split("\\")[0]), ipct=float(c[4]),
                        e=float(c[5].split("\\")[0]))
    core_fj = float(re.search(r"core energy,\s*\n?\\SI\{([0-9.]+)\}\{\\femto\\joule\}",
                              met).group(1))
    ratio = int(re.search(r"composability overhead, is \\num\{(\d+)\}", res).group(1))
    parts = sum(out[k]["e"] for k in ("servo", "bias", "mirr"))
    assert abs(parts - out["total"]["e"]) < 0.02, (parts, out["total"])
    assert abs(out["total"]["e"] * 1e3 / core_fj - ratio) / ratio < 1e-3
    return out, core_fj, ratio


# ------------------------------------------------------------------ (a)
def eml(u, v):
    return math.exp(u) - math.log(v)


def evaluate(t, x):
    if t == "1":
        return 1.0
    if t == "x":
        return x
    return eml(evaluate(t[1], x), evaluate(t[2], x))


TREES = [("eml(x,x)", r"$e^{x} - \ln x$", lambda x: math.exp(x) - math.log(x)),
         ("eml(eml(x,1),1)", r"$e^{e^{x}}$", lambda x: math.exp(math.exp(x))),
         ("eml(1,eml(x,1))", r"$e - x$", lambda x: math.e - x)]


def draw_operator(a):
    a.set_xlim(-0.45, 9.55)
    a.set_ylim(-0.3, 5.0)
    a.set_aspect("equal")
    a.axis("off")
    # operator as a dataflow: u -> exp, v -> ln, subtract
    y0 = 4.15
    for x, lab, col, port in ((0.9, "exp", BLUE, "u"), (0.9, "ln", ORANGE, "v")):
        yy = y0 + (0.38 if lab == "exp" else -0.38)
        a.add_patch(FancyBboxPatch((x, yy - 0.2), 0.75, 0.4, boxstyle="round,pad=0.02",
                                   facecolor="white", edgecolor=col, lw=1.1))
        a.text(x + 0.375, yy, lab, ha="center", va="center", fontsize=7)
        a.annotate("", xy=(x, yy), xytext=(x - 0.55, yy),
                   arrowprops=dict(arrowstyle="-|>", color=col, lw=1.1, mutation_scale=7))
        a.text(x - 0.65, yy, "$%s$" % port, ha="right", va="center", fontsize=8)
        a.annotate("", xy=(2.3, y0 + (0.06 if lab == "exp" else -0.06)),
                   xytext=(x + 0.75, yy),
                   arrowprops=dict(arrowstyle="-|>", color=col, lw=1.1, mutation_scale=7))
    a.add_patch(plt.Circle((2.48, y0), 0.18, facecolor="white", edgecolor=BLACK, lw=0.8))
    a.text(2.48, y0, "$-$", ha="center", va="center", fontsize=8)
    a.annotate("", xy=(3.15, y0), xytext=(2.66, y0),
               arrowprops=dict(arrowstyle="-|>", color=BLACK, lw=1.0, mutation_scale=7))
    a.text(3.25, y0, r"$\mathrm{eml}(u,v) = e^{u} - \ln v$", va="center", fontsize=8)
    a.text(3.25, y0 - 0.55, r"$S \rightarrow 1 \mid x \mid \mathrm{eml}(S,S)$",
           va="center", fontsize=7.5, color="#444444")
    # three worked trees
    top, dy = 2.55, 0.72
    slots = [(0.2, 1.5), (2.2, 2.0), (4.75, 2.2)]
    for (expr, lab, ref), (x0, w) in zip(TREES, slots):
        t = parse(expr)
        for x in (0.3, 0.9, 2.0):
            assert abs(evaluate(t, x) - ref(x)) < 1e-9 * max(1, abs(ref(x))), expr
        draw_tree(a, t, x0, top, w, dy, r=0.12)
        a.text(x0 + w / 2, top - dy * depth(t) - 0.42, lab, ha="center", va="top",
               fontsize=7.5)
    # port legend
    a.plot([7.85, 8.2], [2.3] * 2, color=BLUE, lw=1.3)
    a.text(8.3, 2.3, "$u$ port", va="center", fontsize=6.8)
    a.plot([7.85, 8.2], [1.9] * 2, color=ORANGE, lw=1.3)
    a.text(8.3, 1.9, "$v$ port", va="center", fontsize=6.8)


# ------------------------------------------------------------------ (b)
def box(ax, x, y, w, h, col, text, fs=6.8, fill=0.16, lw=1.0, tc=BLACK):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.03",
                                facecolor=matplotlib.colors.to_rgba(col, fill),
                                edgecolor=col, lw=lw, zorder=2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            zorder=3, color=tc, linespacing=1.1)


def arrow(ax, p, q, col=BLACK, lw=0.9, style="-|>"):
    ax.annotate("", xy=q, xytext=p, arrowprops=dict(arrowstyle=style, color=col, lw=lw,
                                                    mutation_scale=7, shrinkA=0, shrinkB=0))


def draw_cell(b, rec):
    b.set_xlim(-0.3, 10.6)
    b.set_ylim(0.3, 6.2)
    b.set_aspect("equal")
    b.axis("off")
    pct = {k: rec[k]["ipct"] for k in COL}
    # supply rail
    b.plot([1.2, 9.6], [5.75, 5.75], color=BLACK, lw=1.2)
    b.text(9.7, 5.75, "3.3 V", ha="left", va="center", fontsize=6.8)
    # bias network
    box(b, 1.5, 4.55, 7.2, 0.7, COL["bias"],
        "bias network: %.1f %% of supply" % pct["bias"])
    # core
    box(b, 3.3, 1.75, 3.6, 1.75, COL["core"],
        "translinear core\n4 NPN junctions\n%d %% of supply" % pct["core"])
    # servo amplifiers
    sv = [(1.2, 2.95, "A$_1$"), (1.2, 1.55, "A$_2$"), (7.45, 2.95, "A$_3$"),
          (7.45, 1.55, "A$_4$")]
    for x, y, lab in sv:
        tri_x = [x, x, x + 0.95]
        tri_y = [y - 0.4, y + 0.4, y]
        if x > 5:
            tri_x = [x + 0.95, x + 0.95, x]
        b.fill(tri_x, tri_y, facecolor=matplotlib.colors.to_rgba(COL["servo"], 0.16),
               edgecolor=COL["servo"], lw=1.0, zorder=2)
        b.text(x + 0.42 if x < 5 else x + 0.53, y, lab, ha="center", va="center",
               fontsize=6.5, zorder=3)
        if x < 5:
            b.plot([x + 0.95, 3.3], [y, y], color=COL["servo"], lw=0.9)
        else:
            b.plot([x, 6.9], [y, y], color=COL["servo"], lw=0.9)
        b.plot([x + 0.47] * 2, [y + 0.25, 5.75], color=BLACK, lw=0.5, alpha=0.6, zorder=1)
    b.text(5.1, 1.12, "four servo amplifiers hold the junction nodes:\n"
           "%.1f %% of supply" % pct["servo"], ha="center", va="top",
           fontsize=6.8, color=COL["servo"])
    # bias into core (from 1.2 V reference, not the 3.3 V rail)
    for xx in (4.2, 6.0):
        arrow(b, (xx, 4.55), (xx, 3.55), col=COL["bias"])
    # inputs and output mirror
    arrow(b, (0.35, 2.95), (1.2, 2.95), col=BLUE, lw=1.1)
    b.text(0.25, 2.95, "$u$", fontsize=8, va="center", ha="right")
    arrow(b, (0.35, 1.55), (1.2, 1.55), col=ORANGE, lw=1.1)
    b.text(0.25, 1.55, "$v$", fontsize=8, va="center", ha="right")
    box(b, 8.75, 3.95, 1.15, 0.45, COL["mirr"], "mirror", fs=6.3)
    b.plot([9.32, 9.32], [4.42, 5.75], color=BLACK, lw=0.5, alpha=0.6)
    b.plot([6.9, 8.1], [3.3, 3.3], color=COL["core"], lw=0.9)
    b.plot([8.1, 8.1, 8.75], [3.3, 4.17, 4.17], color=COL["core"], lw=0.9)
    arrow(b, (9.32, 3.92), (9.32, 3.2), col=COL["mirr"])
    b.text(9.32, 3.1, "out\n%.1f %%" % pct["mirr"], ha="center", va="top", fontsize=6.5)


# ------------------------------------------------------------------ (c)
def draw_fabric(c):
    c.set_xlim(0, 10)
    c.set_ylim(-0.4, 5.6)
    c.set_aspect("equal")
    c.axis("off")
    L, W = 3, 5
    xs = [1.4 + 1.8 * j for j in range(W)]
    ys = [1.2 + 1.35 * l for l in range(L)]
    # inputs
    for j, x in enumerate(xs):
        c.text(x, 0.05, "$x$" if j % 2 == 0 else "$1$", ha="center", va="center",
               fontsize=7.5)
    for l, y in enumerate(ys):
        ysrc = 0.3 if l == 0 else ys[l - 1] + 0.27
        for j, x in enumerate(xs):
            for dj in (-1, 0, 1):
                k = j + dj
                if not 0 <= k < W:
                    continue
                xa = xs[k]
                for port, off, col in (("u", -0.13, BLUE), ("v", 0.13, ORANGE)):
                    c.plot([xa, x + off], [ysrc, y - 0.27], color=col, lw=0.55,
                           alpha=0.65, zorder=1)
            # weights: one small square per port
            for off, col in ((-0.13, BLUE), (0.13, ORANGE)):
                c.add_patch(plt.Rectangle((x + off - 0.07, y - 0.42), 0.14, 0.14,
                                          facecolor=col, edgecolor="none", zorder=3))
            c.add_patch(FancyBboxPatch((x - 0.38, y - 0.27), 0.76, 0.54,
                                       boxstyle="round,pad=0.02", facecolor="white",
                                       edgecolor=BLACK, lw=0.8, zorder=2))
            c.text(x, y, "eml", ha="center", va="center", fontsize=6, zorder=3)
    # readout
    yr = ys[-1] + 1.15
    c.add_patch(FancyBboxPatch((2.6, yr - 0.22), 4.0, 0.44, boxstyle="round,pad=0.02",
                               facecolor="#F2F2F2", edgecolor=BLACK, lw=0.6, zorder=2))
    c.text(4.6, yr, "readout: weighted sum", ha="center", va="center", fontsize=6.6,
           zorder=3)
    for x in xs:
        c.plot([x, 4.6], [ys[-1] + 0.27, yr - 0.22], color=BLACK, lw=0.5, alpha=0.6)
    # legend
    c.add_patch(plt.Rectangle((7.4, 5.02), 0.14, 0.14, facecolor=BLUE))
    c.add_patch(plt.Rectangle((7.58, 5.02), 0.14, 0.14, facecolor=ORANGE))
    c.text(7.85, 5.09, "weight per port,\n4-bit + sign DAC", va="center",
           fontsize=6.3, linespacing=1.0)


# ------------------------------------------------------------------ (d)
def draw_energy(d, rec, core_fj, ratio):
    rows = [("translinear core", core_fj * 1e-3, COL["core"]),
            ("output mirrors", rec["mirr"]["e"], COL["mirr"]),
            ("bias network", rec["bias"]["e"], COL["bias"]),
            ("servo amplifiers", rec["servo"]["e"], COL["servo"]),
            ("whole cell", rec["total"]["e"], BLACK)]
    for i, (lab, e, col) in enumerate(rows):
        y = len(rows) - 1 - i
        d.barh(y, e, height=0.62, color=col, left=1e-3,
               alpha=1.0 if lab == "whole cell" else 0.85)
        txt = ("%.0f fJ" % (e * 1e3)) if e < 0.1 else ("%.2f pJ" % e)
        d.text(e * 1.25, y, txt, va="center", fontsize=6.8)
    d.set_yticks(range(len(rows)))
    d.set_yticklabels([r[0] for r in rows][::-1])
    d.set_xscale("log")
    d.set_xlim(1e-3, 400)
    d.set_xlabel("energy per evaluation (pJ)")
    d.set_xticks([1e-3, 1e-2, 1e-1, 1, 10, 100])
    d.set_xticklabels(["0.001", "0.01", "0.1", "1", "10", "100"])
    d.tick_params(axis="y", length=0)
    # overhead bracket
    d.text(0.12, 4.0, "cell / core: composability\noverhead $\\times$%s" % "{:,}".format(ratio),
           ha="left", va="center", fontsize=7, linespacing=1.1)
    d.set_ylim(-0.6, 4.6)


def fig():
    rec, core_fj, ratio = records()
    f = plt.figure(figsize=(7.1, 4.75))
    gs = f.add_gridspec(2, 2, width_ratios=[1.0, 1.0], height_ratios=[1.0, 1.0],
                        hspace=0.12, wspace=0.12)
    a = f.add_subplot(gs[0, 0])
    draw_operator(a)
    panel(a, "a")
    b = f.add_subplot(gs[0, 1])
    draw_cell(b, rec)
    panel(b, "b")
    c = f.add_subplot(gs[1, 0])
    draw_fabric(c)
    panel(c, "c")
    d = f.add_subplot(gs[1, 1])
    draw_energy(d, rec, core_fj, ratio)
    d.text(-0.36, 1.0, "d", transform=d.transAxes, fontsize=10, fontweight="bold",
           va="top", ha="left")
    f.subplots_adjust(left=0.01, right=0.985, top=0.99, bottom=0.09)
    d.set_position([0.66, 0.11, 0.32, 0.36])
    f.savefig(os.path.join(HERE, "fig_overview.pdf"))
    f.savefig(os.path.join(HERE, "fig_overview_preview.png"), dpi=170)
    print("core %.1f fJ, cell %.2f pJ, ratio %d" % (core_fj, rec["total"]["e"], ratio),
          {k: rec[k] for k in ("servo", "bias", "mirr")})


if __name__ == "__main__":
    fig()
