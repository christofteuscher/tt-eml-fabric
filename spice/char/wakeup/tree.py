#!/usr/bin/env python3
"""Task 3/4 arithmetic.  All inputs are numbers printed by analyze.py (post-layout,
pex_ship.inc, tt/27C) or the paper's own P(N) law / chain latency (Methods, fabric power and latency)."""
kT = 1.380649e-23 * 300.15
P_CELL, P_LINK, P_DIV = 96.95, 85.64, 2.09        # uW, schematic two-cell chain
N, L = 7, 6                                         # depth-3 binary tree: 4+2+1 cells, 6 links
T7 = 1.19 * (166 + 65 * 2)                          # ns, paper, Methods
P7 = P_CELL * N + P_LINK * L + P_DIV
print(f"(i) spatial, all on for chain latency: P7={P7:.2f} uW x T7={T7:.2f} ns = {P7*T7*1e-3:.1f} pJ"
      f"  [cells {P_CELL*N*T7*1e-3:.1f}, links {P_LINK*L*T7*1e-3:.1f}, div {P_DIV*T7*1e-3:.2f}]")
r = P_LINK / P_CELL
def tree(Ecell, t, lab):
    cells = N * Ecell; links = L * r * Ecell
    print(f"  {lab:46s} E_cell={Ecell:7.1f} pJ t={t:7.0f} ns | tree cells={cells:7.1f} +links={cells+links:7.1f} pJ  latency={3*t:6.0f} ns")
print("(ii) ideal level-gated (each level on for one window, no wake cost):")
tree(39.62, 402, "A: paper per-cell 98.566uW x 402 ns")
tree(P_CELL * 1.19 * 166 * 1e-3, 1.19 * 166, "B: chain-consistent 96.95uW x 1.19x166 ns")
print("    reuse ONE physical level of 4 cells for 3 logical levels, all 4 kept on:"
      f" 4x3x39.62 = {4*3*39.62:.1f} pJ cells, latency {3*402} ns")
print("(iii) realistic level-gated, post-layout wake-up (1 % F), links assumed to wake like cells (x0.883):")
for lab, E, t in [("bias gating, u=+1 (10 ns edge)", 141.12, 3873),
                  ("bias gating, worst u (u=0)", 443.83, 3840),
                  ("bias gating, best u (u=-1.5)", 100.35, 3577),
                  ("pfet-header supply gating, u=+1", 156.96, 3459),
                  ("pfet-header supply gating, worst u (-1.5)", 967.59, 3145),
                  ("IDEAL fast-start (pbias forced), u=+1", 67.01, 657),
                  ("IDEAL fast-start, worst u (u=0)", 315.55, 723)]:
    tree(E, t, lab)
print("\n(4) S/H, kT/C at 300 K, sigma <= LSB/2:")
for b in (2, 3, 4, 6):
    # voltage-mode hold, 1 V full scale
    C_v = kT / (1.0 / 2**b / 2) ** 2
    # current held as a subthreshold mirror gate voltage: dI/I = dV/(n VT), n VT = 33.6 mV,
    # LSB relative to full-scale current, evaluated at full scale and at 1/10 full scale
    dV_fs = 33.6e-3 * 2**-b / 2; dV_10 = dV_fs / 10
    print(f"  {b} bits: V-mode 1 V FS C>={C_v*1e15:8.3f} fF | I-mode (subthreshold gate): "
          f"C>={kT/dV_fs**2*1e15:8.2f} fF at FS, {kT/dV_10**2*1e12:7.2f} pF at FS/10;"
          f" allowed droop {dV_fs*1e3:.3f} mV (FS)")
for C in (60e-15, 1e-12):
    for Il in (1e-12, 2.5e-12):
        for th, lab in ((3 * 402e-9, "3 x 402 ns"), (3 * 3.9e-6, "3 x 3.9 us wake")):
            print(f"  droop C={C*1e15:6.0f} fF Ileak={Il*1e12:.1f} pA over {lab}: {Il*th/C*1e3:.4f} mV")
