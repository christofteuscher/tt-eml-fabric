"""Score the random-feature (ELM) rows against the trained study.

Pools results/elm.json, results/ratio_all.json and results/ratio_silicon.json
and applies the SAME criterion summarise.py uses -- best of a model family, on
`test_nrmse` for pointwise fit and `traj_nrmse` for closed loop -- so the win
counts here are comparable with the published "0 of 16 / 1 of 16".

THE HEADLINE is the 2x2 printed after the four Q blocks: what the extracted
non-idealities cost when the interior is TRAINED (2.56x pointwise, 1.92x
closed loop) against what they cost when it is FROZEN (0.95, 0.99 -- nothing).
The same silicon is expensive when interior values must mean something and
free when they need only be repeatable. That comparison contains no energy
model, no digital baseline and no node-scaling factor, which is what makes it
an independent route to the paper's composability claim.

The four Q blocks are diagnostics behind it:

  Q1  frozen vs trained interior.  Read this ONLY with Q1c below. The
      family-vs-family form lets the ELM use 192 cells against the trained
      study's 18, and even at matched cells it confounds two changes: no
      interior training AND a wider readout.

  Q1c CONTROL: frozen interior, layer-0 readout, i.e. the readout the trained
      fabric uses. The two come out level. Gradient descent through the
      behavioural model is therefore NOT what limits the trained fabric, and
      the paper's median 21.5x is not an optimisation artifact. The
      order-of-magnitude gain in Q1m is the wider readout, which costs an
      output path per cell.

  Q2  frozen fabric vs the matched baselines (mlp, poly).  The regime narrows
      the gap and does not close it: 1 of 16 pointwise, 4 of 16 closed loop.

  Q3  eml features vs tanh features at matched feature count.  The fabric
      loses by 3.26x and 8.75x, so it is not a better random projection than
      the cheapest nonlinearity available.

  Q4  silicon vs ideal, frozen.  Note that the pedestal is mildly helpful in
      BOTH regimes on this suite, so Q4 on its own is not the interesting
      contrast -- the 2x2 headline is.
"""
import json
import sys
from pathlib import Path

H = Path(__file__).resolve().parent
E = json.load(open(H / "results" / (sys.argv[1] if len(sys.argv) > 1
                                    else "elm.json")))
R = json.load(open(H / "results" / "ratio_all.json"))
# run_ratio_silicon.py supplies the trained x silicon cell of the 2x2 that
# the paper's headline is drawn from. Without it the headline cannot be
# reproduced, so this is a hard requirement rather than an optional extra.
SIL = H / "results" / "ratio_silicon.json"
if not SIL.exists():
    raise SystemExit(f"missing {SIL}; run: python run_ratio_silicon.py")
S = json.load(open(SIL))
rows = E["rows"] + R["rows"] + S["rows"]

systems = []
for r in R["rows"]:
    if r["system"] not in systems:
        systems.append(r["system"])


def fam(s, pref, key):
    c = [r for r in rows if r["system"] == s and r["model"].startswith(pref)]
    return min(c, key=lambda r: r[key]) if c else None


