"""Tabulate the std-vs-ext sweep: accuracy at matched cell count, and the
minimum DEPTH at which each architecture reaches a per-target threshold."""
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# "useful accuracy" thresholds, one per target
THRESH = {"thermistor_beta": 0.10, "thermistor_sh": 0.10,   # Kelvin
          "I.12.1": 0.02, "I.15.10": 0.02, "I.9.18": 0.05,
          "expdiff": 0.02}                                   # NRMSE
UNIT = {"thermistor_beta": "K", "thermistor_sh": "K"}

rows = []
for f in sorted(glob.glob(os.path.join(HERE, "results", "[ABC].json"))):
    rows += json.load(open(f))

key = lambda r: (r["target"], r["hw"], r["arch"], r["depth"])
D = {key(r): r for r in rows}
targets = sorted({r["target"] for r in rows})

print("=" * 96)
print("MATCHED CELL COUNT = 12 (mesh, window 3).  test med / best over 4 seeds.")
print("=" * 96)
for hw in ("ideal", "pedestal"):
    print(f"\n### hw = {hw}   (K for thermistor, NRMSE otherwise)")
    print(f"{'target':16s} {'arch':4s} " + " ".join(
        f"{'d='+str(d)+' (w='+str(w)+')':>18s}" for d, w in
        [(1, 12), (2, 6), (3, 4), (4, 3)]) + "   params")
    for t in targets:
        for a in ("std", "ext"):
            cells = []
            p = ""
            for d in (1, 2, 3, 4):
                r = D.get((t, hw, a, d))
                if r is None:
                    cells.append(f"{'--':>18s}")
                    continue
                cells.append(f"{r['test_med']:8.4f}/{r['test_best']:<9.4f}")
                p = f"{r['params']}"
            print(f"{t:16s} {a:4s} " + " ".join(cells) + f"   {p}")

print("\n" + "=" * 96)
print("MIN DEPTH TO REACH THRESHOLD  (12 cells; '-' = not reached at any depth<=4)")
print("=" * 96)
print(f"{'target':16s} {'thr':>8s} | {'ideal std':>10s} {'ideal ext':>10s} "
      f"| {'ped std':>10s} {'ped ext':>10s}   (median | best-of-4)")
cross = {"ideal": [0, 0], "pedestal": [0, 0]}
for t in targets:
    th = THRESH[t]
    out = []
    for hw in ("ideal", "pedestal"):
        for a in ("std", "ext"):
            dm = db = None
            for d in (1, 2, 3, 4):
                r = D.get((t, hw, a, d))
                if r is None:
                    continue
                if dm is None and r["test_med"] <= th:
                    dm = d
                if db is None and r["test_best"] <= th:
                    db = d
            out.append((dm, db))
    f = lambda x: ("-" if x[0] is None else str(x[0])) + "|" + \
                  ("-" if x[1] is None else str(x[1]))
    print(f"{t:16s} {th:8.3f} | {f(out[0]):>10s} {f(out[1]):>10s} "
          f"| {f(out[2]):>10s} {f(out[3]):>10s}")
    # decisive test: std needs depth>=3 (or never), ext reaches at depth<=2
    for i, hw in enumerate(("ideal", "pedestal")):
        s, e = out[2 * i], out[2 * i + 1]
        for j in (0, 1):        # 0 = median, 1 = best
            sd = s[j] if s[j] is not None else 99
            ed = e[j] if e[j] is not None else 99
            if sd >= 3 and ed <= 2:
                cross[hw][j] += 1
                print(f"    ** CROSSES THE LINE ({hw}, "
                      f"{'median' if j == 0 else 'best'}): "
                      f"std d={sd if sd < 99 else 'never'} -> ext d={ed}")
print("\nTargets moved from depth>=3 to depth<=2:",
      {k: dict(median=v[0], best=v[1]) for k, v in cross.items()},
      f"of {len(targets)}")

# head-to-head at each depth
print("\n" + "=" * 96)
print("HEAD-TO-HEAD at equal depth AND equal cells (ext/std test-median ratio;"
      " <1 = ext better)")
print("=" * 96)
print(f"{'target':16s} " + " ".join(f"{hw[:3]+' d'+str(d):>10s}"
                                    for hw in ("ideal", "pedestal")
                                    for d in (1, 2, 3, 4)))
wins = losses = 0
for t in targets:
    c = []
    for hw in ("ideal", "pedestal"):
        for d in (1, 2, 3, 4):
            s, e = D.get((t, hw, "std", d)), D.get((t, hw, "ext", d))
            if not s or not e:
                c.append(f"{'--':>10s}")
                continue
            ratio = e["test_med"] / max(s["test_med"], 1e-12)
            wins += ratio < 0.9
            losses += ratio > 1.1
            c.append(f"{ratio:10.2f}")
    print(f"{t:16s} " + " ".join(c))
print(f"\next better by >10%: {wins} cells;  worse by >10%: {losses} cells; "
      f"of {len(targets) * 8}")
