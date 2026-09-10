"""
Headline figure for the scaling study. Three panels:

  (a) trainability gate  -- RMSE vs depth, legacy vs unity-gain init
  (b) error accumulation -- relative forward error vs depth, no training
  (c) topology           -- RMSE vs cell count at equal hardware config

Palette #2f6fb2 / #d94f3d / #2e9e8f / #a05ab5 passes all six checks of the
dataviz validator in light mode (lightness band, chroma floor, CVD
separation worst-adjacent dE 9.9 deutan, normal-vision floor 24.0,
contrast >= 3:1). Line style and marker shape carry the same distinctions
redundantly, so nothing is encoded by colour alone.
"""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BLUE, RED, TEAL, PURPLE = "#2f6fb2", "#d94f3d", "#2e9e8f", "#a05ab5"
INK, MUTED, GRID = "#1a1a1a", "#5c5c5c", "#d8d8d4"

plt.rcParams.update({
    "font.family": "serif", "font.size": 8,
    "axes.labelsize": 8, "axes.titlesize": 8.5,
    "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "legend.fontsize": 6.8,
    "axes.edgecolor": MUTED, "axes.linewidth": 0.6,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.labelcolor": INK, "text.color": INK,
    "legend.frameon": False, "figure.dpi": 200,
})

D = [1, 2, 3, 4, 6, 8, 10]

# (a) thermistor_sh, median over 3 seeds, 4000 Adam iters
A = {
    "legacy init, ideal":   (D, [2.189, .7262, .5347, .6020, .7409, 2.1928, 19.127]),
    "unity-gain, ideal":    (D, [.0982, .0761, .0136, .0101, .0144, .0093, .5113]),
    "legacy init, PDK":     ([3, 4, 6, 8], [5.3373, 5.4525, 2.7779, 6.2367]),
    "unity-gain, PDK":      (D, [.1566, .1709, .1623, .1337, .1379, .2250, .3137]),
}
A_STYLE = {
    "legacy init, ideal":  (RED,    "o", "-",  1.7),
    "unity-gain, ideal":   (BLUE,   "s", "-",  1.7),
    "legacy init, PDK":    (PURPLE, "^", "--", 1.5),
    "unity-gain, PDK":     (TEAL,   "D", "--", 1.5),
}

# (b) relative forward divergence, frozen weights (depth 10 at 10 % diverges
#     to 4.6e11 and is drawn as an off-scale arrow rather than plotted)
B = {
    r"$\sigma_g$ = 1 %":  (D, [1.088e-2, 6.181e-3, 7.206e-3, 7.567e-3,
                               8.745e-3, 9.866e-3, 1.080e-2]),
    r"$\sigma_g$ = 3 %":  (D, [3.230e-2, 1.793e-2, 2.085e-2, 2.177e-2,
                               2.553e-2, 2.951e-2, 3.288e-2]),
    r"$\sigma_g$ = 10 %": (D[:-1], [1.040e-1, 5.306e-2, 6.123e-2, 6.572e-2,
                                    1.182e-1, 2.138e-1]),
}
B_STYLE = {r"$\sigma_g$ = 1 %": (BLUE, "o"), r"$\sigma_g$ = 3 %": (TEAL, "s"),
           r"$\sigma_g$ = 10 %": (RED, "^")}

# (c) topology, thermistor_sh on the corrected-PDK chip, median of 3 seeds
C = {
    "tree": ([15, 63, 255], [.1294, .2776, .2125]),
    "DAG (full fan-in)": ([16, 32, 48, 60, 64, 256],
                          [.3689, 1.6348, .6631, .4892, 5.1908, 10.5025]),
    "mesh (local fan-in)": ([16, 32, 48, 60, 64, 256],
                            [.0885, .0438, .1699, .0871, .3487, 4.4896]),
}
C_STYLE = {"tree": (BLUE, "o"), "DAG (full fan-in)": (RED, "s"),
           "mesh (local fan-in)": (TEAL, "^")}


