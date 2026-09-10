"""Regression guard for every ELM number the paper states.

Recomputes each claim from the committed JSON and compares it against the
value printed in the manuscript. It does no training and needs no torch, so
it runs in about a second and can be used as a pre-submission check:

    python3 test_elm_headline.py            # print, exit 1 on any drift
    python3 test_elm_headline.py --verbose  # show every comparison

Why this exists. The numbers below appear in four places -- the abstract, the
Results, the Discussion and SOFTWARE_RESULTS.md -- and earlier versions of
this project shipped figures that had drifted between the record and the
manuscript. Anything that changes the JSON, the scoring rule or the model
should either keep these values or fail here loudly.

Two of the pinned claims are corrections that must not silently revert:

  * The CONTROL. An early reading of these runs held that the frozen fabric
    beats the trained one and therefore that the paper's median 21.5x was
    partly an optimisation failure of gradient descent. It is not: with the
    readout held to layer 0, frozen and trained are level. The gain comes
    from the wider readout. The q1c control checks pin that.

  * The 2x2. The extracted non-idealities are expensive when the interior is
    trained and free when it is frozen. That is the paper's ELM result.
"""
import argparse
import json
import sys
from pathlib import Path

H = Path(__file__).resolve().parent
R = H / "results"

TOL = 0.02          # relative tolerance on medians
COUNT_EXACT = True  # win counts are integers and must match exactly


def load():
    need = ["elm.json", "ratio_all.json", "ratio_silicon.json"]
    missing = [n for n in need if not (R / n).exists()]
    if missing:
        raise SystemExit(f"missing {missing}; run run_elm.py and "
                         f"run_ratio_silicon.py first")
    rows = []
    for n in need:
        rows += json.load(open(R / n))["rows"]
    order = []
    for r in json.load(open(R / "ratio_all.json"))["rows"]:
        if r["system"] not in order:
            order.append(r["system"])
    return rows, order


