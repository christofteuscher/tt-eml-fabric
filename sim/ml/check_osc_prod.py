"""Does a larger MLP, or more data, resolve sin(2 pi x1 x2) on [1,3]^3?

Response to Reviewer 1 (revision 1): reruns the perceptron baseline of
osc_prod with the same validation-based selection as run_mlp_fix.py, at the
matched budget and at about ten times the parameters, with 512 and 4096
training points.  Output: results/log_osc_prod_check.txt (about 15 min).

Run from this directory:  python3 check_osc_prod.py
"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import torch
from ml_common import run_mlp_val, synth_task
torch.set_num_threads(4)
t0 = time.time()
for n, P, iters in [(512, 426, 2000), (512, 4000, 4000), (4096, 426, 4000), (4096, 4000, 6000)]:
    r = run_mlp_val(*synth_task("osc_prod", n=n), P=P, iters=iters)
    print(f"n={n:5d} P={r['params']:5d} {r['hidden']} {r['act']} lr={r['lr']} "
          f"val {r['val']:.4f} test {r['test']:.4f} [{time.time()-t0:.0f}s]", flush=True)
