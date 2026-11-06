#!/usr/bin/env python3
"""Settling/energy analysis.  wrdata layout: t io t icell t iref t vd (time repeated).
Settling = last instant outside the band, measured from
the event start t0 (start of the 10 ns edge); band relative to the final value (F)
and, for steps, the step amplitude (S); linear interpolation of the crossing.
Final value = mean of io over the last 1 us.  Energy = int v(vdd)*i dt from t0."""
import sys, numpy as np
def load(f):
    d = np.loadtxt(f)
    return d[:, 0], d[:, 1], d[:, 3], d[:, 5], d[:, 7]
def settle(t, y, t0, band):
    out = np.abs(y - yf) > band
    idx = np.where(out & (t >= t0))[0]
    if len(idx) == 0: return 0.0
    i = idx[-1]
    if i + 1 >= len(t): return np.inf
    # interpolate exit crossing between i and i+1
    e0, e1 = abs(y[i] - yf) - band, abs(y[i + 1] - yf) - band
    tc = t[i] + (t[i + 1] - t[i]) * e0 / (e0 - e1) if e0 != e1 else t[i + 1]
    return tc - t0
def energy(t, p, t0, t1):
    m = (t >= t0) & (t <= t1)
    tt = np.concatenate([[t0], t[m], [t1]]); pp = np.interp(tt, t, p)
    return np.trapezoid(pp, tt)
if __name__ == "__main__":
    f = sys.argv[1]; t0 = float(sys.argv[2]); y0 = float(sys.argv[3]) if len(sys.argv) > 3 else None
    t, io, ic, ir, vd = load(f)
    yf = io[t >= t[-1] - 1e-6].mean()
    pc, pr = vd * ic, vd * ir
    ps = pc[t >= t[-1] - 1e-6].mean()
    print(f"file {f}: npts={len(t)} tend={t[-1]*1e6:.2f}us final io={yf:.6f} Icell_final={ic[-1]*1e6:.4f}uA Pcell_final={ps*1e6:.3f}uW Iref={ir[-1]*1e6:.4f}uA")
    pre = io[t < t0]
    print(f"  pre-event io={pre[-1]:.6f} Icell={ic[t<t0][-1]*1e6:.5f}uA")
    res = {}
    for lab, ref in (("F", abs(yf)),) + ((("S", abs(yf - y0)),) if y0 is not None else ()):
        for pct in (1.0, 0.1, 0.01):
            ts = settle(t, io, t0, ref * pct / 100)
            Ec = energy(t, pc, t0, t0 + ts); Er = energy(t, pr, t0, t0 + ts)
            print(f"  {pct:5}% ({lab}): t={ts*1e9:8.1f} ns  E_cell(int)={Ec*1e12:7.2f} pJ  E_ref(int)={Er*1e12:6.3f} pJ  Pstat*t={ps*ts*1e12:7.2f} pJ")
    post = io[t >= t0]
    if y0 is not None:
        amp = yf - y0
        ov = (post - yf).max() / abs(amp) * 100 if amp > 0 else (yf - post).max() / abs(amp) * 100
        rev = (y0 - post).max() / abs(amp) * 100 if amp > 0 else (post - y0).max() / abs(amp) * 100
        print(f"  overshoot={ov:.2f}% of step  reverse excursion={rev:.2f}%")
    else:
        print(f"  max io after event={post.max():.4f} ({(post.max()/yf-1)*100:+.2f}% of final), min={post.min():.4f}")
    # first time reaching within 1% band (first entry)
    ent = np.where(np.abs(post - yf) <= 0.01 * abs(yf))[0]
    if len(ent): print(f"  first entry into 1% band: {(t[t>=t0][ent[0]]-t0)*1e9:.1f} ns")
    Etot = energy(t, pc, t0, t0 + 10e-6)
    print(f"  E_cell over first 10us={Etot*1e12:.1f} pJ vs Pstat*10us={ps*10e-6*1e12:.1f} pJ -> excess={(Etot-ps*10e-6)*1e12:+.2f} pJ")
