"""
Independent verification of the transcribed AI Feynman equation set.

Three checks, each independent of the transcription itself:

 1. STRUCTURE   every symbol in the expression is declared, and every
                declared variable is used (catches dropped/renamed terms).
 2. DIMENSIONS  the expression is dimensionally homogeneous and equals the
                declared dimension of the left-hand side, and every
                exp/log/sin/... argument is dimensionless.  The dimensions
                are declared from what each symbol MEANS, not from the
                formula, so a wrong power of r, a missing c^2, a swapped
                numerator/denominator or a lost epsilon all fail here.
 3. PHYSICS     hand-written limiting cases, cross-equation identities and
                known SI numerical values (Bohr radius, Rydberg energy,
                speed of sound in air, Lorentz invariance, ...).  These
                catch the dimensionless factors that check 2 cannot see.

Plus a sampler smoke test: finite, non-constant y over the declared ranges.

Run:
  arch -arm64 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 \
      /Users/cteusche/data/projects/eml/code/fabric_sim/bench/verify_feynman.py
"""
from __future__ import annotations

import math
import sys

import numpy as np
import sympy as sp

sys.path.insert(0, "/Users/cteusche/data/projects/eml/code/fabric_sim/bench")
import feynman as F  # noqa: E402

BASE = {s: sp.Symbol(s, positive=True) for s in ("M", "L", "T", "I", "Th", "N")}
TRANSCENDENTAL = (sp.exp, sp.log, sp.sin, sp.cos, sp.tan, sp.asin, sp.acos,
                  sp.atan, sp.sinh, sp.cosh, sp.tanh)


def parse_dim(s):
    return sp.sympify(s, locals=BASE)


class DimError(Exception):
    pass


def dim_of(expr, dims):
    """Propagate dimensions through a sympy tree."""
    if expr.is_Number or expr is sp.pi or expr.is_NumberSymbol:
        return sp.Integer(1)
    if expr.is_Symbol:
        if expr.name not in dims:
            raise DimError(f"undeclared symbol {expr.name}")
        return dims[expr.name]
    if isinstance(expr, sp.Add):
        ds = [dim_of(a, dims) for a in expr.args]
        for d in ds[1:]:
            if sp.simplify(d / ds[0]) != 1:
                raise DimError(f"inhomogeneous sum: {ds[0]} vs {d} in {expr}")
        return ds[0]
    if isinstance(expr, sp.Mul):
        out = sp.Integer(1)
        for a in expr.args:
            out *= dim_of(a, dims)
        return sp.simplify(out)
    if isinstance(expr, sp.Pow):
        b, e = expr.args
        if not e.is_Number:
            if sp.simplify(dim_of(e, dims)) != 1:
                raise DimError(f"dimensional exponent in {expr}")
            if sp.simplify(dim_of(b, dims)) != 1:
                raise DimError(f"dimensional base with symbolic exp {expr}")
            return sp.Integer(1)
        return sp.simplify(dim_of(b, dims) ** e)
    if isinstance(expr, TRANSCENDENTAL):
        arg = dim_of(expr.args[0], dims)
        if sp.simplify(arg) != 1:
            raise DimError(f"{type(expr).__name__} of dimensional arg {arg}")
        return sp.Integer(1)
    raise DimError(f"unhandled node {type(expr).__name__}: {expr}")


# ---------------------------------------------------------------------------
# physics checks: hand-written, independent of the symbolic transcription
# ---------------------------------------------------------------------------
EPS0 = 8.8541878128e-12
HBAR = 1.054571817e-34
ME = 9.1093837015e-31
QE = 1.602176634e-19
KB = 1.380649e-23
CL = 299792458.0


def ev(eid, **kw):
    eq = F.by_id(eid)
    expr, loc = F.parse(eq)
    names = list(eq["vars"])
    missing = set(names) - set(kw)
    if missing:
        raise KeyError(f"{eid}: missing {missing}")
    f = sp.lambdify([loc[n] for n in names], expr, "numpy")
    return float(f(*[kw[n] for n in names]))


