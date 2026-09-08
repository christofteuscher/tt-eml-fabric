"""
The AI Feynman equation benchmark (Udrescu & Tegmark 2020), reproduced
LOCALLY as data -- transcribed from knowledge, not downloaded.

Each entry carries:
    id          the Feynman-lectures index used by the AIF benchmark
    name        a short slug
    expr        the symbolic form, sympy-parseable
    out         (symbol, dimension) of the left-hand side
    vars        name -> (dimension, low, high, range_provenance)
    ops         (computed) the elementary operations the formula needs

Dimensions are written as monomials in the SI base symbols
    M mass, L length, T time, I current, Th temperature, N amount
"1" = dimensionless.  They are declared from the PHYSICAL MEANING of each
symbol, independently of the formula, so that `verify_feynman.py` can use
dimensional homogeneity as a genuine transcription check (see that file).

Range provenance codes (the "how I determined the range" record):
    aif_generic    AI Feynman convention: a generic positive quantity is
                   sampled U(1,5) (they used U(1,3)/U(1,5) throughout).
                   Constants (hbar, kb, c, eps, G) are treated as sampled
                   variables by the benchmark, and so they are here.
    denom_safe     range keeps a denominator / difference bounded away
                   from zero (e.g. omega in (1,2) vs omega_0 in (3,5)).
    vlt_c          relativistic constraint v < c enforced by disjoint
                   ranges: v in (1,2), c in (3,10).
    domain         needed to keep a function argument in its domain:
                   |asin arg| <= 1, log arg > 0, sqrt arg > 0.
    angle          an angle in radians; arc chosen to be representative
                   and to avoid sin()=0 where it sits in a denominator.
    unit_interval  a dimensionless material index with a physically
                   bounded range (Poisson ratio, refractive index...).
    conditioning   narrowed from the AIF generic range because the generic
                   range makes the output span >20 decades (Boltzmann
                   factors), which is a sampling artefact, not physics.

NOTHING here was downloaded; ranges are NOT claimed to be the exact
per-variable ranges of the published AIF .csv files (those could not be
obtained offline). They are documented, physically defensible choices.
"""
from __future__ import annotations

import json
import math

# --- dimension shorthands ---------------------------------------------------
D = "1"
LEN, MASS, TIME, CUR, TEMP = "L", "M", "T", "I", "Th"
VEL, ACC = "L/T", "L/T**2"
FORCE, ENER, POWER = "M*L/T**2", "M*L**2/T**2", "M*L**2/T**3"
MOM, ANGMOM = "M*L/T", "M*L**2/T"
CHG, EFLD, VOLT, BFLD = "I*T", "M*L/(T**3*I)", "M*L**2/(T**3*I)", "M/(T**2*I)"
EPS = "I**2*T**4/(M*L**3)"
HBAR = "M*L**2/T"
KB = "M*L**2/(T**2*Th)"
GRAV = "L**3/(M*T**2)"
PRESS, DENS = "M/(L*T**2)", "M/L**3"
ENDEN = "M/(L*T**2)"
FLUX = "M/T**3"                      # power per unit area
SPECRAD = "M/T**2"                   # W m^-2 Hz^-1 sr^-1
MAGMOM, CAP = "I*L**2", "I**2*T**4/(M*L**2)"
CURDEN, CHGDEN, SURFCHG = "I/L**2", "I*T/L**3", "I*T/L**2"
NUMDEN, DIPOLE = "1/L**3", "I*T*L"
FREQ, WAVENUM, AREA, VOLU = "1/T", "1/L", "L**2", "L**3"
MOB = "T/M"                          # AIF "mobility": v = mob * F
DIFF, THCOND = "L**2/T", "M*L/(T**3*Th)"
POL, MAGN = "I*T/L**2", "I/L"
VECPOT, SPRING = "M*L/(T**2*I)", "M/T**2"

_G = "aif_generic"


def _E(eid, name, expr, out_sym, out_dim, vars_, note=""):
    return {"id": eid, "name": name, "expr": expr,
            "out": {"symbol": out_sym, "dim": out_dim},
            "vars": {k: {"dim": v[0], "low": v[1], "high": v[2],
                         "range_provenance": v[3]} for k, v in vars_.items()},
            "note": note}


# generic positive variable, AIF convention
def g(dim, lo=1.0, hi=5.0, why=_G):
    return (dim, lo, hi, why)


