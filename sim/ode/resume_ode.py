"""Resume the ODE study: run only the (system, hw, cfg) rows missing from
results/ode.json and merge them back in.  Same seeds/iters as the original
full run so recovered and new rows are directly comparable.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run_ode as R                                                # noqa
from ode_systems import SYSTEMS, nl_args                           # noqa

OUT = HERE / "results" / "ode.json"
SEEDS, ITERS = 3, 2500

out = json.load(open(OUT))
have = {(r["system"], r["hw"], tuple(r["cfg"])) for r in out["rows"]}
todo = [(n, hw, cfg) for n in SYSTEMS for hw in R.HW for cfg in R.CFGS
        if (n, hw, tuple(cfg)) not in have]
print(f"have {len(have)} rows, todo {len(todo)}", flush=True)

t0 = time.time()
cache = {}
for name, hw, cfg in todo:
    sys_ = SYSTEMS[name]
    if name not in cache:
        te, refs = R.reference(sys_)
        lo, hi = R.training_box(name, refs)
        in_off = np.where(lo < 0.5, 0.5 - lo, 0.0)
        cache[name] = (te, refs, lo, hi, in_off,
                       R.make_data(sys_, name, lo, hi))
    te, refs, lo, hi, in_off, data = cache[name]
    xt, yt, xv, yv = data
    m, scale, fm = R.fit(sys_, name, xt, yt, xv, yv, in_off, cfg, hw,
                         SEEDS, ITERS)
    N = R.fabric_fn(m, scale, in_off)
    Ptr = np.concatenate([nl_args(name, y) for y in refs], 0)
    ytr = sys_["nl"](Ptr)
    on_traj = float(np.sqrt(np.mean((N(Ptr) - ytr) ** 2))
                    / np.sqrt(np.mean(ytr ** 2)))
    rows = R.closed_loop(sys_, name, N, te, refs, lo, hi)
    r = dict(system=name, hw=hw, cfg=list(cfg), box_lo=lo.tolist(),
             box_hi=hi.tolist(), in_off=in_off.tolist(),
             on_traj_nrmse=on_traj, traj=rows, **fm)
    r["traj_nrmse_med"] = R.med([q["traj_nrmse"] for q in rows])
    r["t_div_med"] = R.med([q["t_div"] for q in rows])
    r["oob_med"] = R.med([q["oob_frac"] for q in rows])
    idr = [q.get("inv_drift") for q in rows if q.get("inv_drift") is not None]
    r["inv_drift_med"] = R.med(idr) if idr else None
    r["inv_drift_ref_med"] = R.med(
        [q["inv_drift_ref"] for q in rows
         if q.get("inv_drift_ref") is not None]) if idr else None
    out["rows"].append(r)
    print(f"{name:17s} {hw:9s} {fm['cells']:5d} tr={fm['train_nrmse']:.4f} "
          f"te={fm['test_nrmse']:.4f} traj={r['traj_nrmse_med']:.4f} "
          f"tdiv/T={r['t_div_med'] / sys_['T']:.3f} [{time.time()-t0:5.0f}s]",
          flush=True)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=2)
print(f"DONE {len(out['rows'])} rows ({time.time()-t0:.0f}s)")