def tidy(ax):
    ax.grid(True, which="major", color=GRID, linewidth=0.5, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


fig, axes = plt.subplots(1, 3, figsize=(7.4, 2.55))

ax = axes[0]
for k, (xs, ys) in A.items():
    c, m, ls, lw = A_STYLE[k]
    ax.plot(xs, ys, ls, color=c, marker=m, markersize=3.6, linewidth=lw,
            label=k, markeredgecolor="white", markeredgewidth=0.5, zorder=3)
ax.set_yscale("log")
ax.set_xlabel("tree depth")
ax.set_ylabel("calibration RMSE (K)")
ax.set_title("(a) trainability", loc="left", color=INK)
ax.set_ylim(4e-3, 4e3)
ax.set_xticks(D)
ax.legend(loc="upper left", handlelength=2.0, ncol=2, columnspacing=1.0,
          borderaxespad=0.2)
tidy(ax)

ax = axes[1]
for k, (xs, ys) in B.items():
    c, m = B_STYLE[k]
    ax.plot(xs, ys, "-", color=c, marker=m, markersize=3.6, linewidth=1.7,
            label=k, markeredgecolor="white", markeredgewidth=0.5, zorder=3)
ax.plot([2, 10], [1.793e-2, 1.793e-2 * (5 ** 0.38)], ":", color=MUTED,
        linewidth=1.0, zorder=2)
ax.annotate(r"$d^{0.38}$", xy=(6.5, 2.9e-2), color=MUTED, fontsize=6.5)
ax.set_yscale("log")
ax.set_ylim(4e-3, 3.0)
ax.annotate("", xy=(10, 1.35), xytext=(8, 2.14e-1),
            arrowprops=dict(arrowstyle="->", color=RED, linewidth=0.9,
                            linestyle=(0, (2, 1.5))))
ax.annotate("diverges\n(4.6e11)", xy=(9.1, 1.5), color=RED, fontsize=6.2,
            ha="center", va="bottom", linespacing=1.1)
ax.set_xlabel("tree depth")
ax.set_ylabel("relative forward error")
ax.set_xticks(D)
ax.set_title("(b) error accumulation", loc="left", color=INK)
ax.legend(loc="lower right", handlelength=2.0, borderaxespad=0.3)
tidy(ax)

ax = axes[2]
# scatter, not lines: successive points are different (depth, width) builds,
# not a trajectory, so joining them would imply a progression that is not
# there. Depth is direct-labelled instead.
C_DEPTH = {"tree": [4, 6, 8],
           "DAG (full fan-in)": [4, 4, 6, 6, 8, 8],
           "mesh (local fan-in)": [4, 4, 6, 6, 8, 8]}
for k, (xs, ys) in C.items():
    c, m = C_STYLE[k]
    ax.scatter(xs, ys, color=c, marker=m, s=26, label=k,
               edgecolors="white", linewidths=0.5, zorder=3)
    for xx, yy, dd in zip(xs, ys, C_DEPTH[k]):
        ax.annotate(f"{dd}", xy=(xx, yy), xytext=(0, -7.5),
                    textcoords="offset points", fontsize=5.4, color=MUTED,
                    ha="center")
ax.set_xscale("log")
ax.set_yscale("log")
ax.set_ylim(2e-2, 8e2)
ax.set_xlim(11, 420)
ax.set_xlabel("cells  (point labels = depth)")
ax.set_ylabel("calibration RMSE (K)")
ax.set_title("(c) topology", loc="left", color=INK)
ax.legend(loc="upper left", handlelength=1.4, borderaxespad=0.2)
tidy(ax)

fig.tight_layout(pad=0.4, w_pad=1.4)
fig.savefig("results/fig_scaling.pdf", bbox_inches="tight")
fig.savefig("results/fig_scaling.png", bbox_inches="tight", dpi=220)
print("wrote results/fig_scaling.pdf and .png")
