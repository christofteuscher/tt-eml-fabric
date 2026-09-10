"""The TRAINED fabric on the PDK-realistic silicon config.

SIMULATION ONLY.  Nothing here measures a physical device.

WHY THIS RUN EXISTS
-------------------
run_elm.py shows that on the frozen (random-feature) fabric the PDK
mismatch, the output rail and 8-bit weights cost almost nothing, because no
interior cell has a target value and a feature only has to be REPEATABLE.
That half is only worth something if the other half is established on the
SAME 16 systems: that when every interior cell IS required to hold a stated
value, the same non-idealities are expensive.

The published ratio study (results/ratio_all.json) ran only `ideal` and
`pedestal`, so the contrast cannot be drawn from it.  This adds the missing
cell of the 2x2: trained x silicon.

    fitting rule   ideal    pedestal   silicon
    trained        published published  THIS RUN
    frozen (ELM)   run_elm  run_elm    run_elm

Everything else -- systems, ICs, training box, 768 samples, 3 seeds, 3000
Adam iterations, best-of-seeds on training error, the closed-loop
substitution and every NRMSE definition -- is run_ratio.py's, imported
rather than copied, so the new rows pool with the published ones.  The only
change is one entry in the hw table, monkey-patched onto the imported
module so that run_ratio.py itself is left exactly as it was published.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import run_ratio                                                      # noqa
from run_ratio import (reference, training_box, make_data, nrmse,     # noqa
                       fit_fabric, closed_loop, summarise, NTRAIN, PEDESTAL)
from eml_fabric_topo import FabricSpec                                # noqa
from ratio_systems import SYSTEMS, nl_args                            # noqa

# Identical to run_elm.py's "silicon": the realised cell's ln pedestal plus
# run_pdk_chip.py's PDK mismatch, output rail and weight resolution.  Read
# noise stays off, as it is off in both other studies.  atten_v stays off:
# it is derived from the pedestal and enabling both double-counts.
SILICON = dict(ln_pedestal=PEDESTAL, mismatch_gain_std=0.02,
               mismatch_offset_std=0.005, sat=30.0, weight_bits=8)

# Monkey-patch rather than edit: fit_fabric reads run_ratio's module-global
# HW, so replacing that table changes which configs are built without
# touching a published file.
run_ratio.HW = {"silicon": SILICON}
CFGS = run_ratio.CFGS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", default="")
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--iters", type=int, default=3000)
    ap.add_argument("--out", default="results/ratio_silicon.json")
    a = ap.parse_args()
    names = a.systems.split(",") if a.systems else list(SYSTEMS)

    out = {"note": "SIMULATION ONLY. Trained fabric on the PDK-realistic "
                   "silicon config; the missing cell of the trained x frozen "
                   "by ideal x pedestal x silicon grid. Protocol imported "
                   "from run_ratio.py unchanged.",
           "hw": {"silicon": SILICON}, "cfgs": [list(c) for c in CFGS],
           "seeds": a.seeds, "iters": a.iters, "ntrain": NTRAIN, "rows": []}

    t0 = time.time()
    print(f"{'system':20s} {'model':22s} {'testN':>9s} {'trajN':>9s} "
          f"{'tdiv/T':>7s} {'par':>5s}", flush=True)

    for name in names:
        s = SYSTEMS[name]
        te, refs = reference(s)
        lo, hi = training_box(name, refs)
        in_off = np.where(lo < 0.5, 0.5 - lo, 0.0)
        xt, yt, xv, yv = make_data(s, lo, hi)
        yt = yt.reshape(len(xt), -1)
        yv = yv.reshape(len(xv), -1)
        Ptr = np.concatenate([nl_args(name, y) for y in refs], 0)
        ytr = s["nl"](Ptr).reshape(len(Ptr), -1)

        for cfg in CFGS:
            nc = sum(FabricSpec(topology=cfg[0], depth=cfg[1],
                                width=cfg[2]).layer_sizes())
            F, info = fit_fabric(s, xt, yt, xv, yv, in_off, "silicon",
                                 a.seeds, a.iters, cfg)
            info["cfg"] = list(cfg)
            mname = f"fabric_silicon_c{nc}"
            te_n = float(np.mean([nrmse(F(xv)[:, k], yv[:, k])
                                  for k in range(s["n_out"])]))
            ot_n = float(np.mean([nrmse(F(Ptr)[:, k], ytr[:, k])
                                  for k in range(s["n_out"])]))
            cl = summarise(closed_loop(s, name, F, te, refs, lo, hi))
            out["rows"].append(dict(system=name, cls=s["cls"], model=mname,
                                    test_nrmse=te_n, on_traj_nrmse=ot_n,
                                    T=s["T"], info=info, **cl))
            print(f"{name:20s} {mname:22s} {te_n:9.4f} "
                  f"{cl['traj_nrmse']:9.4f} {cl['t_div'] / s['T']:7.3f} "
                  f"{info['params']:5d} [{time.time() - t0:5.0f}s]",
                  flush=True)
            Path(a.out).parent.mkdir(parents=True, exist_ok=True)
            json.dump(out, open(a.out, "w"), indent=2)

    print(f"\nSaved {a.out} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