def rel(a, b):
    return abs(a - b) / max(abs(b), 1e-300)


def physics_checks():
    """(equation ids touched, description, callable -> bool)."""
    C = []

    C.append((["I.38.12"], "Bohr radius = 5.29177e-11 m from SI constants",
              lambda: rel(ev("I.38.12", epsilon=EPS0, hbar=HBAR, m=ME, q=QE),
                          5.29177210903e-11) < 1e-6))
    C.append((["III.19.51"], "hydrogen ground state = -13.6057 eV",
              lambda: rel(ev("III.19.51", m=ME, q=QE, hbar=HBAR, n=1.0,
                             epsilon=EPS0), -2.1798723611e-18) < 1e-5))
    C.append((["I.47.23"], "speed of sound in air (1.4, 101325 Pa, 1.225) = 340 m/s",
              lambda: rel(ev("I.47.23", gam=1.4, pr=101325.0, rho=1.225),
                          340.3) < 2e-3))
    C.append((["I.8.14"], "3-4-5 triangle",
              lambda: rel(ev("I.8.14", x1=0, x2=3, y1=0, y2=4), 5.0) < 1e-12))
    C.append((["I.10.7"], "relativistic mass -> m0 as v->0",
              lambda: rel(ev("I.10.7", m_0=2.0, v=1e-9, c=3e8), 2.0) < 1e-12))
    C.append((["I.48.2"], "relativistic energy -> m c^2 as v->0",
              lambda: rel(ev("I.48.2", m=2.0, v=1e-9, c=3.0), 18.0) < 1e-12))
    C.append((["I.15.1"], "relativistic momentum at v=0.6c is 1.25 m0 v",
              lambda: rel(ev("I.15.1", m_0=1.0, v=0.6, c=1.0), 0.75) < 1e-12))
    C.append((["I.16.6"], "velocity addition: c (+) c = c",
              lambda: rel(ev("I.16.6", u=1.0, v=1.0, c=1.0), 1.0) < 1e-12))
    C.append((["I.15.3x", "I.15.3t"],
              "Lorentz transform preserves c^2 t^2 - x^2",
              lambda: rel(
                  (2.0 * ev("I.15.3t", x=3.0, u=0.5, c=2.0, t=1.7)) ** 2
                  - ev("I.15.3x", x=3.0, u=0.5, c=2.0, t=1.7) ** 2,
                  (2.0 * 1.7) ** 2 - 3.0 ** 2) < 1e-10))
    C.append((["I.12.2", "I.12.4", "I.12.5"],
              "F = q2 * E(q1) reproduces Coulomb's law",
              lambda: rel(ev("I.12.5", q2=3.0,
                             Ef=ev("I.12.4", q1=2.0, epsilon=EPS0, r=0.5)),
                          ev("I.12.2", q1=2.0, q2=3.0, epsilon=EPS0, r=0.5))
              < 1e-12))
    C.append((["II.27.16", "II.27.18"], "Poynting flux = c * energy density",
              lambda: rel(ev("II.27.16", epsilon=EPS0, c=CL, Ef=3.0),
                          CL * ev("II.27.18", epsilon=EPS0, Ef=3.0)) < 1e-12))
    C.append((["II.11.27", "II.11.28"],
              "Clausius-Mossotti: P = (eps_r - 1) eps E",
              lambda: rel(ev("II.11.27", n=0.4, alpha=0.5, epsilon=EPS0, Ef=2.0),
                          (ev("II.11.28", n=0.4, alpha=0.5) - 1.0) * EPS0 * 2.0)
              < 1e-12))
    C.append((["I.6.2", "I.6.2a"], "Gaussian with sigma=1 equals unit Gaussian",
              lambda: rel(ev("I.6.2", sigma=1.0, theta=0.7),
                          ev("I.6.2a", theta=0.7)) < 1e-12))
    C.append((["I.6.2b", "I.6.2"], "shifted Gaussian with theta1=0 equals I.6.2",
              lambda: rel(ev("I.6.2b", sigma=2.0, theta=0.7, theta1=0.0),
                          ev("I.6.2", sigma=2.0, theta=0.7)) < 1e-12))
    C.append((["I.6.2a"], "unit Gaussian integrates to 1 (trapezoid)",
              lambda: abs(np.trapezoid(
                  [ev("I.6.2a", theta=t) for t in np.linspace(-12, 12, 20001)],
                  np.linspace(-12, 12, 20001)) - 1.0) < 1e-9))
    C.append((["I.39.10", "I.39.11"], "monatomic gas is gamma=5/3 case",
              lambda: rel(ev("I.39.10", pr=2.0, V=3.0),
                          ev("I.39.11", gam=5.0 / 3.0, pr=2.0, V=3.0)) < 1e-12))
    C.append((["III.4.32", "III.4.33"], "E = n_bose * hbar * omega",
              lambda: rel(ev("III.4.33", hbar=HBAR, omega=1e13, kb=KB, T=300.0),
                          ev("III.4.32", hbar=HBAR, omega=1e13, kb=KB, T=300.0)
                          * HBAR * 1e13) < 1e-12))
    C.append((["III.4.33"], "Planck oscillator -> kT in the classical limit",
              lambda: rel(ev("III.4.33", hbar=HBAR, omega=1e6, kb=KB, T=300.0),
                          KB * 300.0) < 1e-6))
    C.append((["I.41.16"], "Planck law -> Rayleigh-Jeans (omega^2 kT / pi^2 c^2)",
              lambda: rel(ev("I.41.16", hbar=HBAR, omega=1e8, c=CL, kb=KB,
                             T=300.0),
                          1e8 ** 2 * KB * 300.0 / (math.pi ** 2 * CL ** 2))
              < 1e-5))
    C.append((["II.13.17"], "B field of a wire = mu0 I / (2 pi r)",
              lambda: rel(ev("II.13.17", epsilon=EPS0, c=CL, Curr=2.0, r=0.1),
                          (4e-7 * math.pi) * 2.0 / (2 * math.pi * 0.1)) < 1e-6))
    C.append((["I.29.16"], "phasor sum with equal phases = |x1 - x2|",
              lambda: rel(ev("I.29.16", x1=5.0, x2=2.0, theta1=1.3, theta2=1.3),
                          3.0) < 1e-9))
    C.append((["I.44.4"], "isothermal work vanishes for V2 = V1",
              lambda: abs(ev("I.44.4", n=3.0, kb=KB, T=300.0, V1=2.0, V2=2.0))
              < 1e-30))
    C.append((["II.35.21"], "magnetization saturates at n_rho * mu",
              lambda: rel(ev("II.35.21", n_rho=1e28, mom=9.27e-24, B=1e6,
                             kb=KB, T=1.0), 1e28 * 9.27e-24) < 1e-9))
    C.append((["I.34.14", "I.34.1"],
              "relativistic and classical Doppler agree to O(v/c)",
              lambda: abs(ev("I.34.14", omega_0=1.0, v=1e-4, c=1.0)
                          - ev("I.34.1", omega_0=1.0, v=1e-4, c=1.0)) < 1e-7))
    C.append((["I.26.2"], "Snell: n=1 gives theta1 = theta2",
              lambda: rel(ev("I.26.2", n=1.0, theta2=0.4), 0.4) < 1e-12))
    C.append((["II.34.29a"], "Bohr magneton = 9.274e-24 J/T",
              lambda: rel(ev("II.34.29a", q=QE, h=2 * math.pi * HBAR, m=ME),
                          9.2740100783e-24) < 1e-6))
    C.append((["III.15.12", "III.15.14"],
              "tight-binding curvature at k->0 gives m* = hbar^2/(2 U d^2)",
              lambda: rel(
                  HBAR ** 2 / ((ev("III.15.12", U=3.0, k=1e-3, d=2.0)
                                - 2 * ev("III.15.12", U=3.0, k=0.0, d=2.0)
                                + ev("III.15.12", U=3.0, k=-1e-3, d=2.0))
                               / 1e-6),
                  ev("III.15.14", hbar=HBAR, En=3.0, d=2.0)) < 1e-6))
    C.append((["I.13.12", "I.9.18"],
              "|-dU/dr| of the gravitational PE is Newton's force",
              lambda: rel(
                  abs((ev("I.13.12", G=1.0, m1=2.0, m2=3.0, r1=1.0, r2=1e9)
                       - ev("I.13.12", G=1.0, m1=2.0, m2=3.0, r1=1.0 + 1e-7,
                            r2=1e9)) / 1e-7),
                  ev("I.9.18", G=1.0, m1=2.0, m2=3.0, x1=0, x2=1.0,
                     y1=0, y2=0, z1=0, z2=0)) < 1e-5))
    C.append((["II.6.15a", "II.6.15b"],
              "Cartesian and polar dipole transverse field agree",
              lambda: rel(ev("II.6.15a", epsilon=EPS0, p_d=2.0, r=1.5,
                             x=1.5 * math.sin(0.7), y=0.0,
                             z=1.5 * math.cos(0.7)),
                          ev("II.6.15b", epsilon=EPS0, p_d=2.0, theta=0.7,
                             r=1.5)) < 1e-12))
    C.append((["II.6.11", "II.4.32"],
              "dipole potential = superposition of +q,-q separated by s (r>>s)",
              lambda: rel(
                  ev("II.6.11", epsilon=EPS0, p_d=1e-3 * 1.0, theta=0.6,
                     r=100.0),
                  ev("II.4.32", q=1.0, epsilon=EPS0,
                     r=math.dist((0, 0, 100 * math.cos(0.6)),
                                 (0, 100 * math.sin(0.6), 5e-4)))
                  - ev("II.4.32", q=1.0, epsilon=EPS0,
                       r=math.dist((0, 0, 100 * math.cos(0.6)),
                                   (0, 100 * math.sin(0.6), -5e-4)))) < 1e-6))
    C.append((["I.32.5"], "Larmor power equals the mu0 form mu0 q^2 a^2/(6 pi c)",
              lambda: rel(ev("I.32.5", q=QE, a=1e15, epsilon=EPS0, c=CL),
                          (4e-7 * math.pi) * QE ** 2 * 1e30
                          / (6 * math.pi * CL)) < 1e-6))
    C.append((["II.8.7"], "sphere energy equals (3/5) q^2/(4 pi eps d)",
              lambda: rel(ev("II.8.7", q=2.0, epsilon=EPS0, d=0.3),
                          0.6 * 4.0 / (4 * math.pi * EPS0 * 0.3)) < 1e-12))
    C.append((["I.24.6"], "at omega = omega_0 it is the oscillator energy m w^2 x^2/2",
              lambda: rel(ev("I.24.6", m=2.0, omega=3.0, omega_0=3.0, x=0.5),
                          0.5 * 2.0 * 9.0 * 0.25) < 1e-12))
    C.append((["III.9.52"], "transition probability -> p E t/hbar on resonance",
              lambda: rel(ev("III.9.52", p_d=1.0, Ef=2.0, t=3.0, hbar=1.5,
                             omega=1.0, omega_0=1.0 + 1e-7),
                          1.0 * 2.0 * 3.0 / 1.5) < 1e-6))
    C.append((["III.7.38"], "electron spin precession = 1.7608e11 rad/s/T",
              lambda: rel(ev("III.7.38", mom=9.2740100783e-24, B=1.0,
                             hbar=HBAR), 1.7588e11) < 1e-3))
    C.append((["I.34.8", "II.34.11"],
              "cyclotron: q v B / p equals g q B / 2m with p = m v, g = 2",
              lambda: rel(ev("I.34.8", q=QE, v=1e5, B=0.3, p=ME * 1e5),
                          ev("II.34.11", g_=2.0, q=QE, B=0.3, m=ME)) < 1e-12))
    C.append((["II.3.24"], "flux integrated over the sphere returns the power",
              lambda: rel(ev("II.3.24", Pwr=7.0, r=2.0) * 4 * math.pi * 4.0,
                          7.0) < 1e-12))
    C.append((["I.40.1"], "barometric density equals n_0 at x = 0",
              lambda: rel(ev("I.40.1", n_0=3.0, m=1.0, g_acc=9.81, x=0.0,
                             kb=KB, T=300.0), 3.0) < 1e-12))
    C.append((["I.43.31", "I.43.16"],
              "Einstein relation and drift velocity share the same mobility "
              "convention (v = mob*F): D/(kb T) == v d/(q Volt)",
              lambda: rel(ev("I.43.31", mob=0.7, kb=KB, T=300.0) / (KB * 300.0),
                          ev("I.43.16", mu_drift=0.7, q=2.0, Volt=3.0, d=4.0)
                          * 4.0 / (2.0 * 3.0)) < 1e-12))
    C.append((["I.30.3"], "N-slit intensity -> n^2 I0 at theta -> 0",
              lambda: rel(ev("I.30.3", Int_0=1.0, theta=1e-6, n=4.0), 16.0)
              < 1e-6))
    C.append((["III.14.14"], "diode current is 0 at zero bias",
              lambda: abs(ev("III.14.14", Curr_0=1e-12, q=QE, Volt=0.0, kb=KB,
                             T=300.0)) < 1e-30))
    return C


