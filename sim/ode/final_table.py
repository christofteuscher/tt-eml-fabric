"""Final ODE-study tables: fit accuracy, closed-loop, invariant drift."""
import json
from pathlib import Path

H = Path(__file__).resolve().parent
R = json.load(open(H / "results" / "ode.json"))
B = json.load(open(H / "results" / "ode_budget.json"))
T = {"lotka_volterra": 20.0, "van_der_pol": 20.0,
     "michaelis_menten": 6.0, "pendulum": 20.0}
K = {(r["system"], r["cells"], r["hw"]): r for r in R["rows"]}
print(f"rows={len(R['rows'])} seeds={R['seeds']} iters={R['iters']} hw={R['hw']}")

print("\n=== 1. fit accuracy vs cells (test NRMSE / on-trajectory NRMSE) ===")
print(f"{'system':17s} {'cells':>5} {'ideal_te':>9} {'ideal_otr':>9} "
      f"{'ped_te':>9} {'ped_otr':>9}")
for s in T:
    for c in (8, 18, 32):
        i, p = K.get((s, c, "ideal")), K.get((s, c, "pedestal"))
        if not i or not p:
            continue
        print(f"{s:17s} {c:5d} {i['test_nrmse']:9.4f} "
              f"{i['on_traj_nrmse']:9.4f} {p['test_nrmse']:9.4f} "
              f"{p['on_traj_nrmse']:9.4f}")

print("\n=== 2. closed loop (median of 5 ICs) ===")
print(f"{'system':17s} {'hw':9s} {'cel':>3} {'otraj':>7} {'trajNRMSE':>10} "
      f"{'tdiv/T':>7} {'oob':>5} {'invdrift':>9} {'invref':>9}")
for r in R["rows"]:
    i, ir = r["inv_drift_med"], r["inv_drift_ref_med"]
    print(f"{r['system']:17s} {r['hw']:9s} {r['cells']:3d} "
          f"{r['on_traj_nrmse']:7.4f} {r['traj_nrmse_med']:10.4f} "
          f"{r['t_div_med'] / T[r['system']]:7.3f} {r['oob_med']:5.2f} "
          f"{(i if i is not None else float('nan')):9.4f} "
          f"{(ir if ir is not None else float('nan')):9.2e}")

print("\n=== 3. best fabric per system vs polynomial baseline ===")
print(f"{'system':17s} {'best_te':>8} {'cells':>5} {'hw':9s} "
      f"{'poly_te':>9} {'deg':>3} {'nterms':>6}")
for s in T:
    rs = [r for r in R["rows"] if r["system"] == s]
    if not rs:
        continue
    b = min(rs, key=lambda r: r["test_nrmse"])
    pl = [p for p in B["poly"] if p["system"] == s]
    bp = min(pl, key=lambda p: p["test_nrmse"])
    print(f"{s:17s} {b['test_nrmse']:8.4f} {b['cells']:5d} {b['hw']:9s} "
          f"{bp['test_nrmse']:9.2e} {bp['deg']:3d} {bp['nterms']:6d}")
