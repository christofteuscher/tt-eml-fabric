"""
The three hardware-derived non-idealities, one knob at a time.

  (a) ln_pedestal   ln(v + s), s = 2.547 units (segmented basis)
  (b) atten_v       v-port per-hop gain 0.2551
  (c) span_decades  8.372 decades of current, 5.80e-6 .. 1366 units

(b) is DERIVED from (a) -- lambda_v = 1.094/(1.741+2.547) = 0.2551 -- so
the rows that switch both on ("ab_*", "abc_*") are pessimistic BOUNDS, not
the die.  a_pedestal is the physical silicon row (= silicon_config()).

Each is measured in two regimes, because they behave completely
differently in the two:

  IN-SITU   train through the non-ideal forward model (the fabric's
            selling point).  A non-ideality that the optimiser can absorb
            shows up as ~no change here.
  TRANSFER  train on an ideal chip, then program the weights onto the
            non-ideal one.  This is where an "absorbable" effect is not
            absorbable at all.

Also measures the realised per-hop v-port gain lambda_v and how close the
internal currents come to the edges of the device span, so the claim
"effect X is/is not reachable" is backed by a number rather than an
assertion.

Usage:
  python3 run_nonideal.py --pilot
  python3 run_nonideal.py
"""
import argparse
import json
import math
import time
from pathlib import Path

import torch

from eml_fabric_sim import (AnalogConfig, TrainConfig, evaluate, train,
                            PEDESTAL_SEGMENTED, PEDESTAL_LUMPED,
                            ATTEN_V_NOMINAL, ATTEN_V_SECANT, LN_SLOPE_SEGMENTED,
                            SPAN_DECADES, SPAN_HI_UNITS)
from eml_fabric_topo import AnalogEMLFabric, FabricSpec
from eml_feynman import make_data_mv, n_vars
from run_scaling import make_data, PDK, median

PED = dict(ln_pedestal=PEDESTAL_SEGMENTED)
ATT = dict(atten_v=ATTEN_V_NOMINAL)
SPAN = dict(span_decades=SPAN_DECADES, span_hi=SPAN_HI_UNITS)
# This sweep is the one place where (a)+(b) together is INTENTIONAL: the
# point is to bound the loss, not to model the die.  lambda_v = 0.2551 is
# derived from the pedestal (see eml_fabric_sim.silicon_config), so every
# "ab_*"/"abc_*" row below double-counts the v-port loss by construction
# and is an upper bound.  a_pedestal is the physically-derived row.
DBL = dict(allow_double_count=True)

CONFIGS = [
    ("ideal", {}),
    ("a_pedestal", PED),                        # <- the silicon (physical)
    ("b_atten", ATT),
    ("c_span", SPAN),
    ("c_span_2dec", dict(span_decades=2.0, span_hi=SPAN_HI_UNITS)),
    ("ab_ped_atten", {**PED, **ATT, **DBL}),            # bound, not silicon
    ("abc_silicon", {**PED, **ATT, **SPAN, **DBL}),     # bound, not silicon
    ("abc_silicon_lumped", {**PED, **ATT, **SPAN, **DBL,
                            "ln_pedestal": PEDESTAL_LUMPED}),
    ("abc_silicon_secant", {**PED, **SPAN, **DBL,
                            "atten_v": ATTEN_V_SECANT}),
    ("pdk", PDK),
    ("pdk_abc_silicon", {**PDK, **PED, **ATT, **SPAN, **DBL}),
]


def mv_data(target):
    if target.startswith("I") and "." in target:
        xt, tt, xv, tv, sc, unit = make_data_mv(target)
        return xt, tt, xv, tv, 1.0, "nrmse", n_vars(target)
    xt, tt, xv, tv, sc, unit = make_data(target)
    return xt, tt, xv, tv, sc, unit, 1


def make_model(target, nv, acfg, seed, spec_kw):
    return AnalogEMLFabric(FabricSpec(n_vars=nv, **spec_kw), acfg, seed=seed)