EQUATIONS = [
    # ---------------- Volume I ----------------
    _E("I.6.2a", "gaussian_unit", "exp(-theta**2/2)/sqrt(2*pi)", "f", D,
       {"theta": g(D, 0.5, 3.0)}),
    _E("I.6.2", "gaussian_sigma",
       "exp(-(theta/sigma)**2/2)/(sqrt(2*pi)*sigma)", "f", D,
       {"sigma": g(D, 1.0, 3.0), "theta": g(D, 1.0, 3.0)}),
    _E("I.6.2b", "gaussian_shifted",
       "exp(-((theta-theta1)/sigma)**2/2)/(sqrt(2*pi)*sigma)", "f", D,
       {"sigma": g(D, 1.0, 3.0), "theta": g(D, 1.0, 3.0),
        "theta1": g(D, 1.0, 3.0)}),
    _E("I.8.14", "distance_2d", "sqrt((x2-x1)**2+(y2-y1)**2)", "d", LEN,
       {"x1": g(LEN), "x2": g(LEN), "y1": g(LEN), "y2": g(LEN)}),
    _E("I.9.18", "newton_gravity",
       "G*m1*m2/((x2-x1)**2+(y2-y1)**2+(z2-z1)**2)", "F", FORCE,
       {"G": g(GRAV, 1.0, 2.0), "m1": g(MASS, 1.0, 2.0),
        "m2": g(MASS, 1.0, 2.0),
        "x1": (LEN, 1.0, 2.0, "denom_safe"), "x2": (LEN, 3.0, 5.0, "denom_safe"),
        "y1": (LEN, 1.0, 2.0, "denom_safe"), "y2": (LEN, 3.0, 5.0, "denom_safe"),
        "z1": (LEN, 1.0, 2.0, "denom_safe"), "z2": (LEN, 3.0, 5.0, "denom_safe")},
       "r^2 kept >= 12 by disjoint coordinate ranges"),
    _E("I.10.7", "relativistic_mass", "m_0/sqrt(1-v**2/c**2)", "m", MASS,
       {"m_0": g(MASS), "v": (VEL, 1.0, 2.0, "vlt_c"),
        "c": (VEL, 3.0, 10.0, "vlt_c")}),
    _E("I.11.19", "dot_product", "x1*y1+x2*y2+x3*y3", "A", D,
       {"x1": g(D), "x2": g(D), "x3": g(D),
        "y1": g(D), "y2": g(D), "y3": g(D)}),
    _E("I.12.1", "friction", "mu*Nn", "F", FORCE,
       {"mu": g(D), "Nn": g(FORCE)}),
    _E("I.12.2", "coulomb_force", "q1*q2/(4*pi*epsilon*r**2)", "F", FORCE,
       {"q1": g(CHG), "q2": g(CHG), "epsilon": g(EPS), "r": g(LEN)}),
    _E("I.12.4", "coulomb_field", "q1/(4*pi*epsilon*r**2)", "Ef", EFLD,
       {"q1": g(CHG), "epsilon": g(EPS), "r": g(LEN)}),
    _E("I.12.5", "force_on_charge", "q2*Ef", "F", FORCE,
       {"q2": g(CHG), "Ef": g(EFLD)}),
    _E("I.12.11", "lorentz_force", "q*(Ef+B*v*sin(theta))", "F", FORCE,
       {"q": g(CHG), "Ef": g(EFLD), "B": g(BFLD), "v": g(VEL),
        "theta": (D, 0.0, 6.28, "angle")}),
    _E("I.13.4", "kinetic_energy_3d", "m*(v**2+u**2+w**2)/2", "K", ENER,
       {"m": g(MASS), "v": g(VEL), "u": g(VEL), "w": g(VEL)}),
    _E("I.13.12", "gravitational_pe", "G*m1*m2*(1/r2-1/r1)", "U", ENER,
       {"G": g(GRAV), "m1": g(MASS), "m2": g(MASS),
        "r1": g(LEN), "r2": g(LEN)}),
    _E("I.14.3", "potential_energy_height", "m*g_acc*z", "U", ENER,
       {"m": g(MASS), "g_acc": g(ACC), "z": g(LEN)}),
    _E("I.14.4", "spring_energy", "k_spring*x**2/2", "U", ENER,
       {"k_spring": g(SPRING), "x": g(LEN)}),
    _E("I.15.3x", "lorentz_x", "(x-u*t)/sqrt(1-u**2/c**2)", "x1", LEN,
       {"x": g(LEN, 5.0, 10.0), "u": (VEL, 1.0, 2.0, "vlt_c"),
        "c": (VEL, 3.0, 20.0, "vlt_c"), "t": g(TIME, 1.0, 2.0)}),
    _E("I.15.3t", "lorentz_t", "(t-u*x/c**2)/sqrt(1-u**2/c**2)", "t1", TIME,
       {"x": g(LEN, 1.0, 5.0), "u": (VEL, 1.0, 2.0, "vlt_c"),
        "c": (VEL, 3.0, 20.0, "vlt_c"), "t": g(TIME, 1.0, 5.0)}),
    _E("I.15.1", "relativistic_momentum", "m_0*v/sqrt(1-v**2/c**2)", "p", MOM,
       {"m_0": g(MASS), "v": (VEL, 1.0, 2.0, "vlt_c"),
        "c": (VEL, 3.0, 10.0, "vlt_c")}),
    _E("I.16.6", "velocity_addition", "(u+v)/(1+u*v/c**2)", "v1", VEL,
       {"u": (VEL, 1.0, 2.0, "vlt_c"), "v": (VEL, 1.0, 2.0, "vlt_c"),
        "c": (VEL, 3.0, 10.0, "vlt_c")}),
    _E("I.18.4", "center_of_mass", "(m1*r1+m2*r2)/(m1+m2)", "r", LEN,
       {"m1": g(MASS), "m2": g(MASS), "r1": g(LEN), "r2": g(LEN)}),
    _E("I.18.12", "torque", "r*F*sin(theta)", "tau", ENER,
       {"r": g(LEN), "F": g(FORCE), "theta": (D, 0.0, 6.28, "angle")}),
    _E("I.18.16", "angular_momentum", "m*r*v*sin(theta)", "L", ANGMOM,
       {"m": g(MASS), "r": g(LEN), "v": g(VEL),
        "theta": (D, 0.0, 6.28, "angle")}),
    _E("I.24.6", "oscillator_energy",
       "m*(omega**2+omega_0**2)*x**2/4", "En", ENER,
       {"m": g(MASS), "omega": g(FREQ), "omega_0": g(FREQ), "x": g(LEN)}),
    _E("I.25.13", "capacitor_voltage", "q/C", "Volt", VOLT,
       {"q": g(CHG), "C": g(CAP)}),
    _E("I.26.2", "snell_law", "asin(n*sin(theta2))", "theta1", D,
       {"n": (D, 0.3, 0.9, "domain"), "theta2": (D, 0.1, 1.0, "domain")},
       "n*sin(theta2) <= 0.76 keeps asin real"),
    _E("I.27.6", "focal_length", "1/(1/d1+n/d2)", "foc", LEN,
       {"d1": g(LEN), "d2": g(LEN), "n": g(D)}),
    _E("I.29.4", "wavenumber", "omega/c", "k", WAVENUM,
       {"omega": g(FREQ), "c": g(VEL)}),
    _E("I.29.16", "phasor_sum",
       "sqrt(x1**2+x2**2-2*x1*x2*cos(theta1-theta2))", "x", LEN,
       {"x1": g(LEN), "x2": g(LEN), "theta1": (D, 1.0, 3.0, "angle"),
        "theta2": (D, 1.0, 3.0, "angle")}),
    _E("I.30.3", "n_slit_interference",
       "Int_0*sin(n*theta/2)**2/sin(theta/2)**2", "Int", D,
       {"Int_0": g(D), "theta": (D, 0.2, 5.0, "denom_safe"),
        "n": g(D, 1.0, 5.0)}),
    _E("I.30.5", "diffraction_angle", "asin(lambd/(n*d))", "theta", D,
       {"lambd": (LEN, 1.0, 2.0, "domain"), "d": (LEN, 4.0, 6.0, "domain"),
        "n": (D, 1.0, 2.0, "domain")}),
    _E("I.32.5", "larmor_power", "q**2*a**2/(6*pi*epsilon*c**3)", "Pwr", POWER,
       {"q": g(CHG), "a": g(ACC), "epsilon": g(EPS), "c": g(VEL)}),
    _E("I.32.17", "scattered_power",
       "(epsilon*c*Ef**2/2)*(8*pi*r**2/3)*(omega**4/(omega**2-omega_0**2)**2)",
       "Pwr", POWER,
       {"epsilon": g(EPS), "c": g(VEL), "Ef": g(EFLD), "r": g(LEN),
        "omega": (FREQ, 1.0, 2.0, "denom_safe"),
        "omega_0": (FREQ, 3.0, 5.0, "denom_safe")}),
    _E("I.34.8", "cyclotron_frequency", "q*v*B/p", "omega", FREQ,
       {"q": g(CHG), "v": g(VEL), "B": g(BFLD), "p": g(MOM)}),
    _E("I.34.1", "doppler_nonrel", "omega_0/(1-v/c)", "omega", FREQ,
       {"omega_0": g(FREQ), "v": (VEL, 1.0, 2.0, "vlt_c"),
        "c": (VEL, 3.0, 10.0, "vlt_c")}),
    _E("I.34.14", "doppler_relativistic",
       "(1+v/c)/sqrt(1-v**2/c**2)*omega_0", "omega", FREQ,
       {"omega_0": g(FREQ), "v": (VEL, 1.0, 2.0, "vlt_c"),
        "c": (VEL, 3.0, 10.0, "vlt_c")}),
    _E("I.34.27", "photon_energy", "hbar*omega", "En", ENER,
       {"hbar": g(HBAR), "omega": g(FREQ)}),
    _E("I.37.4", "two_beam_interference",
       "Int1+Int2+2*sqrt(Int1*Int2)*cos(delta)", "Int", D,
       {"Int1": g(D), "Int2": g(D), "delta": (D, 0.0, 6.28, "angle")}),
    _E("I.38.12", "bohr_radius", "4*pi*epsilon*hbar**2/(m*q**2)", "r", LEN,
       {"epsilon": g(EPS), "hbar": g(HBAR), "m": g(MASS), "q": g(CHG)}),
    _E("I.39.10", "monatomic_internal_energy", "3*pr*V/2", "En", ENER,
       {"pr": g(PRESS), "V": g(VOLU)}),
    _E("I.39.11", "ideal_gas_energy", "pr*V/(gam-1)", "En", ENER,
       {"gam": (D, 1.1, 1.9, "denom_safe"), "pr": g(PRESS), "V": g(VOLU)}),
    _E("I.39.22", "ideal_gas_law", "n*kb*T/V", "pr", PRESS,
       {"n": g(D), "kb": g(KB), "T": g(TEMP), "V": g(VOLU)}),
    _E("I.40.1", "barometric_formula", "n_0*exp(-m*g_acc*x/(kb*T))", "n", D,
       {"n_0": g(D), "m": (MASS, 1.0, 2.0, "conditioning"),
        "g_acc": (ACC, 1.0, 2.0, "conditioning"),
        "x": (LEN, 1.0, 2.0, "conditioning"),
        "kb": (KB, 1.0, 2.0, "conditioning"),
        "T": (TEMP, 1.0, 2.0, "conditioning")},
       "AIF generic ranges give exp(-125)..exp(-0.25); narrowed for conditioning"),
    _E("I.41.16", "planck_law",
       "hbar*omega**3/(pi**2*c**2*(exp(hbar*omega/(kb*T))-1))", "L_rad", SPECRAD,
       {"hbar": g(HBAR, 1.0, 5.0), "omega": g(FREQ, 1.0, 5.0), "c": g(VEL),
        "kb": g(KB, 1.0, 5.0), "T": g(TEMP, 1.0, 5.0)}),
    _E("I.43.16", "drift_velocity", "mu_drift*q*Volt/d", "v", VEL,
       {"mu_drift": g(MOB), "q": g(CHG), "Volt": g(VOLT), "d": g(LEN)},
       "AIF 'mobility' is defined by v = mu*F, hence dim T/M"),
    _E("I.43.31", "einstein_relation", "mob*kb*T", "D_diff", DIFF,
       {"mob": g(MOB), "kb": g(KB), "T": g(TEMP)}),
    _E("I.43.43", "thermal_conductivity", "kb*v/(A*(gam-1))", "kappa", THCOND,
       {"gam": (D, 1.1, 1.9, "denom_safe"), "kb": g(KB), "v": g(VEL),
        "A": g(AREA)}),
    _E("I.44.4", "isothermal_work", "n*kb*T*log(V2/V1)", "En", ENER,
       {"n": g(D), "kb": g(KB), "T": g(TEMP), "V1": g(VOLU), "V2": g(VOLU)}),
    _E("I.47.23", "speed_of_sound", "sqrt(gam*pr/rho)", "c", VEL,
       {"gam": g(D, 1.1, 1.9), "pr": g(PRESS), "rho": g(DENS)}),
    _E("I.48.2", "relativistic_energy", "m*c**2/sqrt(1-v**2/c**2)", "En", ENER,
       {"m": g(MASS), "v": (VEL, 1.0, 2.0, "vlt_c"),
        "c": (VEL, 3.0, 10.0, "vlt_c")}),
    _E("I.50.26", "anharmonic_oscillation",
       "x1*(cos(omega*t)+alpha*cos(omega*t)**2)", "x", LEN,
       {"x1": g(LEN), "omega": g(FREQ), "t": g(TIME), "alpha": g(D, 1.0, 3.0)}),

    # ---------------- Volume II ----------------
    _E("II.2.42", "heat_conduction", "kappa*(T2-T1)*A/d", "Pwr", POWER,
       {"kappa": g(THCOND), "T1": g(TEMP), "T2": g(TEMP), "A": g(AREA),
        "d": g(LEN)}),
    _E("II.3.24", "flux_from_point_source", "Pwr/(4*pi*r**2)", "FE", FLUX,
       {"Pwr": g(POWER), "r": g(LEN)}),
    _E("II.4.32", "coulomb_potential", "q/(4*pi*epsilon*r)", "Volt", VOLT,
       {"q": g(CHG), "epsilon": g(EPS), "r": g(LEN)}),
    _E("II.6.11", "dipole_potential",
       "p_d*cos(theta)/(4*pi*epsilon*r**2)", "Volt", VOLT,
       {"epsilon": g(EPS), "p_d": g(DIPOLE), "theta": (D, 1.0, 3.0, "angle"),
        "r": g(LEN)}),
    _E("II.6.15a", "dipole_field_cartesian",
       "3*p_d*z*sqrt(x**2+y**2)/(4*pi*epsilon*r**5)", "Ef", EFLD,
       {"epsilon": g(EPS), "p_d": g(DIPOLE), "r": g(LEN, 1.0, 3.0),
        "x": g(LEN, 1.0, 3.0), "y": g(LEN, 1.0, 3.0), "z": g(LEN, 1.0, 3.0)}),
    _E("II.6.15b", "dipole_field_polar",
       "3*p_d*cos(theta)*sin(theta)/(4*pi*epsilon*r**3)", "Ef", EFLD,
       {"epsilon": g(EPS), "p_d": g(DIPOLE), "theta": (D, 1.0, 3.0, "angle"),
        "r": g(LEN)}),
    _E("II.8.7", "uniform_sphere_energy", "3*q**2/(20*pi*epsilon*d)", "En", ENER,
       {"q": g(CHG), "epsilon": g(EPS), "d": g(LEN)},
       "3/5 * q^2/(4 pi eps d)"),
    _E("II.8.31", "field_energy_density", "epsilon*Ef**2/2", "E_den", ENDEN,
       {"epsilon": g(EPS), "Ef": g(EFLD)}),
    _E("II.10.9", "field_in_dielectric", "sigma_den/(epsilon*(1+chi))", "Ef", EFLD,
       {"sigma_den": g(SURFCHG), "epsilon": g(EPS), "chi": g(D)}),
    _E("II.11.3", "driven_oscillator_amplitude",
       "q*Ef/(m*(omega_0**2-omega**2))", "x", LEN,
       {"q": g(CHG), "Ef": g(EFLD), "m": g(MASS),
        "omega_0": (FREQ, 3.0, 5.0, "denom_safe"),
        "omega": (FREQ, 1.0, 2.0, "denom_safe")}),
    _E("II.11.17", "boltzmann_dipole_density",
       "n_0*(1+p_d*Ef*cos(theta)/(kb*T))", "n", NUMDEN,
       {"n_0": g(NUMDEN), "kb": g(KB), "T": g(TEMP),
        "theta": (D, 1.0, 3.0, "angle"), "p_d": g(DIPOLE), "Ef": g(EFLD)}),
    _E("II.11.20", "langevin_polarization",
       "n_rho*p_d**2*Ef/(3*kb*T)", "Pol", POL,
       {"n_rho": g(NUMDEN), "p_d": g(DIPOLE), "Ef": g(EFLD), "kb": g(KB),
        "T": g(TEMP)}),
    _E("II.11.27", "clausius_mossotti_pol",
       "n*alpha/(1-n*alpha/3)*epsilon*Ef", "Pol", POL,
       {"n": (NUMDEN, 0.0, 1.0, "denom_safe"),
        "alpha": (VOLU, 0.0, 1.0, "denom_safe"),
        "epsilon": g(EPS), "Ef": g(EFLD)}),
    _E("II.11.28", "clausius_mossotti_eps",
       "1+n*alpha/(1-n*alpha/3)", "theta", D,
       {"n": (NUMDEN, 0.0, 1.0, "denom_safe"),
        "alpha": (VOLU, 0.0, 1.0, "denom_safe")}),
    _E("II.13.17", "field_of_wire", "2*Curr/(4*pi*epsilon*c**2*r)", "B", BFLD,
       {"epsilon": g(EPS), "c": g(VEL), "Curr": g(CUR), "r": g(LEN)}),
    _E("II.13.23", "charge_density_boost",
       "rho_c_0/sqrt(1-v**2/c**2)", "rho_c", CHGDEN,
       {"rho_c_0": g(CHGDEN), "v": (VEL, 1.0, 2.0, "vlt_c"),
        "c": (VEL, 3.0, 10.0, "vlt_c")}),
    _E("II.13.34", "current_density_boost",
       "rho_c_0*v/sqrt(1-v**2/c**2)", "j", CURDEN,
       {"rho_c_0": g(CHGDEN), "v": (VEL, 1.0, 2.0, "vlt_c"),
        "c": (VEL, 3.0, 10.0, "vlt_c")}),
    _E("II.15.4", "magnetic_dipole_energy", "-mom*B*cos(theta)", "En", ENER,
       {"mom": g(MAGMOM), "B": g(BFLD), "theta": (D, 1.0, 3.0, "angle")}),
    _E("II.15.5", "electric_dipole_energy", "-p_d*Ef*cos(theta)", "En", ENER,
       {"p_d": g(DIPOLE), "Ef": g(EFLD), "theta": (D, 1.0, 3.0, "angle")}),
    _E("II.21.32", "lienard_wiechert_potential",
       "q/(4*pi*epsilon*r*(1-v/c))", "Volt", VOLT,
       {"q": g(CHG), "epsilon": g(EPS), "r": g(LEN),
        "v": (VEL, 1.0, 2.0, "vlt_c"), "c": (VEL, 3.0, 10.0, "vlt_c")}),
    _E("II.24.17", "waveguide_wavenumber",
       "sqrt(omega**2/c**2-pi**2/d**2)", "k", WAVENUM,
       {"omega": (FREQ, 4.0, 6.0, "domain"), "c": (VEL, 1.0, 2.0, "domain"),
        "d": (LEN, 2.0, 4.0, "domain")},
       "ranges force omega/c >= 2 > pi/d <= 1.57 so the sqrt is real"),
    _E("II.27.16", "poynting_flux", "epsilon*c*Ef**2", "FE", FLUX,
       {"epsilon": g(EPS), "c": g(VEL), "Ef": g(EFLD)}),
    _E("II.27.18", "em_energy_density", "epsilon*Ef**2", "E_den", ENDEN,
       {"epsilon": g(EPS), "Ef": g(EFLD)}),
    _E("II.34.2a", "orbiting_current", "q*v/(2*pi*r)", "Curr", CUR,
       {"q": g(CHG), "v": g(VEL), "r": g(LEN)}),
    _E("II.34.2", "orbital_magnetic_moment", "q*v*r/2", "mom", MAGMOM,
       {"q": g(CHG), "v": g(VEL), "r": g(LEN)}),
    _E("II.34.11", "larmor_frequency", "g_*q*B/(2*m)", "omega", FREQ,
       {"g_": g(D), "q": g(CHG), "B": g(BFLD), "m": g(MASS)}),
    _E("II.34.29a", "bohr_magneton", "q*h/(4*pi*m)", "mom", MAGMOM,
       {"q": g(CHG), "h": g(HBAR), "m": g(MASS)}),
    _E("II.34.29b", "zeeman_energy", "g_*mom*B*Jz/hbar", "En", ENER,
       {"g_": g(D), "Jz": g(ANGMOM), "mom": g(MAGMOM),
        "B": g(BFLD), "hbar": g(HBAR)}),
    _E("II.35.18", "two_level_population",
       "n_0/(exp(mom*B/(kb*T))+exp(-mom*B/(kb*T)))", "n", NUMDEN,
       {"n_0": g(NUMDEN), "mom": g(MAGMOM, 1.0, 3.0), "B": g(BFLD, 1.0, 3.0),
        "kb": g(KB, 1.0, 3.0), "T": g(TEMP, 1.0, 3.0)}),
    _E("II.35.21", "brillouin_magnetization",
       "n_rho*mom*tanh(mom*B/(kb*T))", "M", MAGN,
       {"n_rho": g(NUMDEN), "mom": g(MAGMOM), "B": g(BFLD), "kb": g(KB),
        "T": g(TEMP)}),
    _E("II.36.38", "weiss_field",
       "mom*H/(kb*T)+mom*alpha*M/(epsilon*c**2*kb*T)", "f", D,
       {"mom": g(MAGMOM), "H": g(BFLD), "kb": g(KB), "T": g(TEMP),
        "alpha": g(D), "epsilon": g(EPS), "c": g(VEL), "M": g(MAGN)}),
    _E("II.37.1", "moment_in_medium", "mom*(1+chi)*B", "En", ENER,
       {"mom": g(MAGMOM), "B": g(BFLD), "chi": g(D)}),
    _E("II.38.3", "hookes_law_bar", "Y*A*x/d", "F", FORCE,
       {"Y": g(PRESS), "A": g(AREA), "d": g(LEN), "x": g(LEN)}),
    _E("II.38.14", "shear_modulus", "Y/(2*(1+sigma))", "mu_S", PRESS,
       {"Y": g(PRESS), "sigma": (D, 0.1, 0.4, "unit_interval")}),

    # ---------------- Volume III ----------------
    _E("III.4.32", "bose_occupation", "1/(exp(hbar*omega/(kb*T))-1)", "n", D,
       {"hbar": g(HBAR), "omega": g(FREQ), "kb": g(KB), "T": g(TEMP)}),
    _E("III.4.33", "planck_oscillator_energy",
       "hbar*omega/(exp(hbar*omega/(kb*T))-1)", "En", ENER,
       {"hbar": g(HBAR), "omega": g(FREQ), "kb": g(KB), "T": g(TEMP)}),
    _E("III.7.38", "spin_precession", "2*mom*B/hbar", "omega", FREQ,
       {"mom": g(MAGMOM), "B": g(BFLD), "hbar": g(HBAR)}),
    _E("III.8.54", "two_state_probability", "sin(En*t/hbar)**2", "prob", D,
       {"En": g(ENER), "t": g(TIME), "hbar": g(HBAR)}),
    _E("III.9.52", "transition_probability",
       "(p_d*Ef*t/hbar)*sin((omega-omega_0)*t/2)**2/((omega-omega_0)*t/2)**2",
       "prob", D,
       {"p_d": g(DIPOLE), "Ef": g(EFLD), "t": g(TIME), "hbar": g(HBAR),
        "omega": (FREQ, 1.0, 2.0, "denom_safe"),
        "omega_0": (FREQ, 3.0, 5.0, "denom_safe")}),
    _E("III.10.19", "zeeman_splitting_3d",
       "mom*sqrt(Bx**2+By**2+Bz**2)", "En", ENER,
       {"mom": g(MAGMOM), "Bx": g(BFLD), "By": g(BFLD), "Bz": g(BFLD)}),
    _E("III.12.43", "quantized_angular_momentum", "n*hbar", "L", ANGMOM,
       {"n": g(D), "hbar": g(HBAR)}),
    _E("III.13.18", "band_velocity", "2*En*d**2*k/hbar", "v", VEL,
       {"En": g(ENER), "d": g(LEN), "k": g(WAVENUM), "hbar": g(HBAR)}),
    _E("III.14.14", "diode_equation",
       "Curr_0*(exp(q*Volt/(kb*T))-1)", "Curr", CUR,
       {"Curr_0": g(CUR), "q": g(CHG, 1.0, 2.0), "Volt": g(VOLT, 1.0, 2.0),
        "kb": g(KB, 1.0, 2.0), "T": g(TEMP, 1.0, 2.0)},
       "exponent narrowed to <=4 for conditioning"),
    _E("III.15.12", "tight_binding_band", "2*U*(1-cos(k*d))", "En", ENER,
       {"U": g(ENER), "k": g(WAVENUM), "d": g(LEN)}),
    _E("III.15.14", "effective_mass", "hbar**2/(2*En*d**2)", "m", MASS,
       {"hbar": g(HBAR), "En": g(ENER), "d": g(LEN)}),
    _E("III.15.27", "brillouin_wavevector", "2*pi*alpha/(n*d)", "k", WAVENUM,
       {"alpha": g(D), "n": g(D), "d": g(LEN)}),
    _E("III.17.37", "angular_distribution", "beta_*(1+alpha*cos(theta))", "f", D,
       {"beta_": g(D), "alpha": g(D), "theta": (D, 0.0, 6.28, "angle")}),
    _E("III.19.51", "hydrogen_levels",
       "-m*q**4/(2*(4*pi*epsilon)**2*hbar**2*n**2)", "En", ENER,
       {"m": g(MASS), "q": g(CHG), "hbar": g(HBAR), "n": g(D),
        "epsilon": g(EPS)}),
    _E("III.21.20", "london_current", "-rho_c_0*q*A_vec/m", "j", CURDEN,
       {"rho_c_0": g(CHGDEN), "q": g(CHG), "A_vec": g(VECPOT), "m": g(MASS)}),
]