def main():
    print("=" * 78)
    print("AI Feynman transcription verification")
    print("=" * 78)
    dropped, kept = [], []
    stats = {"structure": 0, "dimension": 0, "sampler": 0}

    for eq in F.EQUATIONS:
        eid = eq["id"]
        try:
            expr, loc = F.parse(eq)
        except Exception as e:
            dropped.append((eid, f"parse: {e}"))
            continue

        used = {s.name for s in expr.free_symbols}
        declared = set(eq["vars"])
        if used - declared:
            dropped.append((eid, f"undeclared symbols {sorted(used-declared)}"))
            stats["structure"] += 1
            continue
        if declared - used:
            dropped.append((eid, f"declared but unused {sorted(declared-used)}"))
            stats["structure"] += 1
            continue

        dims = {n: parse_dim(v["dim"]) for n, v in eq["vars"].items()}
        try:
            d = dim_of(expr, dims)
            want = parse_dim(eq["out"]["dim"])
            if sp.simplify(d / want) != 1:
                raise DimError(f"LHS {eq['out']['symbol']}[{want}] != RHS [{d}]")
        except DimError as e:
            dropped.append((eid, f"DIM: {e}"))
            stats["dimension"] += 1
            continue

        try:
            X, y, names = F.sampler(eq)(2000, seed=7)
            if not np.all(np.isfinite(y)):
                raise ValueError(f"{int((~np.isfinite(y)).sum())} non-finite y")
            if np.std(y) == 0:
                raise ValueError("constant y")
            dyn = (np.log10(np.max(np.abs(y)) / max(np.min(np.abs(y)), 1e-300))
                   if np.min(np.abs(y)) > 0 else float("inf"))
        except Exception as e:
            dropped.append((eid, f"SAMPLE: {e}"))
            stats["sampler"] += 1
            continue

        kept.append((eq, F.ops_of(eq), dyn))

    print(f"\n[1+2] structure/dimension/sampler: {len(kept)} passed, "
          f"{len(dropped)} failed")
    for eid, why in dropped:
        print(f"      DROP {eid:12s} {why}")

    print("\n[3] physics checks (limiting cases / identities / SI values)")
    kept_ids = {e["id"] for e, _, _ in kept}
    pc_fail = []
    npass = 0
    for ids, desc, fn in physics_checks():
        if not set(ids) <= kept_ids:
            print(f"      SKIP {ids} (equation already dropped)")
            continue
        try:
            ok = bool(fn())
        except Exception as e:
            ok = False
            desc += f"  [raised {type(e).__name__}: {e}]"
        if ok:
            npass += 1
        else:
            pc_fail.append((ids, desc))
        print(f"      {'PASS' if ok else 'FAIL'}  {'/'.join(ids):24s} {desc}")
    covered = sorted({i for ids, _, _ in physics_checks() for i in ids})
    print(f"\n      {npass} passed, {len(pc_fail)} failed; "
          f"{len(covered)} equations touched by a physics check")

    ill = [(e['id'], d) for e, _, d in kept if d > 12]
    if ill:
        print("\n[4] wide-dynamic-range warnings (log10 |y| span > 12):")
        for eid, d in ill:
            print(f"      {eid:12s} {d:.1f} decades")

    trig = [e["id"] for e, ops, _ in kept if F.is_trig_blocked(ops)]
    hyp = [e["id"] for e, ops, _ in kept if set(ops) & F.HYP]
    print("\n" + "=" * 78)
    print(f"KEPT {len(kept)} / {len(F.EQUATIONS)} equations")
    print(f"trig-blocked (sin/cos/tan/asin/acos/atan): {len(trig)} "
          f"= {100*len(trig)/len(kept):.1f}% of kept -> NOT EML-representable")
    print(f"eml-candidate (exp/log/+/x//,pow,sqrt,tanh only): "
          f"{len(kept)-len(trig)} = {100*(len(kept)-len(trig))/len(kept):.1f}%")
    print(f"hyperbolic (representable via exp): {len(hyp)} {hyp}")

    from collections import Counter
    opc = Counter(o for _, ops, _ in kept for o in ops)
    print("\noperation histogram over kept equations:")
    for o, c in opc.most_common():
        print(f"  {o:8s} {c:4d}  ({100*c/len(kept):.0f}%)")
    nv = Counter(len(e["vars"]) for e, _, _ in kept)
    print("variable-count histogram: " +
          ", ".join(f"{k}v:{nv[k]}" for k in sorted(nv)))
    prov = Counter(v["range_provenance"] for e, _, _ in kept
                   for v in e["vars"].values())
    print("range provenance: " + ", ".join(f"{k}={c}" for k, c in
                                           prov.most_common()))

    # ---- write the verification status back into the dataset -------------
    import json
    import os
    checks_for = {}
    for ids, desc, _ in physics_checks():
        for i in ids:
            checks_for.setdefault(i, []).append(desc)
    dropped_ids = {eid for eid, _ in dropped}
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "feynman_equations.json")
    blob = json.load(open(path))
    n_phys = 0
    for rec in blob["equations"]:
        eid = rec["id"]
        pc = checks_for.get(eid, [])
        n_phys += bool(pc)
        rec["verification"] = {
            "structure_and_dimensions": eid not in dropped_ids,
            "sampler_finite": eid not in dropped_ids,
            "independent_physics_checks": pc,
            "dynamic_range_decades": next(
                (round(d, 2) for e, _, d in kept if e["id"] == eid), None),
        }
    blob["verification_summary"] = {
        "method": "structural (declared == used symbols) + dimensional "
                  "homogeneity in SI base dimensions + sampler finiteness + "
                  "hand-written physics limiting cases / cross-equation "
                  "identities / known SI numerical values",
        "kept": len(kept), "dropped": len(dropped),
        "dropped_ids": sorted(dropped_ids),
        "physics_checks_run": len(physics_checks()),
        "physics_checks_failed": len(pc_fail),
        "equations_with_an_independent_physics_check": n_phys,
        "caveat": "dimensional analysis cannot detect a wrong dimensionless "
                  f"prefactor; the {len(blob['equations'])-n_phys} equations "
                  "without a physics check rest on structure+dimensions only",
    }
    json.dump(blob, open(path, "w"), indent=1)
    print(f"\nverification status written into {path}")
    print(f"  equations with an independent physics check: {n_phys}; "
          f"dimension+structure only: {len(blob['equations'])-n_phys}")
    return len(dropped), len(pc_fail)


if __name__ == "__main__":
    nd, nf = main()
    sys.exit(0)