def med(v):
    v = sorted(x for x in v if x is not None and x == x and abs(x) != float("inf"))
    if not v:
        return float("nan")
    n = len(v)
    return v[n // 2] if n % 2 else 0.5 * (v[n // 2 - 1] + v[n // 2])


def block(title, lhs, rhs, key, lhs_lab, rhs_lab):
    """One head-to-head over all systems, on one criterion."""
    print(f"\n=== {title}  [{key}] ===")
    print(f"{'system':20s} {'class':15s} {lhs_lab:>12s} {rhs_lab:>12s} "
          f"{'ratio':>9s} {'win':>5s}")
    wins, ratios = 0, []
    for s in systems:
        a = min((fam(s, p, key) for p in lhs if fam(s, p, key)),
                key=lambda r: r[key], default=None)
        b = min((fam(s, p, key) for p in rhs if fam(s, p, key)),
                key=lambda r: r[key], default=None)
        if a is None or b is None:
            continue
        ra = a[key] / max(b[key], 1e-12)
        ratios.append(ra)
        w = a[key] < b[key]
        wins += w
        print(f"{s:20s} {a['cls']:15s} {a[key]:12.4g} {b[key]:12.4g} "
              f"{ra:9.2f} {'WIN' if w else '-':>5s}")
    print(f"{'':20s} {'':15s} {'':12s} {'wins':>12s} {wins:>4d} of "
          f"{len(ratios)}   median ratio {med(ratios):.2f}x")
    return wins, len(ratios), med(ratios)


print(f"ELM: seeds={E['seeds']} ntrain={E['ntrain']} clip={E['clip_sigma']}"
      f" sigma  cfgs={E['cfgs']}")
print(f"trained study: seeds={R['seeds']} iters={R['iters']}")

ELM_F = ["elm_ideal", "elm_pedestal", "elm_silicon"]
TRAINED = ["fabric_ideal", "fabric_pedestal"]
BASE = ["mlp", "poly"]

summary = {}
for key in ("test_nrmse", "traj_nrmse"):
    lab = "POINTWISE FIT" if key == "test_nrmse" else "CLOSED LOOP"
    summary[f"Q1 {lab}"] = block(
        f"Q1 frozen interior vs trained interior -- {lab}",
        ELM_F, TRAINED, key, "elm", "trained")
    summary[f"Q2 {lab}"] = block(
        f"Q2 frozen fabric vs matched baselines -- {lab}",
        ELM_F, BASE, key, "elm", "mlp/poly")
    summary[f"Q3 {lab}"] = block(
        f"Q3 eml features vs tanh features -- {lab}",
        ELM_F, ["elmtanh"], key, "elm", "elmtanh")
    summary[f"Q4 {lab}"] = block(
        f"Q4 silicon vs ideal, frozen -- {lab}",
        ["elm_silicon"], ["elm_ideal"], key, "silicon", "ideal")

print("\n" + "=" * 72)
print("HEADLINE: what the extracted non-idealities cost, trained vs frozen")
print("=" * 72)
print("Ratio is silicon / pedestal-only, so <1 means the extra")
print("non-idealities HELPED. This is the paper's central ELM result and it")
print("contains no energy model, no digital baseline and no node scaling.")
print(f"\n{'fitting rule':16s} {'criterion':16s} {'sil/ped':>9s} {'sil better':>11s}")
for lab, ap, bp in (("trained", "fabric_silicon", "fabric_pedestal"),
                    ("frozen (ELM)", "elm_silicon", "elm_pedestal")):
    for key, kl in (("test_nrmse", "pointwise fit"), ("traj_nrmse", "closed loop")):
        rr, w = [], 0
        for s in systems:
            a, b = fam(s, ap, key), fam(s, bp, key)
            if a is None or b is None:
                continue
            rr.append(a[key] / max(b[key], 1e-12))
            w += a[key] < b[key]
        print(f"{lab:16s} {kl:16s} {med(rr):9.2f} {w:6d} of {len(rr):<3d}")

print("\n=== Q1m frozen vs trained at MATCHED CELLS and MATCHED hw ===")
print("The family-vs-family Q1 above lets the ELM use up to 192 cells while")
print("the trained study stops at 18, so it is not a fair read on its own.")
print("Here each ELM is compared with the trained fabric of the SAME cell")
print("count on the SAME hw config. Trainable parameters are NOT matched:")
print("the ELM fits only its readout, so it has far fewer.")
for key in ("test_nrmse", "traj_nrmse"):
    print(f"\n-- {key} --")
    print(f"{'pair':28s} {'elm':>10s} {'trained':>10s} {'ratio':>8s} "
          f"{'elm par':>8s} {'trn par':>8s} {'win':>5s}")
    for hw in ("ideal", "pedestal"):
        for nc in (8, 18):
            e = [r for r in rows if r["model"] == f"elm_{hw}_c{nc}"]
            t = [r for r in rows if r["model"] == f"fabric_{hw}_c{nc}"]
            ebys = {r["system"]: r for r in e}
            tbys = {r["system"]: r for r in t}
            common = [s for s in systems if s in ebys and s in tbys]
            if not common:
                continue
            ratios = [ebys[s][key] / max(tbys[s][key], 1e-12) for s in common]
            wins = sum(ebys[s][key] < tbys[s][key] for s in common)
            print(f"{f'{hw} c{nc}':28s} "
                  f"{med([ebys[s][key] for s in common]):10.4f} "
                  f"{med([tbys[s][key] for s in common]):10.4f} "
                  f"{med(ratios):8.2f} "
                  f"{ebys[common[0]]['info']['params']:8d} "
                  f"{tbys[common[0]]['info']['params']:8d} "
                  f"{wins:2d}/{len(common):<2d}")

print("\n=== Q1c CONTROL: frozen vs trained, SAME cells, hw AND readout ===")
print("elm0_* freezes the interior but reads only layer 0, exactly the")
print("readout the trained fabric uses. The only difference left is whether")
print("the interior was trained. If elm0 still wins, gradient descent through")
print("the behavioural model is the problem; if it does not, the wider")
print("readout was doing the work in Q1m and that is what should be said.")
for key in ("test_nrmse", "traj_nrmse"):
    print(f"\n-- {key} --")
    print(f"{'pair':28s} {'elm0':>10s} {'trained':>10s} {'ratio':>8s} "
          f"{'win':>6s}")
    for hw in ("ideal", "pedestal"):
        for nc in (8, 18):
            e = {r["system"]: r for r in rows
                 if r["model"] == f"elm0_{hw}_c{nc}"}
            t = {r["system"]: r for r in rows
                 if r["model"] == f"fabric_{hw}_c{nc}"}
            common = [s for s in systems if s in e and s in t]
            if not common:
                continue
            ratios = [e[s][key] / max(t[s][key], 1e-12) for s in common]
            wins = sum(e[s][key] < t[s][key] for s in common)
            print(f"{f'{hw} c{nc}':28s} "
                  f"{med([e[s][key] for s in common]):10.4f} "
                  f"{med([t[s][key] for s in common]):10.4f} "
                  f"{med(ratios):8.2f} {wins:2d}/{len(common):<3d}")

print("\n=== scaling: does a wider feature bank help? (median over systems) ===")
print(f"{'model':20s} {'med test':>10s} {'med traj':>10s} {'cells':>6s}")
for hw in ("ideal", "pedestal", "silicon"):
    for nc in (8, 18, 48, 192):
        m = f"elm_{hw}_c{nc}"
        rs = [r for r in rows if r["model"] == m]
        if not rs:
            continue
        print(f"{m:20s} {med([r['test_nrmse'] for r in rs]):10.4f} "
              f"{med([r['traj_nrmse'] for r in rs]):10.4f} {nc:6d}")
for nf in (18, 192):
    m = f"elmtanh_f{nf}"
    rs = [r for r in rows if r["model"] == m]
    if rs:
        print(f"{m:20s} {med([r['test_nrmse'] for r in rs]):10.4f} "
              f"{med([r['traj_nrmse'] for r in rs]):10.4f} {'-':>6s}")
for pref in ("fabric_ideal", "fabric_pedestal", "mlp", "poly"):
    rs = [r for r in rows if r["model"].startswith(pref)]
    print(f"{pref + ' (trained)':20s} "
          f"{med([r['test_nrmse'] for r in rs]):10.4f} "
          f"{med([r['traj_nrmse'] for r in rs]):10.4f} {'-':>6s}")

print("\n=== headline ===")
for k, (w, n, r) in summary.items():
    print(f"{k:32s} {w:2d} of {n:2d}   median ratio {r:8.2f}x")