# ---------------------------------------------------------------------------
# operation tagging -- derived from the parsed tree, never hand-written
# ---------------------------------------------------------------------------
TRIG = {"sin", "cos", "tan", "asin", "acos", "atan", "atan2", "sec", "csc",
        "cot"}
# hyperbolics are NOT blocked: tanh(u) = (exp(2u)-1)/(exp(2u)+1) is inside
# the eml closure {exp, log, +, x, /}.
HYP = {"sinh", "cosh", "tanh", "asinh", "acosh", "atanh"}


def parse(eq):
    """Parse an entry's expr with a local namespace so that physics names
    (I, E, N, S, beta, gamma, lambda...) cannot collide with sympy builtins."""
    import sympy as sp
    from sympy.parsing.sympy_parser import parse_expr
    loc = {n: sp.Symbol(n, positive=False, real=True) for n in eq["vars"]}
    loc.update({"pi": sp.pi, "exp": sp.exp, "log": sp.log, "sqrt": sp.sqrt,
                "sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "asin": sp.asin,
                "acos": sp.acos, "atan": sp.atan, "tanh": sp.tanh,
                "sinh": sp.sinh, "cosh": sp.cosh})
    return parse_expr(eq["expr"], local_dict=loc, evaluate=True), loc


def ops_of(eq):
    """Elementary operations the formula requires."""
    import sympy as sp
    expr, _ = parse(eq)
    ops = set()
    for node in sp.preorder_traversal(expr):
        if isinstance(node, sp.Pow):
            e = node.exp
            if e.is_Rational and e == sp.Rational(1, 2):
                ops.add("sqrt")
            elif e.is_Rational and e == sp.Rational(-1, 2):
                ops.update(("sqrt", "div"))
            elif e.is_Number and e < 0:
                ops.add("div")
                if e != -1:
                    ops.add("pow")
            elif e.is_Number and e != 1:
                ops.add("pow")
            else:
                ops.add("pow")
        elif isinstance(node, sp.Mul):
            ops.add("mul")
            for a in node.args:
                if a.is_Rational and not a.is_Integer:
                    ops.add("div")
        elif isinstance(node, sp.Add):
            ops.add("add")
        elif isinstance(node, sp.Function):
            ops.add(type(node).__name__)
    return sorted(ops)


