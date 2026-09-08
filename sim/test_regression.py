"""Scalar-path regression guard.

Fixed-seed re-runs of three cases that RESULTS.md / RESULTS_SCALING.md
already depend on (thermistor, photodiode_log, osc_k3), plus the
tree/fabric equivalence check. Prints a JSON blob of RMSEs so a run
before a change can be diffed bit-for-bit against a run after it.

    python3 test_regression.py            # print
    python3 test_regression.py --save f   # write JSON to f
    python3 test_regression.py --check f  # compare against f, exit 1 on drift
"""
import argparse
import json
import math

import torch

from eml_fabric_sim import (AnalogConfig, TrainConfig, AnalogEMLTree,
                            evaluate, train, make_data as make_data_scalar,
                            worst_case_config, PEDESTAL_SEGMENTED,
                            ATTEN_V_NOMINAL, SPAN_DECADES, SPAN_HI_UNITS)
from eml_fabric_topo import AnalogEMLFabric, FabricSpec
from run_scaling import make_data, PDK


def case_tree(target, depth, iters, seed, over):
    xt, tt, xv, tv, scale, unit = make_data(target)
    acfg = AnalogConfig(mismatch_seed=1000 + seed, **over)
    m = AnalogEMLTree(depth=depth, acfg=acfg, seed=seed)
    torch.manual_seed(seed)
    train(m, xt, tt, TrainConfig(iters=iters))
    r, _ = evaluate(m, xt, tt)
    return r * scale


def case_fabric(target, depth, iters, seed, over, topology="tree", width=4):
    xt, tt, xv, tv, scale, unit = make_data(target)
    acfg = AnalogConfig(mismatch_seed=1000 + seed, **over)
    m = AnalogEMLFabric(FabricSpec(topology, depth, width), acfg, seed=seed,
                        init_scheme="identity")
    m.init_readout_lstsq(xt, tt)
    torch.manual_seed(seed)
    train(m, xt, tt, TrainConfig(iters=iters))
    r, _ = evaluate(m, xt, tt)
    return r * scale


def case_photodiode(depth, iters, seed):
    xt, tt, xv, tv, scale, unit = make_data_scalar("photodiode_log")
    m = AnalogEMLTree(depth=depth, acfg=AnalogConfig(), seed=seed)
    torch.manual_seed(seed)
    train(m, xt, tt, TrainConfig(iters=iters))
    r, _ = evaluate(m, xt, tt)
    return r * scale


def case_equivalence(depth, over):
    """Layered 'tree' fabric must match AnalogEMLTree to ~0 ulp."""
    from test_topo import copy_tree_weights_into_fabric
    acfg = AnalogConfig(**over)
    tree = AnalogEMLTree(depth=depth, acfg=acfg, seed=3)
    fab = AnalogEMLFabric(FabricSpec("tree", depth), acfg, seed=3,
                          init_scheme="standard")
    copy_tree_weights_into_fabric(fab, tree)
    x = torch.linspace(0.3, 7.85, 64, dtype=torch.float64)
    a = tree(x, noisy=False)
    b = fab(x, noisy=False)
    return float((a - b).abs().max())


def program_product(acfg, n_vars=2):
    """Hand-program a 2-layer, width-2 DAG to compute x1 * x2 EXACTLY.

    leaf j :  u = -50 (exp ~ 2e-22),  v = x_{j+1}     -> out_j = -ln x_{j+1}
    root   :  u = -out_0 - out_1 = ln x1 + ln x2      -> exp(u) = x1 x2
              v = 1                                    -> ln v = 0

    This is the multiplication that motivates a log-domain fabric in the
    first place, so it is the right probe for both the multivariate
    plumbing (ideal config -> error ~ 1e-16) and for representability
    under the new non-idealities (no training involved).
    """
    spec = FabricSpec("dag", depth=2, width=2, n_vars=n_vars)
    m = AnalogEMLFabric(spec, acfg, seed=0, init_scheme="identity")
    with torch.no_grad():
        for p in list(m.alpha) + list(m.beta) + list(m.gamma):
            p.zero_()
        m.alpha[1][:, 0] = -50.0            # leaves: exp path off
        for j in range(2):
            m.beta[1][j, 1, j] = 1.0        # leaf j reads x_{j+1} on ln path
        m.alpha[0][:, 0] = 0.0
        m.alpha[0][:, 1] = 1.0              # root ln path: ln(1) = 0
        m.gamma[0][0, 0, 0] = -1.0          # root exp path: -out_0 - out_1
        m.gamma[0][0, 0, 1] = -1.0
        m.ro_w.zero_()
        m.ro_w[0] = 1.0
        m.ro_b.zero_()
    return m


