"""Fairness check: is the extended cell's deficit an INIT artifact?

w_share=0 starts the extended fabric bit-close to the standard one (w port
present but carrying ~0 gain), so any remaining loss is optimisation, not
representation.  Also runs an UNWEIGHTED w port (gamma_w frozen at +-1/F,
the 'genuinely free' hardware variant: a bare mirror leg, no gamma MDAC).
"""
import json
import os
import statistics
import sys
import time

import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from eml_fabric_sim import AnalogConfig, TrainConfig, train, evaluate, \
    PEDESTAL_SEGMENTED                                              # noqa
from eml_fabric_topo import FabricSpec, AnalogEMLFabric             # noqa
from eml_fabric_ext import AnalogEMLFabricW                         # noqa
import run_ext as R                                                 # noqa

torch.set_num_threads(2)
ITERS, SEEDS = 2500, 4


def one(target, hw, depth, width, seed, kind):
    xt, tt, xv, tv, scale, unit, nv = R.get_data(target)
    acfg = AnalogConfig() if hw == "ideal" else \
        AnalogConfig(ln_pedestal=PEDESTAL_SEGMENTED)
    spec = FabricSpec(topology="mesh", depth=depth, width=width,
                      window=min(3, width), n_vars=nv)
    if kind == "std":
        m = AnalogEMLFabric(spec, acfg, seed=seed, init_scheme="identity",
                            var_mode="dense")
    else:
        ws = {"ext0": 1e-6, "ext15": 0.15, "ext33": 1.0 / 3.0,
              "extfree": 1.0 / 3.0}[kind]
        m = AnalogEMLFabricW(spec, acfg, seed=seed, w_share=ws,
                             init_scheme="identity", var_mode="dense")
        if kind == "extfree":
            # unweighted port: freeze gamma_w at its init (no gamma MDAC)
            for l in range(m.depth):
                g = m.gamma[l]
                mask = torch.ones_like(g)
                mask[:, 2] = 0.0
                g.register_hook(lambda gr, mk=mask: gr * mk)
    m.init_readout_lstsq(xt, tt)
    train(m, xt, tt, TrainConfig(iters=ITERS, eval_every=100))
    te, _ = evaluate(m, xv, tv)
    return te * scale, m.n_params()


def main():
    targets = sys.argv[1].split(",")
    out = sys.argv[2]
    rows, t0 = [], time.time()
    for target in targets:
        for hw in ("ideal", "pedestal"):
            for depth, width in [(2, 6), (3, 4)]:
                for kind in ("std", "ext0", "ext15", "ext33", "extfree"):
                    r = [one(target, hw, depth, width, s, kind)
                         for s in range(SEEDS)]
                    te = [a for a, _ in r]
                    rows.append(dict(target=target, hw=hw, depth=depth,
                                     width=width, kind=kind,
                                     med=statistics.median(te), best=min(te),
                                     params=r[0][1]))
                    x = rows[-1]
                    print(f"{target:16s} {hw:9s} d={depth} {kind:8s} "
                          f"med={x['med']:.4g} best={x['best']:.4g} "
                          f"[{time.time()-t0:.0f}s]", flush=True)
    json.dump(rows, open(out, "w"), indent=1)
    print("DONE", out)


if __name__ == "__main__":
    main()
