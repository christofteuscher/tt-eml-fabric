"""Print the tables for the ODE study from results/ode.json."""
import json
from pathlib import Path

R = json.load(open(Path(__file__).parent / "results" / "ode.json"))

print("=== fit accuracy vs cell count (best of seeds, NRMSE) ===")
print(f"{'system':17s} {'cells':>5} {'ideal_tr':>9} {'ideal_te':>9} "
      f"{'ped_tr':>9} {'ped_te':>9} {'id_ontraj':>9} {'pd_ontraj':>9}")
key = {}
for r in R["rows"]:
    key[(r["system"], r["cells"], r["hw"])] = r
for s in dict.fromkeys(r["system"] for r in R["rows"]):
    for c in dict.fromkeys(r["cells"] for r in R["rows"] if r["system"] == s):
        i, p = key[(s, c, "ideal")], key[(s, c, "pedestal")]
        print(f"{s:17s} {c:5d} {i['train_nrmse']:9.4f} {i['test_nrmse']:9.4f} "
              f"{p['train_nrmse']:9.4f} {p['test_nrmse']:9.4f} "
              f"{i['on_traj_nrmse']:9.4f} {p['on_traj_nrmse']:9.4f}")

print("\n=== closed loop (median over 5 ICs) ===")
print(f"{'system':17s} {'hw':9s} {'cells':>5} {'fit':>8} {'ontraj':>8} "
      f"{'trajNRMSE':>10} {'t_div/T':>8} {'oob':>5} {'invdrift':>9} "
      f"{'invref':>9}")
T = {"lotka_volterra": 20.0, "van_der_pol": 20.0,
     "michaelis_menten": 6.0, "pendulum": 20.0}
for r in R["rows"]:
    idr = r["inv_drift_med"]
    idrr = r["inv_drift_ref_med"]
    print(f"{r['system']:17s} {r['hw']:9s} {r['cells']:5d} "
          f"{r['test_nrmse']:8.4f} {r['on_traj_nrmse']:8.4f} "
          f"{r['traj_nrmse_med']:10.4f} "
          f"{r['t_div_med'] / T[r['system']]:8.3f} {r['oob_med']:5.2f} "
          f"{(idr if idr is not None else float('nan')):9.4f} "
          f"{(idrr if idrr is not None else float('nan')):9.2e}")

print("\n=== per-IC detail, largest fabric ===")
for r in R["rows"]:
    if r["cells"] != max(q["cells"] for q in R["rows"]):
        continue
    print(f"-- {r['system']} / {r['hw']}  box lo={['%.2f' % v for v in r['box_lo']]} "
          f"hi={['%.2f' % v for v in r['box_hi']]} off={r['in_off']}")
    for q in r["traj"]:
        print(f"   ic={['%.2f' % v for v in q['ic']]} t_div={q['t_div']:7.3f} "
              f"covered={q['covered']:7.3f} nrmse={q['traj_nrmse']:9.4f} "
              f"oob={q['oob_frac']:.2f} "
              f"inv={q.get('inv_drift') if q.get('inv_drift') is None else round(q['inv_drift'], 4)}")
