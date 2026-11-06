#!/usr/bin/env python3
"""Fig. (fig:topologies): the three fabric topologies of the study.

Drawn from the simulator's own connection tables (FabricSpec.conn_index in
sim/eml_fabric_topo.py), and parameter counts are taken from the
instantiated model, so the drawing cannot drift from what was simulated.
Configurations: the depth-4 tree, and depth-4 DAG and mesh of width 8 (the
mesh is the best PDK-realistic fabric of Fig. 3).

Run:
  arch -arm64 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 \
      gen_fig_topologies.py
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402
sys.path.insert(0, paths.repo("sim"))
from eml_fabric_topo import AnalogConfig, AnalogEMLFabric, FabricSpec  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
    "font.size": 8, "figure.facecolor": "white", "savefig.facecolor": "white",
    "pdf.fonttype": 42,
})
BLUE, ORANGE, GREY, BLACK = "#0072B2", "#E69F00", "#9A9A9A", "#000000"
DEPTH, WIDTH = 4, 8


def panel(ax, letter):
    ax.text(0.0, 1.0, letter, transform=ax.transAxes, fontsize=10,
            fontweight="bold", va="top", ha="left")


def positions(spec, span=8.0):
    """(layer, j) -> (x, y); layer 0 (output) on top."""
    pos = {}
    for l, n in enumerate(spec.layer_sizes()):
        y = (DEPTH - 1 - l) * 1.0
        for j in range(n):
            x = (j + 0.5) * span / n
            pos[l, j] = (x, y)
    return pos


def draw(ax, topo, title):
    spec = FabricSpec(topology=topo, depth=DEPTH, width=WIDTH)
    model = AnalogEMLFabric(spec, AnalogConfig())
    pos = positions(spec)
    span = 8.0
    for l in range(DEPTH - 1):
        ci = spec.conn_index(l)                       # (n_l, 2, F)
        for j in range(ci.shape[0]):
            x0, y0 = pos[l, j]
            for path in (0, 1):
                for c in ci[j, path].tolist():
                    x1, y1 = pos[l + 1, c]
                    if topo == "tree":
                        col, lw, al = (BLUE, ORANGE)[path], 1.2, 1.0
                    else:
                        if path == 1:
                            continue                 # same child feeds both ports
                        col, lw, al = GREY, 0.6, 0.55 if topo == "dag" else 0.9
                    wrap = topo == "mesh" and abs(x1 - x0) > span / 2
                    if wrap:
                        # mesh window wraps around: draw as a stub leaving the edge
                        dx = -0.6 if x1 > x0 else 0.6
                        ax.annotate("", xy=(x0 + dx, y0 - 0.6), xytext=(x0, y0),
                                    arrowprops=dict(arrowstyle="-", color=col,
                                                    lw=lw, ls=(0, (2, 1.5))))
                        continue
                    ax.plot([x0, x1], [y0, y1], color=col, lw=lw, alpha=al,
                            zorder=1, solid_capstyle="round")
    for (l, j), (x, y) in pos.items():
        ax.add_patch(plt.Circle((x, y), 0.17, facecolor="white",
                                edgecolor=BLACK, lw=0.8, zorder=3))
    # readout
    top = [pos[0, j] for j in range(spec.layer_sizes()[0])]
    ytop = DEPTH - 1 + 0.75
    ax.add_patch(FancyBboxPatch((span / 2 - 1.5, ytop - 0.2), 3.0, 0.4,
                                boxstyle="round,pad=0.02", facecolor="#F2F2F2",
                                edgecolor=BLACK, lw=0.6, zorder=3))
    ax.text(span / 2, ytop, "digital readout", ha="center", va="center",
            fontsize=6.6, zorder=4)
    for x, y in top:
        ax.plot([x, span / 2], [y + 0.17, ytop - 0.2], color=BLACK, lw=0.5,
                alpha=0.7, zorder=2)
    n_cells, n_par = spec.n_cells(), model.n_params()
    ax.text(span / 2, -0.75, "%s\n%d cells, %d parameters" % (title, n_cells, n_par),
            ha="center", va="top", fontsize=7.3, linespacing=1.25)
    ax.set_xlim(-0.35, span + 0.35)
    ax.set_ylim(-2.15, DEPTH + 0.15)
    ax.set_aspect("equal")
    ax.axis("off")
    return n_cells, n_par


def fig():
    f, axs = plt.subplots(1, 3, figsize=(7.1, 2.45))
    out = []
    for ax, (topo, title), letter in zip(
            axs, [("tree", "tree: no shared subexpressions"),
                  ("dag", "DAG: every cell of the layer below"),
                  ("mesh", "mesh: self and two neighbors below")], "abc"):
        out.append((topo,) + draw(ax, topo, title))
        panel(ax, letter)
    # port legend (tree) and layer axis note
    axs[0].plot([0.0, 0.45], [-1.95] * 2, color=BLUE, lw=1.2)
    axs[0].text(0.55, -1.95, "$u$ (exp)", va="center", fontsize=6.6)
    axs[0].plot([2.6, 3.05], [-1.95] * 2, color=ORANGE, lw=1.2)
    axs[0].text(3.15, -1.95, "$v$ (log)", va="center", fontsize=6.6)
    axs[1].text(4.0, -1.95, "each link feeds both ports, separately weighted",
                ha="center", va="center", fontsize=6.4, color="#444444")
    axs[2].text(4.0, -1.95, "dashed: window wraps to the opposite edge",
                ha="center", va="center", fontsize=6.4, color="#444444")
    f.subplots_adjust(left=0.01, right=0.99, top=0.97, bottom=0.02, wspace=0.08)
    f.savefig(os.path.join(HERE, "fig_topologies.pdf"), bbox_inches="tight", pad_inches=0.03)
    f.savefig(os.path.join(HERE, "fig_topologies_preview.png"), dpi=170, bbox_inches="tight", pad_inches=0.03)
    print("wrote fig_topologies.pdf", out)


if __name__ == "__main__":
    fig()
