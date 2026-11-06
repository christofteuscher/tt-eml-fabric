#!/usr/bin/env python3
"""Fig. 2 (fig:grammar): what the eml grammar expresses.

Every number is read at run time; nothing is transcribed.

  (a) example trees, drawn from their expressions, including the two trees
      that compute ln x (a genuine identity found by the enumeration)
  (b) syntactic trees, defined trees and distinct functions by depth
  (c) distinct functions over total depth d and u-depth p, with the share
      that stays inside the device range and is not constant
  (d) the 100 AI Feynman equations by operator class

Sources
  corpus_stats_exact.json   written by corpus_enum.py exact (sim/corpus/)
  sim/bench/feynman_equations.json

Run:
  arch -arm64 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 \
      corpus_enum.py exact
  arch -arm64 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 \
      gen_fig_grammar.py
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm, LinearSegmentedColormap
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
import sys  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402
FEYNMAN = paths.repo("sim", "bench", "feynman_equations.json")

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
    "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8.5,
    "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "legend.fontsize": 7,
    "axes.linewidth": 0.7, "xtick.major.width": 0.7, "ytick.major.width": 0.7,
    "figure.facecolor": "white", "axes.facecolor": "white",
    "savefig.facecolor": "white", "pdf.fonttype": 42,
    "axes.spines.top": False, "axes.spines.right": False,
})
# Okabe-Ito, as in the v6 figures.  Blue = exponential port (u), orange =
# logarithm port (v), throughout the paper.
BLUE, ORANGE, SKY, VERM, GREY, BLACK = ("#0072B2", "#E69F00", "#56B4E9",
                                        "#D55E00", "#BFBFBF", "#000000")


def panel(ax, letter, x=-0.12, y=1.02):
    ax.text(x, y, letter, transform=ax.transAxes, fontsize=10,
            fontweight="bold", va="bottom", ha="left")


# ------------------------------------------------------------------ trees
def parse(s):
    """'eml(a,b)' -> ('eml', a, b); leaves '1', 'x'."""
    s = s.strip()
    if not s.startswith("eml("):
        return s
    body, depth, cut = s[4:-1], 0, None
    for i, ch in enumerate(body):
        depth += ch == "("
        depth -= ch == ")"
        if ch == "," and depth == 0:
            cut = i
            break
    return ("eml", parse(body[:cut]), parse(body[cut + 1:]))


def depth(t):
    return 0 if isinstance(t, str) else 1 + max(depth(t[1]), depth(t[2]))


def leaves(t):
    return 1 if isinstance(t, str) else leaves(t[1]) + leaves(t[2])


def draw_tree(ax, t, x0, y0, width, dy, r=0.13):
    """Draw tree t with its root at (x0 + width/2, y0); returns root xy."""
    def place(t, left, y):
        n = leaves(t)
        cx = left + n * width_per_leaf / 2
        if isinstance(t, str):
            ax.text(cx, y, "$%s$" % t, ha="center", va="center", fontsize=8)
            return cx, y
        lx, ly = place(t[1], left, y - dy)
        rx, ry = place(t[2], left + leaves(t[1]) * width_per_leaf, y - dy)
        for (ex, ey), col in (((lx, ly), BLUE), ((rx, ry), ORANGE)):
            ax.plot([cx, ex], [y, ey], color=col, lw=1.3, zorder=1,
                    solid_capstyle="round")
        ax.add_patch(plt.Circle((cx, y), r, facecolor="white",
                                edgecolor=BLACK, lw=0.8, zorder=2))
        ax.plot([cx], [y], marker="o", ms=2.2, color=BLACK, zorder=3)
        return cx, y
    width_per_leaf = width / leaves(t)
    return place(t, x0, y0)


def fig():
    st = json.load(open(paths.corpus_stats("exact")))
    assert st["mode"] == "exact"
    merges = st["merges"]
    ln_a = "eml(1,eml(eml(1,x),1))"
    ln_b = next(b for a, b in merges if a == ln_a)

    f = plt.figure(figsize=(7.1, 4.7))
    gs = f.add_gridspec(2, 2, width_ratios=[1.35, 1.0], height_ratios=[1.0, 0.82],
                        hspace=0.42, wspace=0.28)

    # (a) example trees ------------------------------------------------------
    a = f.add_subplot(gs[0, 0])
    a.set_xlim(0, 11.0)
    a.set_ylim(-0.75, 4.55)
    a.set_aspect("equal")
    a.axis("off")
    dy = 0.82
    top = 4.0
    examples = [("eml(1,1)", 0.0, 1.0, "$e$"),
                ("eml(x,1)", 1.25, 1.0, "$e^{x}$"),
                (ln_a, 3.0, 2.4, r"$\ln x$, depth 3"),
                (ln_b, 5.95, 4.9, r"$\ln x$, depth 4")]
    for expr, x0, w, lab in examples:
        t = parse(expr)
        draw_tree(a, t, x0, top, w, dy)
        a.text(x0 + w / 2, top - dy * depth(t) - 0.55, lab, ha="center",
               va="top", fontsize=7.5)
    a.text((3.0 + 5.95 + 4.9) / 2, top + 0.42,
           "one function, two trees", ha="center", fontsize=7, color="#444444")
    # legend: node and ports
    lx, ly = 0.05, 0.25
    a.add_patch(plt.Circle((lx + 0.15, ly), 0.13, facecolor="white",
                           edgecolor=BLACK, lw=0.8))
    a.plot([lx + 0.15], [ly], marker="o", ms=2.2, color=BLACK)
    a.text(lx + 0.4, ly, r"$\mathrm{eml}(u,v) = e^{u} - \ln v$", va="center",
           fontsize=7)
    a.plot([lx, lx + 0.32], [ly - 0.45] * 2, color=BLUE, lw=1.3)
    a.text(lx + 0.4, ly - 0.45, "$u$ port (exponential)", va="center", fontsize=7)
    a.plot([lx, lx + 0.32], [ly - 0.85] * 2, color=ORANGE, lw=1.3)
    a.text(lx + 0.4, ly - 0.85, "$v$ port (logarithm)", va="center", fontsize=7)
    panel(a, "a", x=-0.02, y=0.98)

    # (b) trees vs functions --------------------------------------------------
    b = f.add_subplot(gs[0, 1])
    D = np.arange(1, 5)
    T = np.array(st["syntactic_trees_cum"])[1:]
    Dt = np.array(st["defined_trees_cum"])[1:]
    F = np.array(st["distinct_cum"])[1:]
    w = 0.26
    series = [(T, GREY, "syntactic trees"), (Dt, SKY, "defined trees"),
              (F, BLUE, "distinct functions")]
    for i, (v, c, lab) in enumerate(series):
        b.bar(D + (i - 1) * w, v, w, color=c, label=lab, edgecolor="white", lw=0.4)
    b.set_yscale("log")
    b.set_ylim(1, 1e9)
    b.set_xticks(D)
    b.set_xlabel("depth $\\leq d$")
    b.set_ylabel("count")
    b.text(4 - w, T[-1] * 1.6, "{:,}".format(int(T[-1])), ha="center", fontsize=6.5)
    b.text(4 + w * 0.5, F[-1] * 1.9, "{:,}\n{:,}".format(int(Dt[-1]), int(F[-1])),
           ha="center", fontsize=6.5, linespacing=1.0)
    und = 1 - Dt[-1] / T[-1]
    b.annotate("%.1f %%\nundefined\nor overflow" % (100 * und),
               xy=(4 - 0.5 * w, 4e5), xytext=(2.75, 6e5), ha="center",
               va="center", fontsize=6.6,
               arrowprops=dict(arrowstyle="-", color="#666666", lw=0.6))
    b.legend(loc="upper left", frameon=False, handlelength=1.0)
    panel(b, "b", x=-0.24)

    # (c) heat map over (d, p) -------------------------------------------------
    c = f.add_subplot(gs[1, 0])
    grid = st["by_depth_udepth"]
    P = np.arange(1, 4)
    M = np.full((4, 3), np.nan)
    for d in D:
        for p in P:
            g = grid.get("%d,%d" % (d, p))
            if g:
                M[d - 1, p - 1] = g["n"]
    cmap = LinearSegmentedColormap.from_list("b", ["#EAF3FA", BLUE])
    c.imshow(M.T, origin="lower", cmap=cmap, norm=LogNorm(1, 1e5),
             extent=(0.5, 4.5, 0.5, 3.5), aspect="auto")
    for d in D:
        for p in P:
            g = grid.get("%d,%d" % (d, p))
            if not g:
                c.text(d, p, "--", ha="center", va="center", fontsize=7, color="#888888")
                continue
            share = g["in_span_nonconst"] / g["n"]
            col = "white" if g["n"] > 3000 else BLACK
            c.text(d, p + 0.13, "{:,}".format(g["n"]), ha="center", va="center",
                   fontsize=7.5, fontweight="bold", color=col)
            c.text(d, p - 0.2, "%d %% in range" % round(100 * share), ha="center",
                   va="center", fontsize=6.5, color=col)
    c.set_xticks(D)
    c.set_yticks(P)
    c.set_xlabel("depth $d$")
    c.set_ylabel("$u$-depth $p$ (stacked exponentials)")
    c.spines[["top", "right"]].set_visible(True)
    c.tick_params(length=0)
    panel(c, "c", x=-0.11)

    # (d) AI Feynman partition -------------------------------------------------
    dd = f.add_subplot(gs[1, 1])
    eqs = json.load(open(FEYNMAN))["equations"]
    assert len(eqs) == 100
    TRANS = {"exp", "log", "tanh"}
    blocked = [e for e in eqs if e["trig_blocked"]]
    rest = [e for e in eqs if not e["trig_blocked"]]
    trans = [e for e in rest if TRANS & set(e["ops"])]
    alg = [e for e in rest if not TRANS & set(e["ops"])]
    mono = [e for e in alg if not {"add", "sub"} & set(e["ops"])]
    segs = [(len(blocked), VERM, "trigonometric:\nnot representable"),
            (len(trans), BLUE, "contain\nexp, log or tanh"),
            (len(alg) - len(mono), SKY, "algebraic,\nwith sums"),
            (len(mono), GREY, "products of\npowers")]
    y = 0
    for n, col, lab in segs:
        dd.bar(0, n, 0.55, bottom=y, color=col, edgecolor="white", lw=0.8)
        dd.text(0, y + n / 2, "%d" % n, ha="center", va="center", fontsize=8,
                fontweight="bold", color="white" if col in (VERM, BLUE) else BLACK)
        dd.text(0.36, y + n / 2, lab, va="center", fontsize=6.8, linespacing=1.0)
        y += n
    dd.set_xlim(-0.4, 1.6)
    dd.set_ylim(0, 100)
    dd.set_xticks([])
    dd.set_ylabel("AI Feynman equations (of 100)")
    dd.spines["bottom"].set_visible(False)
    panel(dd, "d", x=-0.24)

    f.subplots_adjust(left=0.07, right=0.985, top=0.95, bottom=0.08)
    out = os.path.join(HERE, "fig_grammar.pdf")
    f.savefig(out)
    f.savefig(os.path.join(HERE, "fig_grammar_preview.png"), dpi=170)
    print("wrote", out, "| feynman blocked=%d trans=%d alg=%d mono=%d"
          % (len(blocked), len(trans), len(alg), len(mono)))


if __name__ == "__main__":
    fig()
