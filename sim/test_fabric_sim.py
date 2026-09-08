"""Sanity checks for the analog EML fabric simulator. Run directly:
    python3 test_fabric_sim.py
"""
import math
import torch

from eml_fabric_sim import (
    AnalogConfig, AnalogEMLTree, TrainConfig, thermistor_beta, make_data,
    REAL_DTYPE,
)


def test_ideal_cell_is_exact_eml():
    """With default (ideal) config a depth-1 tree computes
    readout-scaled exp(u) - ln(v) for the programmed affine inputs."""
    m = AnalogEMLTree(depth=1, acfg=AnalogConfig(), seed=0)
    # u = 0.3 + 0.5x, v = 2.0 + 0.25x
    m.program([[[0.3, 0.5, 0.0], [2.0, 0.25, 0.0]]], [1.0, 0.0])
    x = torch.linspace(0.1, 5.0, 50, dtype=REAL_DTYPE)
    got = m(x, noisy=False)
    want = torch.exp(0.3 + 0.5 * x) - torch.log(2.0 + 0.25 * x)
    err = (got - want).abs().max().item()
    assert err < 1e-14, f"ideal cell mismatch: {err}"
    print(f"PASS ideal cell == exact eml (max err {err:.2e})")


def program_beta_model(model, B=3435.0, T25=298.15):
    """Program the 3-cell chain T = 1/(1/T25 + ln(x)/B) onto a depth-3 tree.

    heap layout: root=0, children(0)=1,2; children(1)=3,4.
      cell4 (leaf level): exp path off (alpha=-30), ln path = x
                          -> out4 = -ln(x)          (+ exp(-30) ~ 1e-13)
      cell1: exp path off; ln input = a + gamma*out4 with a=1/T25,
             gamma=-1/B  -> out1 = -ln(1/T25 + ln(x)/B)
      cell0: exp input = out1 -> exp(-ln(w)) = 1/w; ln input = 1 -> 0
      readout: T/100
    """
    n = model.n_cells
    w = torch.zeros(n, 2, 3, dtype=REAL_DTYPE)
    w[:, 0, 0] = -30.0          # default: all exp paths off
    w[:, 1, 0] = 1.0            # default: all ln inputs = 1 -> ln = 0
    w[4, 1] = torch.tensor([0.0, 1.0, 0.0])          # v = x
    w[1, 1] = torch.tensor([1.0 / T25, 0.0, -1.0 / B])
    w[0, 0] = torch.tensor([0.0, 0.0, 1.0])          # u = out1
    model.program(w, [0.01, 0.0])
    return model


def test_programmed_thermistor_exact():
    m = AnalogEMLTree(depth=3, acfg=AnalogConfig(), seed=0)
    program_beta_model(m)
    x = torch.exp(torch.linspace(math.log(0.145), math.log(24.8), 200,
                                 dtype=REAL_DTYPE))
    got = m(x, noisy=False)
    want = thermistor_beta(x)
    err_K = 100.0 * (got - want).abs().max().item()
    # residual comes only from the exp(-30) path-off leakage
    assert err_K < 1e-3, f"programmed beta-model error {err_K} K"
    print(f"PASS programmed beta-model matches thermistor (max err {err_K:.2e} K)")


def test_readback():
    m = AnalogEMLTree(depth=3, acfg=AnalogConfig(), seed=0)
    program_beta_model(m)
    expr = m.readback(chop=1e-4, simplify=True)
    s = str(expr)
    assert "log(x)" in s or "log" in s, f"readback lost the log: {s}"
    print(f"PASS readback: T*0.01 = {s}")


def test_quantization_ste():
    cfg = AnalogConfig(weight_bits=6)
    m = AnalogEMLTree(depth=2, acfg=cfg, seed=1)
    x = torch.linspace(0.5, 2.0, 20, dtype=REAL_DTYPE)
    pred = m(x, noisy=False)
    loss = pred.pow(2).mean()
    loss.backward()
    g = m.weights.grad
    assert g is not None and torch.isfinite(g).all() and g.abs().sum() > 0, \
        "STE gradient did not flow through quantizer"
    step = 2 * cfg.weight_range / (2 ** 6 - 1)
    wq = m._quant(m.weights).detach()
    resid = (wq / step - torch.round(wq / step)).abs().max().item()
    assert resid < 1e-9, f"quantized weights off-grid: {resid}"
    print(f"PASS quantization on-grid (step {step:.3f}) with STE gradients")


def test_saturation_and_floor():
    cfg = AnalogConfig(sat=10.0, ln_floor=1e-3, rail_leak=0.0)
    m = AnalogEMLTree(depth=1, acfg=cfg, seed=0)
    m.program([[[5.0, 0.0, 0.0], [-1.0, 0.0, 0.0]]], [1.0, 0.0])  # exp(5)=148, ln(-1) invalid
    out = m(torch.zeros(3, dtype=REAL_DTYPE), noisy=False)
    assert out.max().item() <= 10.0 + 1e-12, "saturation clamp failed"
    assert torch.isfinite(out).all(), "ln floor failed on negative input"
    print(f"PASS saturation rails at {out.max().item():.1f}, negative ln input railed finite")


def test_short_training_converges():
    torch.manual_seed(0)
    cfg = AnalogConfig()
    m = AnalogEMLTree(depth=2, acfg=cfg, seed=7)
    xt, tt, _, _, scale, unit = make_data("photodiode_log", seed=99)
    r = __import__("eml_fabric_sim").train(
        m, xt, tt, TrainConfig(iters=600, eval_every=50))
    assert r * scale < 0.5, f"photodiode short-train RMSE too high: {r*scale} {unit}"
    print(f"PASS short training: photodiode depth-2 RMSE {r*scale:.3f} {unit}")


if __name__ == "__main__":
    test_ideal_cell_is_exact_eml()
    test_programmed_thermistor_exact()
    test_readback()
    test_quantization_ste()
    test_saturation_and_floor()
    test_short_training_converges()
    print("\nAll sanity checks passed.")
