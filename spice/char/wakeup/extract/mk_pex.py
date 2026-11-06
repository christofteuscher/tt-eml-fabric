#!/usr/bin/env python3
"""Rebuild pex_ship.inc from magic's raw extraction, following the repair recipe
used for the paper's post-layout netlists:
  1. names: '.' -> '_', '#' -> '_h'
  2. merge every R card < 1 ohm (union of its two nodes)
  3. drop non-positive C cards
  4. attach the 12-port list  nu nv out vdd vrefb ve pbias VSUB nb0 nc2 ndl nsv
Also writes pex_ctrl.inc (all R shorted, all C removed)."""
import re, sys
PORTS = "nu nv out vdd vrefb ve pbias VSUB nb0 nc2 ndl nsv".split()
raw = open(sys.argv[1]).read().splitlines()
def san(n): return n.replace('.', '_').replace('#', '_h')
def val(s):
    m = re.match(r'^([-+0-9.eE]+)([a-zA-Z]*)$', s)
    x = float(m.group(1)); suf = m.group(2).lower()
    mult = {'': 1, 'f': 1e-15, 'p': 1e-12, 'n': 1e-9, 'u': 1e-6, 'm': 1e-3, 'k': 1e3, 'meg': 1e6}
    return x * mult[suf]
body = [l for l in raw if l and not l.startswith('*') and not l.startswith('.subckt') and not l.startswith('.ends')]
devs, Rs, Cs = [], [], []
for l in body:
    t = l.split()
    if l[0] == 'X': devs.append(t)
    elif l[0] == 'R': Rs.append((t[0], san(t[1]), san(t[2]), val(t[3])))
    elif l[0] == 'C': Cs.append((t[0], san(t[1]), san(t[2]), val(t[3])))
    else: raise SystemExit('unknown card ' + l)
def build(rlim, keepC):
    par = {}
    def f(a):
        par.setdefault(a, a)
        while par[a] != a:
            par[a] = par[par[a]]; a = par[a]
        return a
    def u(a, b):
        ra, rb = f(a), f(b)
        if ra == rb: return
        # prefer bare port names as representative
        if rb in PORTS and ra not in PORTS: ra, rb = rb, ra
        par[rb] = ra
    removed = 0.0
    for n, a, b, v in Rs:
        if v < rlim: u(a, b); removed += v
    # magic splits ports into port.tN pieces; the bare port name must exist
    nodes = set()
    for d in devs: nodes.update(san(x) for x in d[1:] if '=' not in x and not x.startswith('sky130'))
    for _, a, b, _v in Rs + Cs: nodes.update((a, b))
    for p in PORTS: assert p in nodes, p
    out = ['.subckt emlcell_b ' + ' '.join(PORTS)]
    for d in devs:
        o = [d[0]]
        for x in d[1:]:
            o.append(x if ('=' in x or x.startswith('sky130')) else f(san(x)))
        out.append(' '.join(o))
    nr = nc = 0; dropped = []
    for n, a, b, v in Rs:
        if v >= rlim and f(a) != f(b):
            out.append(f'{n} {f(a)} {f(b)} {v:.6g}'); nr += 1
    if keepC:
        for n, a, b, v in Cs:
            if v <= 0: dropped.append((n, a, b, v)); continue
            if f(a) == f(b): continue
            out.append(f'{n} {f(a)} {f(b)} {v:.6g}'); nc += 1
    out.append('.ends')
    return out, nr, nc, removed, dropped
ship, nr, nc, rem, drop = build(1.0, True)
open('pex_ship.inc', 'w').write('* rebuilt by mk_pex.py from magic raw emlcell_b.spice\n' + '\n'.join(ship) + '\n')
print(f'pex_ship: dev={len(devs)} R={nr} C={nc} sub-ohm removed={rem:.1f} ohm of {sum(r[3] for r in Rs):.4g} dropped={drop}')
ctrl, nr2, nc2, _, _ = build(float('inf'), False)
open('pex_ctrl.inc', 'w').write('* parasitic-free control\n' + '\n'.join(ctrl) + '\n')
print(f'pex_ctrl: dev={len(devs)} R={nr2} C={nc2}')
