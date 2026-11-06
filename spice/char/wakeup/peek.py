import sys, numpy as np
d=np.loadtxt(sys.argv[1]); t=d[:,0]; io=d[:,1]; ic=d[:,3]; vd=d[:,7]
for ts in [0.99,1.0,1.005,1.01,1.02,1.05,1.1,1.2,1.5,2,2.5,3,3.5,4,4.5,5,5.5,6,8,10,20,39]:
    i=np.searchsorted(t,ts*1e-6); print(f"{ts:6.3f}us io={io[i]:10.4f} Icell={ic[i]*1e6:9.3f}uA vdd={vd[i]:.3f}")
i=np.argmax(io); print("max io at",t[i]*1e6,"us", io[i])
