"""Tables for the RATIO x CONTRACTING hypothesis test."""
import json
import sys
from pathlib import Path

H = Path(__file__).resolve().parent
R = json.load(open(H / "results" / (sys.argv[1] if len(sys.argv) > 1
                                    else "ratio.json")))
A = json.load(open(H / "results" / "amp.json"))
rows = R["rows"]
systems = []
for r in rows:
    if r["system"] not in systems:
        systems.append(r["system"])

AMP = {}
for a in A["rows"]:
    AMP.setdefault(a["system"], []).append(a["amp"])
AMP = {k: max(v) for k, v in AMP.items()}


def best(sysname, pref):
    c = [r for r in rows if r["system"] == sysname
         and r["model"].startswith(pref)]
    return min(c, key=lambda r: r["test_nrmse"]) if c else None


def bestcl(sysname, pref):
    """Best closed-loop member of a model family (fairest to each side)."""
    c = [r for r in rows if r["system"] == sysname
         and r["model"].startswith(pref)]
    return min(c, key=lambda r: r["traj_nrmse"]) if c else None


print(f"config: cfgs={R['cfgs']} seeds={R['seeds']} iters={R['iters']} "
      f"ntrain={R['ntrain']} hw={R['hw']}")

print("\n=== T1. POINTWISE fit (test NRMSE on the box; best of each family) ===")
print(f"{'system':20s} {'class':15s} {'fab_id':>8s} {'fab_ped':>8s} "
      f"{'mlp':>8s} {'poly':>9s} {'best_base':>9s} {'ratio':>7s} {'win':>4s}")
for s in systems:
    fi, fp = best(s, "fabric_ideal"), best(s, "fabric_pedestal")
    m, p = best(s, "mlp"), best(s, "poly")
    bb = min(m["test_nrmse"], p["test_nrmse"])
    bf = min(fi["test_nrmse"], fp["test_nrmse"])
    print(f"{s:20s} {fi['cls']:15s} {fi['test_nrmse']:8.4f} "
          f"{fp['test_nrmse']:8.4f} {m['test_nrmse']:8.4f} "
          f"{p['test_nrmse']:9.2e} {bb:9.2e} {bf / max(bb, 1e-12):7.1f} "
          f"{'FAB' if bf < bb else '-':>4s}")

print("\n=== T2. CLOSED LOOP (median over 4 ICs; best of each family) ===")
print(f"{'system':20s} {'class':15s} {'A_max':>6s} "
      f"{'fab_traj':>9s} {'fab_tdiv':>9s} {'base_traj':>10s} "
      f"{'base_tdiv':>10s} {'ratio':>7s} {'win':>4s}")
for s in systems:
    f = min([bestcl(s, "fabric_ideal"), bestcl(s, "fabric_pedestal")],
            key=lambda r: r["traj_nrmse"])
    b = min([bestcl(s, "mlp"), bestcl(s, "poly")],
            key=lambda r: r["traj_nrmse"])
    T = f["T"]
    print(f"{s:20s} {f['cls']:15s} {AMP.get(s, float('nan')):6.1f} "
          f"{f['traj_nrmse']:9.4f} {f['t_div'] / T:9.3f} "
          f"{b['traj_nrmse']:10.4f} {b['t_div'] / T:10.3f} "
          f"{f['traj_nrmse'] / max(b['traj_nrmse'], 1e-12):7.1f} "
          f"{'FAB' if f['traj_nrmse'] < b['traj_nrmse'] else '-':>4s}")

print("\n=== T3. steady state / invariant (best fabric vs best baseline) ===")
print(f"{'system':20s} {'fab_ss':>9s} {'base_ss':>9s} {'fab_inv':>9s} "
      f"{'base_inv':>9s}")
for s in systems:
    f = min([bestcl(s, "fabric_ideal"), bestcl(s, "fabric_pedestal")],
            key=lambda r: r["traj_nrmse"])
    b = min([bestcl(s, "mlp"), bestcl(s, "poly")],
            key=lambda r: r["traj_nrmse"])
    fi, bi = f.get("inv"), b.get("inv")
    print(f"{s:20s} {f['ss_err']:9.4f} {b['ss_err']:9.4f} "
          f"{(fi if fi is not None else float('nan')):9.4f} "
          f"{(bi if bi is not None else float('nan')):9.4f}")

print("\n=== T4. matched pairs: SAME nonlinearity, different dynamics ===")
PAIRS = [("N=x*y", "bimolecular", "lotka_volterra"),
         ("N=1/(1+p^2)", "gene_autoreg", "gene_repressilator"),
         ("N=sin(th)", "pendulum_damped", None)]
for lab, a, b in PAIRS:
    for s in (a, b):
        if s is None or s not in systems:
            continue
        f = min([bestcl(s, "fabric_ideal"), bestcl(s, "fabric_pedestal")],
                key=lambda r: r["traj_nrmse"])
        bl = min([bestcl(s, "mlp"), bestcl(s, "poly")],
                 key=lambda r: r["traj_nrmse"])
        bf = min(best(s, "fabric_ideal")["test_nrmse"],
                 best(s, "fabric_pedestal")["test_nrmse"])
        bb = min(best(s, "mlp")["test_nrmse"], best(s, "poly")["test_nrmse"])
        print(f"  {lab:12s} {s:20s} {f['cls']:15s} A={AMP.get(s, 0):5.1f} "
              f"fit {bf:.4f} vs {bb:.4f} | traj {f['traj_nrmse']:.4f} vs "
              f"{bl['traj_nrmse']:.4f} | tdiv {f['t_div'] / f['T']:.3f} vs "
              f"{bl['t_div'] / bl['T']:.3f}")

print("\n=== T5. all rows ===")
for r in rows:
    print(f"{r['system']:20s} {r['model']:20s} test {r['test_nrmse']:8.4f} "
          f"otraj {r['on_traj_nrmse']:8.4f} traj {r['traj_nrmse']:8.4f} "
          f"tdiv/T {r['t_div'] / r['T']:6.3f} ss {r['ss_err']:8.4f} "
          f"par {r['info']['params']:4d}")
