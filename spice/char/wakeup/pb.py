import sys, numpy as np
d=np.loadtxt(sys.argv[1]); t=d[:,0]; io=d[:,1]; ic=d[:,3]; vp=d[:,9]
vf=vp[-1]; v0=vp[t<1e-6][-1]
print(f"pbias: pre={v0:.4f} final={vf:.4f}")
for tol in (10e-3, 1e-3):
    i=np.where(np.abs(vp-vf)>tol)[0][-1]; print(f"  pbias last outside +-{tol*1e3:.0f} mV: {(t[i]-1e-6)*1e9:.0f} ns")
for ts in [1.01,1.5,2,2.5,2.8,3.0,3.2,3.5]:
    i=np.searchsorted(t,ts*1e-6); print(f"  {ts}us pbias={vp[i]:.4f} io={io[i]:.3f}")
