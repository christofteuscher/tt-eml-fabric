"""Equivalence, correctness and speed checks for the layered fabric core."""
import math
import time

import torch

from eml_fabric_sim import AnalogConfig, AnalogEMLTree, make_data
from eml_fabric_topo import AnalogEMLFabric, FabricSpec


def copy_tree_weights_into_fabric(fab, tree):
    """Map heap-indexed AnalogEMLTree weights onto the layered fabric."""
    with torch.no_grad():
        for l in range(fab.depth):
            base = 2 ** l - 1
            n_l = fab.sizes[l]
            for j in range(n_l):
                i = base + j
                fab.alpha[l][j, 0] = tree.weights[i, 0, 0]
                fab.alpha[l][j, 1] = tree.weights[i, 1, 0]
                fab.beta[l][j, 0] = tree.weights[i, 0, 1]
                fab.beta[l][j, 1] = tree.weights[i, 1, 1]
                if l < fab.depth - 1:
                    fab.gamma[l][j, 0, 0] = tree.weights[i, 0, 2]
                    fab.gamma[l][j, 1, 0] = tree.weights[i, 1, 2]
        fab.ro_w[0] = tree.readout[0]
        fab.ro_b[0] = tree.readout[1]
        # same chip instance
        for l in range(fab.depth):
            base = 2 ** l - 1
            n_l = fab.sizes[l]
            sl = slice(base, base + n_l)
            getattr(fab, f"mm_exp_gain_{l}").copy_(tree.mm_exp_gain[sl])
            getattr(fab, f"mm_ln_gain_{l}").copy_(tree.mm_ln_gain[sl])
            getattr(fab, f"mm_exp_off_{l}").copy_(tree.mm_exp_off[sl])
            getattr(fab, f"mm_ln_off_{l}").copy_(tree.mm_ln_off[sl])


def test_tree_equivalence():
    """Layered 'tree' must be bit-comparable to the original AnalogEMLTree."""
    x = torch.linspace(0.3, 7.8, 64, dtype=torch.float64)
    for depth in (1, 2, 3, 4, 5):
        for acfg in (AnalogConfig(),
                     AnalogConfig(mismatch_gain_std=0.03,
                                  mismatch_offset_std=0.01,
                                  mismatch_seed=7, sat=30.0, weight_bits=8)):
            tree = AnalogEMLTree(depth=depth, acfg=acfg, seed=3)
            fab = AnalogEMLFabric(FabricSpec("tree", depth), acfg, seed=3,
                                  init_scheme="standard")
            copy_tree_weights_into_fabric(fab, tree)
            a = tree(x, noisy=False)
            b = fab(x, noisy=False)
            err = float((a - b).abs().max())
            assert err < 1e-10, f"depth {depth}: max abs diff {err:.3e}"
    print("PASS  tree equivalence vs AnalogEMLTree (depths 1-5, ideal + noisy cfg)")


def test_ideal_cell_is_exact_eml():
    """With defaults the cell must be exact real-domain exp(u) - ln(v)."""
    spec = FabricSpec("tree", 1)
    fab = AnalogEMLFabric(spec, AnalogConfig(), seed=0, init_scheme="standard")
    x = torch.linspace(0.5, 3.0, 32, dtype=torch.float64)
    with torch.no_grad():
        u = fab.alpha[0][0, 0] + fab.beta[0][0, 0] * x
        v = fab.alpha[0][0, 1] + fab.beta[0][0, 1] * x
        want = fab.ro_w[0] * (torch.exp(u) - torch.log(v)) + fab.ro_b[0]
        got = fab(x, noisy=False)
    err = float((want - got).abs().max())
    assert err < 1e-12, err
    print(f"PASS  ideal cell == exp(u) - ln(v)   (max abs diff {err:.2e})")


def test_identity_init_scaling():
    """Near-identity init must keep per-layer RMS bounded as depth grows."""
    x = torch.linspace(0.3, 7.8, 64, dtype=torch.float64)
    print("\n  per-layer output RMS at init (layer 0 = output):")
    print(f"  {'depth':>6} {'scheme':>9} {'RMS L0':>10} {'RMS Lmid':>10} "
          f"{'RMS Ldeep':>10}")
    for depth in (3, 5, 7, 10):
        for scheme in ("standard", "identity"):
            fab = AnalogEMLFabric(FabricSpec("tree", depth), AnalogConfig(),
                                  seed=1, init_scheme=scheme)
            s = fab.layer_stats(x)
            print(f"  {depth:6d} {scheme:>9} {s[0]:10.3e} "
                  f"{s[depth // 2]:10.3e} {s[depth - 1]:10.3e}")
            if scheme == "identity":
                assert s[0] < 1e3, f"identity init exploded at depth {depth}"
    print("PASS  identity init stays bounded to depth 10")


def test_topologies_run():
    x = torch.linspace(0.3, 7.8, 32, dtype=torch.float64)
    print("\n  topology shapes:")
    for spec in (FabricSpec("tree", 6),
                 FabricSpec("dag", 6, width=8),
                 FabricSpec("mesh", 6, width=8, window=3)):
        fab = AnalogEMLFabric(spec, AnalogConfig(), seed=0)
        y = fab(x, noisy=False)
        assert y.shape == x.shape
        assert torch.isfinite(y).all()
        print(f"  {spec.topology:5s} depth {spec.depth} "
              f"cells {fab.n_cells:5d} params {fab.n_params():6d} "
              f"out RMS {float(y.pow(2).mean().sqrt()):.3e}")
    print("PASS  all three topologies produce finite output")


def bench():
    print("\n  wall-clock, batch 256, forward+backward, float64:")
    x = torch.linspace(0.3, 7.8, 256, dtype=torch.float64)
    t = torch.zeros_like(x)
    for spec in (FabricSpec("tree", 3), FabricSpec("tree", 6),
                 FabricSpec("tree", 8), FabricSpec("tree", 10),
                 FabricSpec("dag", 10, width=16),
                 FabricSpec("mesh", 10, width=16)):
        fab = AnalogEMLFabric(spec, AnalogConfig(), seed=0)
        opt = torch.optim.Adam(fab.parameters(), lr=1e-3)
        for _ in range(3):                      # warm up
            opt.zero_grad(); ((fab(x) - t) ** 2).mean().backward(); opt.step()
        n = 20
        t0 = time.time()
        for _ in range(n):
            opt.zero_grad(); ((fab(x) - t) ** 2).mean().backward(); opt.step()
        dt = (time.time() - t0) / n
        print(f"  {spec.topology:5s} depth {spec.depth:2d} "
              f"cells {fab.n_cells:5d}: {dt*1e3:8.2f} ms/iter "
              f"-> {dt*3000:7.1f} s per 3000-iter run")

    # legacy comparison
    old = AnalogEMLTree(depth=8, acfg=AnalogConfig(), seed=0)
    opt = torch.optim.Adam(old.parameters(), lr=1e-3)
    t0 = time.time()
    for _ in range(3):
        opt.zero_grad(); ((old(x) - t) ** 2).mean().backward(); opt.step()
    dt = (time.time() - t0) / 3
    print(f"  LEGACY AnalogEMLTree depth  8 cells   255: {dt*1e3:8.2f} ms/iter "
          f"-> {dt*3000:7.1f} s per 3000-iter run")


if __name__ == "__main__":
    torch.manual_seed(0)
    test_ideal_cell_is_exact_eml()
    test_tree_equivalence()
    test_topologies_run()
    test_identity_init_scaling()
    bench()
