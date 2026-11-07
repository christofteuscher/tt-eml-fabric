import sys, numpy as np
d=np.loadtxt(sys.argv[1]); t=d[:,0]; io=d[:,1]; ic=d[:,3]; t0=1e-6
m=t>=t0; i=np.argmax(ic*m); print(f"peak Icell={ic[i]*1e6:.1f}uA at +{(t[i]-t0)*1e9:.0f}ns; peak|io|={np.abs(io[m]).max()*0.5:.1f}uA")
hi=m&(ic>2*ic[-1]); print(f"time with Icell>2x final: {np.sum(np.diff(t)[hi[:-1]])*1e9:.0f} ns, between +{(t[hi][0]-t0)*1e9:.0f} and +{(t[hi][-1]-t0)*1e9:.0f} ns" if hi.any() else "no >2x interval")
