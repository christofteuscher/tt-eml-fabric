#!/usr/bin/env python3
"""
CRITERION (d): does the host material's NATIVE dynamics hold the computational
variable, and is the attractor CONTINUOUS or DISCRETE?

Three parts.

  A. PROPOSITION (stated here, checked numerically in B).
     For autonomous dynamics xdot = F(x) on R^n, let S be the set of states the
     system holds indefinitely against noise, i.e. asymptotically stable fixed
     points with a nonzero linear restoring rate.  Every such point is isolated:
     if F(x)=0 on a connected set C of positive dimension then DF is singular
     along C, so the restoring rate vanishes in the direction tangent to C.
     Hence: a readout that is surjective onto an interval requires S to contain
     a continuum, and along that continuum the restoring rate is exactly 0.
     => RESTORATION AND CONTINUOUS-VALUEDNESS ARE MUTUALLY EXCLUSIVE for any
        autonomous substrate.  Continuous attractors are marginal, not
        restoring: noise along them performs a random walk, Var ~ 2Dt.
     The 3046x overhead is the price of the external, non-autonomous machinery
     that supplies the missing restoring rate.  It is NOT a property of eml.

  B. Langevin test of the five canonical host landscapes.
  C. Attractor census of each physics-native operator used as a relaxing node:
     tau xdot = f(x,c) - x.  Counts the stable fixed points -- i.e. how many
     values the substrate can hold -- and whether they form a continuum.
"""
import json, os, sys
import numpy as np
import phys_ops
import op_search as OS

np.seterr(all="ignore")
OUT = os.path.dirname(os.path.abspath(__file__))
rng = np.random.default_rng(3)

# ------------------------------------------------------------------ B
# overdamped Langevin  dx = -U'(x) dt + sqrt(2D) dW      (REDUCED: 4000 walkers)
HOSTS = {
 "flat / Goldstone":      (lambda x: np.zeros_like(x),
     "open JJ phase, laser phase, easy-plane spin, nematic director, CDW slide"),
 "harmonic / driven RC":  (lambda x: x,
     "CMOS analog node, CSTR concentration held by a maintained inflow"),
 "washboard / fluxoid":   (lambda x: np.sin(x),
     "JJ in a superconducting loop; flux quantisation"),
 "double well":           (lambda x: 4.0 * x * (x * x - 1.0),
     "memristor filament, ferroelectric domain, CMOS latch, spin"),
 "tilted washboard":      (lambda x: np.sin(x) - 0.4,
     "pinned CDW / skyrmion under drive"),
}
D, DT, NW, NS = 0.02, 0.005, 4000, 240000
probe = np.unique(np.round(np.logspace(1, np.log10(NS), 24)).astype(int))

partB = {}
for nm, (dU, host) in HOSTS.items():
    x = np.full(NW, 0.37)                       # an arbitrary held value
    sq = np.sqrt(2 * D * DT)
    var, tt = [], []
    j = 0
    for s in range(1, NS + 1):
        x = x - dU(x) * DT + sq * rng.standard_normal(NW)
        if j < len(probe) and s == probe[j]:
            var.append(float(x.var())); tt.append(s * DT); j += 1
    var, tt = np.array(var), np.array(tt)
    m = (tt > tt[-1] / 30) & (var > 0)
    slope = float(np.polyfit(np.log10(tt[m]), np.log10(var[m]), 1)[0])
    partB[nm] = dict(host=host, var_end=round(float(var[-1]), 5),
                     slope=round(slope, 3),
                     verdict=("MARGINAL: free diffusion, Var ~ t, value lost"
                              if slope > 0.7 else
                              "RESTORING but the held value is not free" ),
                     free_energy_2D=round(float(2 * D * tt[-1]), 4))
    print("%-22s slope(logVar/logt)=%+6.3f  Var(end)=%.4g   %s"
          % (nm, slope, var[-1], host), flush=True)

# how far the held value drifted in the two restoring landscapes: is it the
# value we put there, or the nearest well?
drift = {}
for nm in ["washboard / fluxoid", "double well"]:
    dU = HOSTS[nm][0]
    for x0 in [0.37, 0.9, 1.6, 2.6]:
        x = np.full(2000, x0)
        for _ in range(NS):
            x = x - dU(x) * DT + np.sqrt(2 * D * DT) * rng.standard_normal(2000)
        drift.setdefault(nm, {})[x0] = round(float(np.median(x)), 4)
print("\nheld value -> where it ends up (restoring landscapes):")
for k, v in drift.items():
    print("  %-22s %s" % (k, v))

# ------------------------------------------------------------------ C
# attractor census: node relaxes as tau xdot = f(x,c) - x, for c on the grid.
def census(name, lo=-12.0, hi=12.0, n=200001):
    f, dfu, dfv, dom, blurb = OS.OPS[name]
    x = np.linspace(lo, hi, n)
    ns, cont, tot = [], 0, 0
    for c in OS.X:
        cc = np.full_like(x, c)
        m = dom(x, cc)
        g = np.where(m, f(np.where(m, x, 1.0), cc), np.nan)
        gp = np.where(m, dfu(np.where(m, x, 1.0), cc), np.nan)
        h = g - x
        ok = np.isfinite(h) & np.isfinite(gp) & (np.abs(g) < 1e12)
        s = np.sign(h)
        cr = np.where(ok[:-1] & ok[1:] & (s[:-1] * s[1:] < 0))[0]
        st = int(np.sum(gp[cr] < 1.0))           # continuous-time stability
        ns.append(st); tot += len(cr)
        # is there a positive-length interval of fixed points? (continuum)
        cont += int(np.sum(ok & (np.abs(h) < 1e-9)) > 20)
    return dict(op=name, blurb=blurb, stable_med=float(np.median(ns)),
                stable_max=int(np.max(ns)), roots_tot=int(tot),
                continuum=bool(cont > 0))

NAMES = list(phys_ops.PHYS) + ["eml", "sag", "sna", "lse", "tln"]
partC = [census(n) for n in NAMES]
print("\nATTRACTOR CENSUS  (node relaxing onto its own transfer curve)")
print("%-5s %-9s %-9s %-9s %s" % ("op", "stable~", "stable_mx", "continuum", "blurb"))
for r in sorted(partC, key=lambda r: -r["stable_med"]):
    print("%-5s %-9.1f %-9d %-9s %s"
          % (r["op"], r["stable_med"], r["stable_max"], r["continuum"], r["blurb"][:46]))

# ------------------------------------------------------------------ the price
kT = 1.380649e-23 * 300.0
print("\nHOLD-TIME BOUND (Kramers): to hold ONE discrete value for time t against")
print("kT at 300 K needs a barrier dE >= kT ln(t/tau0); tau0 = 1 ps:")
for t in [1e-9, 1e-6, 1e-3, 1.0]:
    b = np.log(t / 1e-12)
    print("   t=%-8.0e  dE >= %5.1f kT = %6.3f eV = %.3g J" % (t, b, b * kT / 1.602e-19, b * kT))
print("   ...and a b-bit analog value needs 2^b such wells, i.e. it IS digital.")

json.dump(dict(langevin=partB, drift=drift, census=partC),
          open(os.path.join(OUT, "restoration.json"), "w"), indent=1)
print("\nwrote restoration.json")