def is_trig_blocked(ops):
    return any(o in TRIG for o in ops)


def eml_representable_ops(ops):
    """Ops inside the eml(x,y)=exp(x)-ln(y) closure."""
    ok = {"add", "mul", "div", "pow", "sqrt", "exp", "log"} | HYP
    return all(o in ok for o in ops)


# ---------------------------------------------------------------------------
# sampling
# ---------------------------------------------------------------------------
def sampler(eq, backend="numpy"):
    """Return f(n, seed) -> (X (n,d) float64, y (n,) float64, names)."""
    import numpy as np
    import sympy as sp
    expr, loc = parse(eq)
    names = list(eq["vars"])
    syms = [loc[n] for n in names]
    f = sp.lambdify(syms, expr, "numpy")
    los = np.array([eq["vars"][n]["low"] for n in names])
    his = np.array([eq["vars"][n]["high"] for n in names])

    def sample(n=1000, seed=0):
        rng = np.random.default_rng(seed)
        X = rng.uniform(los, his, size=(n, len(names)))
        y = np.asarray(f(*[X[:, i] for i in range(len(names))]),
                       dtype=np.float64)
        if y.ndim == 0:
            y = np.full(n, float(y))
        return X, y, names

    return sample


def by_id(eid):
    for e in EQUATIONS:
        if e["id"] == eid:
            return e
    raise KeyError(eid)


def to_json(path):
    out = []
    for e in EQUATIONS:
        ops = ops_of(e)
        d = dict(e)
        d["ops"] = ops
        d["trig_blocked"] = is_trig_blocked(ops)
        d["eml_representable"] = eml_representable_ops(ops)
        d["n_vars"] = len(e["vars"])
        out.append(d)
    with open(path, "w") as fh:
        json.dump({"source": "AI Feynman benchmark (Udrescu & Tegmark 2020), "
                             "transcribed offline from knowledge",
                   "n_equations": len(out), "equations": out}, fh, indent=1)
    return out


if __name__ == "__main__":
    import os
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "feynman_equations.json")
    out = to_json(p)
    nt = sum(e["trig_blocked"] for e in out)
    print(f"{len(out)} equations -> {p}")
    print(f"trig-blocked: {nt}  ({100*nt/len(out):.1f}%)  "
          f"eml-candidate: {len(out)-nt}")