def case_product(acfg, refit=False):
    """Relative RMS error of the hand-programmed x1*x2 on this chip.

    With refit=True the output stage (gain and offset only -- the one
    thing a digital back end can always trim) is re-solved by least
    squares first.  An effect that survives the refit has changed the
    SHAPE of the realised function; one that does not is a pure scale or
    offset and is absorbed by any retraining."""
    g = torch.Generator().manual_seed(5)
    x = torch.empty(256, 2, dtype=torch.float64).uniform_(1.0, 5.0,
                                                          generator=g)
    y = x[:, 0] * x[:, 1]
    m = program_product(acfg)
    p = torch.nan_to_num(m(x, noisy=False), nan=1e6)
    if refit:
        A = torch.stack([p, torch.ones_like(p)], dim=1)
        w = torch.linalg.lstsq(A, y.unsqueeze(1)).solution
        p = (A @ w)[:, 0]
    return float(torch.sqrt(torch.mean((p - y) ** 2))
                 / torch.sqrt(torch.mean(y ** 2)))


def collect():
    return {
        "tree_thermistor_beta_d3_ideal_s0_800":
            case_tree("thermistor_beta", 3, 800, 0, {}),
        "tree_thermistor_sh_d3_pdk_s0_800":
            case_tree("thermistor_sh", 3, 800, 0, PDK),
        "photodiode_log_d1_ideal_s0_600":
            case_photodiode(1, 600, 0),
        "fabric_osc_k3_d4_ideal_s0_800":
            case_fabric("osc_k3", 4, 800, 0, {}),
        "fabric_thermistor_sh_mesh_d4w8_pdk_s0_800":
            case_fabric("thermistor_sh", 4, 800, 0, PDK, "mesh", 8),
        "equiv_tree_fabric_d4_ideal_maxabs":
            case_equivalence(4, {}),
        "equiv_tree_fabric_d3_pdk_maxabs":
            case_equivalence(3, dict(PDK, mismatch_seed=7)),
        # --- new: multivariate + hardware effects, no training involved ---
        "mv_product_ideal_relrms":
            case_product(AnalogConfig()),
        "mv_product_pedestal_relrms":
            case_product(AnalogConfig(ln_pedestal=PEDESTAL_SEGMENTED)),
        "mv_product_atten_relrms":
            case_product(AnalogConfig(atten_v=ATTEN_V_NOMINAL)),
        "mv_product_span_relrms":
            case_product(AnalogConfig(span_decades=SPAN_DECADES,
                                      span_hi=SPAN_HI_UNITS)),
        "mv_product_span2dec_relrms":
            case_product(AnalogConfig(span_decades=2.0,
                                      span_hi=SPAN_HI_UNITS)),
        # NOTE: the two "silicon" keys below are pinned to the DOUBLE-COUNTED
        # (a)+(b)+(c) configuration, which is what the original
        # silicon_config() built.  They now call worst_case_config() so the
        # stored reference values stay bit-for-bit valid -- but they are a
        # pessimistic bound, NOT the silicon.  The physically correct config
        # (silicon_config() = pedestal only) is already pinned above as
        # mv_product_pedestal_*.
        "mv_product_silicon_relrms":
            case_product(worst_case_config()),
        # same, after the output stage is re-trimmed (gain + offset only):
        # separates "changed the shape" from "changed the scale"
        "mv_product_pedestal_refit_relrms":
            case_product(AnalogConfig(ln_pedestal=PEDESTAL_SEGMENTED), True),
        "mv_product_atten_refit_relrms":
            case_product(AnalogConfig(atten_v=ATTEN_V_NOMINAL), True),
        "mv_product_span2dec_refit_relrms":
            case_product(AnalogConfig(span_decades=2.0,
                                      span_hi=SPAN_HI_UNITS), True),
        "mv_product_silicon_refit_relrms":
            case_product(worst_case_config(), True),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save")
    ap.add_argument("--check")
    args = ap.parse_args()

    res = collect()
    for k, v in res.items():
        print(f"{k:44s} {v:.10e}")

    if args.save:
        with open(args.save, "w") as f:
            json.dump(res, f, indent=2)
        print(f"saved {args.save}")

    if args.check:
        with open(args.check) as f:
            ref = json.load(f)
        bad = 0
        for k, v in ref.items():
            got = res.get(k)
            if got is None:
                print(f"MISSING {k}")
                bad += 1
                continue
            d = abs(got - v)
            rel = d / max(abs(v), 1e-30)
            ok = d < 1e-12 or rel < 1e-9
            print(f"{'OK ' if ok else 'DRIFT'} {k:44s} "
                  f"ref={v:.10e} got={got:.10e} rel={rel:.2e}")
            bad += 0 if ok else 1
        print("REGRESSION: " + ("PASS" if bad == 0 else f"FAIL ({bad})"))
        raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