@torch.no_grad()
def span_probe(model, x):
    """Decades by which the internal currents overshoot / undershoot the
    device span.  Positive = the signal is outside the window."""
    model._probe = []
    model(x, noisy=False)
    p, model._probe = model._probe, None
    if not p:
        return 0.0, 0.0
    lo_seen = min(a for a, _ in p)
    hi_seen = max(b for _, b in p)
    lo = model.acfg.span_lo() or 5.80e-6
    hi = model.acfg.span_hi_eff() if model.acfg.span_decades > 0 \
        else SPAN_HI_UNITS
    under = max(0.0, math.log10(lo / max(lo_seen, 1e-300)))
    over = max(0.0, math.log10(max(hi_seen, 1e-300) / hi))
    return over, under


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--iters", type=int, default=2500)
    ap.add_argument("--targets", nargs="+",
                    default=["thermistor_sh", "osc_k3", "I.12.1"])
    ap.add_argument("--out", default="results/nonideal.json")
    args = ap.parse_args()

    seeds = 1 if args.pilot else args.seeds
    iters = 300 if args.pilot else args.iters
    cfgs = CONFIGS[:4] if args.pilot else CONFIGS
    spec_kw = dict(topology="mesh", depth=4, width=8, window=3)
    out = {"spec": spec_kw, "iters": iters, "seeds": seeds, "rows": [],
           "lambda_v": {}}
    t0 = time.time()

    # -- realised per-hop v-port gain, k * |d out / d v| ------------------
    print("=== realised lambda_v (segmented slope k = 1.094 folded in) ===")
    for name, over in CONFIGS:
        acfg = AnalogConfig(**over)
        m = AnalogEMLFabric(FabricSpec("tree", 2), acfg, seed=0)
        g = {v: LN_SLOPE_SEGMENTED * m.measured_hop_gain_v(v)
             for v in (1.0, 1.741)}
        out["lambda_v"][name] = g
        print(f"{name:20s} v0=1.0 {g[1.0]:.4f}   v0=1.741 {g[1.741]:.4f}")

    print("\n=== in-situ vs factory transfer, one knob at a time ===",
          flush=True)
    print(f"{'target':12s} {'config':20s} {'insitu med':>11} "
          f"{'insitu best':>11} {'transfer med':>13} {'over/under dec':>15}",
          flush=True)
    for target in args.targets:
        xt, tt, xv, tv, scale, unit, nv = mv_data(target)
        # ideal reference weights, per seed, for the transfer arm
        ideal = []
        for s in range(seeds):
            acfg = AnalogConfig(mismatch_seed=1000 + s)
            m = make_model(target, nv, acfg, s, spec_kw)
            m.init_readout_lstsq(xt, tt)
            torch.manual_seed(s)
            train(m, xt, tt, TrainConfig(iters=iters))
            ideal.append({k: v.clone() for k, v in m.state_dict().items()})

        for name, over in cfgs:
            insitu, transfer, spans = [], [], []
            for s in range(seeds):
                acfg = AnalogConfig(mismatch_seed=1000 + s, **over)
                m = make_model(target, nv, acfg, s, spec_kw)
                m.init_readout_lstsq(xt, tt)
                torch.manual_seed(s)
                train(m, xt, tt, TrainConfig(iters=iters))
                r, _ = evaluate(m, xt, tt)
                insitu.append(r * scale)
                spans.append(span_probe(m, xt))
                # transfer: ideal-trained weights on this chip
                m2 = make_model(target, nv, acfg, s, spec_kw)
                m2.load_state_dict(ideal[s])
                r2, _ = evaluate(m2, xt, tt)
                transfer.append(min(r2 * scale, 1e6))
                out["rows"].append(dict(
                    target=target, config=name, seed=s, unit=unit,
                    insitu=r * scale, transfer=min(r2 * scale, 1e6),
                    over_dec=spans[-1][0], under_dec=spans[-1][1]))
            ov = max(a for a, _ in spans)
            un = max(b for _, b in spans)
            print(f"{target:12s} {name:20s} {median(insitu):11.4f} "
                  f"{min(insitu):11.4f} {median(transfer):13.4f} "
                  f"{ov:7.2f}/{un:6.2f}  [{time.time()-t0:5.0f}s]",
                  flush=True)
            Path(args.out).parent.mkdir(exist_ok=True)
            with open(args.out, "w") as f:
                json.dump(out, f, indent=2)

    print(f"\nSaved {args.out} ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