def med(v):
    v = sorted(x for x in v if x is not None and x == x
               and abs(x) != float("inf"))
    if not v:
        return float("nan")
    n = len(v)
    return v[n // 2] if n % 2 else 0.5 * (v[n // 2 - 1] + v[n // 2])


def best(rows, s, pref, key):
    c = [r for r in rows if r["system"] == s and r["model"].startswith(pref)]
    return min(c, key=lambda r: r[key]) if c else None


def head_to_head(rows, order, lhs, rhs, key):
    """Median ratio lhs/rhs and how often lhs is better, over all systems."""
    ratios, wins = [], 0
    for s in order:
        a = min((best(rows, s, p, key) for p in lhs
                 if best(rows, s, p, key)), key=lambda r: r[key], default=None)
        b = min((best(rows, s, p, key) for p in rhs
                 if best(rows, s, p, key)), key=lambda r: r[key], default=None)
        if a is None or b is None:
            continue
        ratios.append(a[key] / max(b[key], 1e-12))
        wins += a[key] < b[key]
    return med(ratios), wins, len(ratios)


ELM = ["elm_ideal", "elm_pedestal", "elm_silicon"]
BASE = ["mlp", "poly"]


def checks(rows, order):
    """(label, computed, expected, kind) for every claim the paper makes."""
    out = []

    # --- the 2x2: the paper's ELM headline -----------------------------
    for lab, ap, bp, e_pt, e_cl in (
            ("2x2 trained  silicon/pedestal", "fabric_silicon",
             "fabric_pedestal", 2.56, 1.92),
            ("2x2 frozen   silicon/pedestal", "elm_silicon",
             "elm_pedestal", 0.95, 0.99)):
        for key, kl, exp in (("test_nrmse", "pointwise", e_pt),
                             ("traj_nrmse", "closedloop", e_cl)):
            r, _, _ = head_to_head(rows, order, [ap], [bp], key)
            out.append((f"{lab} {kl}", r, exp, "ratio"))

    # --- the regime does not rescue the fabric -------------------------
    for key, kl, exp_w in (("test_nrmse", "pointwise", 1),
                           ("traj_nrmse", "closedloop", 4)):
        _, w, n = head_to_head(rows, order, ELM, BASE, key)
        out.append((f"frozen vs matched baselines {kl} wins", w, exp_w,
                    "count"))
        assert n == 16, f"expected 16 systems, scored {n}"
    for key, kl, exp_w in (("test_nrmse", "pointwise", 1),
                           ("traj_nrmse", "closedloop", 0)):
        _, w, _ = head_to_head(rows, order, ["fabric_ideal",
                                             "fabric_pedestal"], BASE, key)
        out.append((f"trained vs matched baselines {kl} wins (published)",
                    w, exp_w, "count"))

    # --- not even a good random-feature map ----------------------------
    for key, kl, exp in (("test_nrmse", "pointwise", 3.26),
                         ("traj_nrmse", "closedloop", 8.75)):
        r, _, _ = head_to_head(rows, order, ELM, ["elmtanh"], key)
        out.append((f"eml features vs tanh features {kl}", r, exp, "ratio"))

    # --- the CONTROL: freezing is not what helped ----------------------
    # The paper states one band over all four matched pairs and both
    # criteria: median ratios 0.82--1.95, winning 4 to 10 of 16. A ratio
    # far below that band would mean freezing really does beat training and
    # the paper's reading is wrong. Bounds are checked as bounds -- the
    # stated range must CONTAIN every observed value, so the manuscript
    # rounds its endpoints outward, not to nearest.
    ratios, wins = [], []
    for hw in ("ideal", "pedestal"):
        for nc in (8, 18):
            for key in ("test_nrmse", "traj_nrmse"):
                e = {r["system"]: r for r in rows
                     if r["model"] == f"elm0_{hw}_c{nc}"}
                tr = {r["system"]: r for r in rows
                      if r["model"] == f"fabric_{hw}_c{nc}"}
                com = [s for s in order if s in e and s in tr]
                assert com, f"no rows for elm0_{hw}_c{nc}"
                ratios.append(med([e[s][key] / max(tr[s][key], 1e-12)
                                   for s in com]))
                wins.append(sum(e[s][key] < tr[s][key] for s in com))
    out.append(("q1c control: no ratio below the stated 0.82",
                min(ratios) >= 0.82, True, "band"))
    out.append(("q1c control: no ratio above the stated 1.95",
                max(ratios) <= 1.95, True, "band"))
    out.append(("q1c control: wins within the stated 4-10 of 16",
                min(wins) >= 4 and max(wins) <= 10, True, "band"))
    # and the claim that matters: frozen is NOT an order of magnitude better
    # at matched readout, which is what would resurrect the retracted reading
    out.append(("q1c control: frozen not >2x better at matched readout",
                min(ratios) > 0.5, True, "band"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    rows, order = load()
    bad = 0
    for lab, got, exp, kind in checks(rows, order):
        if kind == "ratio":
            ok = abs(got - exp) <= TOL * abs(exp)
            shown = f"{got:8.2f} vs {exp:.2f}"
        elif kind == "count":
            ok = (got == exp) if COUNT_EXACT else True
            shown = f"{got:8d} vs {exp}"
        else:
            ok = got is exp
            shown = f"{'yes' if got else 'NO':>8s}"
        bad += not ok
        if a.verbose or not ok:
            print(f"{'ok  ' if ok else 'DRIFT'} {lab:52s} {shown}")
    if bad:
        print(f"\n{bad} value(s) drifted from the manuscript. Either the "
              f"manuscript or this guard is now wrong -- resolve before "
              f"submitting.")
        return 1
    print(f"all {len(checks(rows, order))} ELM claims match the manuscript")
    return 0


if __name__ == "__main__":
    sys.exit(main())
