# Wake-up and power-gating study, one post-layout EML cell (sky130A, tt, 27 C)

Behind Results section 2.5 and Table 5 of the revised paper (revision 1,
November 2026). It answers Reviewer 1's question whether tree levels could be
power-gated in sequence, with outputs held on sample-and-hold capacitors. Every
number is from SPICE; nothing has been fabricated. Unless a row says otherwise,
numbers are **post-layout** (`extract/pex_ship.inc`); "SCH" means the
schematic-level, LVS-matched `emlcell_b_sim12.inc` (identical to
`../emlcell_b_sim12.inc`).

## Running

```sh
export PDK_ROOT=$HOME/.ciel          # the directory that contains sky130A
ngspice -b base_pex.spice > runs/base_pex.log
python3 analyze.py runs/base_pex.dat 1e-6 0.264087   # 1 % (S): 401.9 ns, 40.44 pJ
```

`gen.py` regenerates the decks. The waveforms of the reported runs are in
`runs/*.dat.gz`; `analyze.py` reads them directly (numpy decompresses `.gz`).
A run takes about a minute.

## 0. The netlist

`extract/pex_ship.inc` is a re-extraction of the submitted cell layout
(`gds/` of this repository) with the same recipe as `../../extracted/`:
flattening, Magic 8.3.623 with `extract/extract_rc.tcl`, PDK 0536d02d, then the
repairs in `extract/mk_pex.py`.

* Raw extraction: **61 devices / 5779 R / 1317 C**, EXTRACT_FEEDBACK 0.
* After repair: **4984 R / 1316 C**, with 166.4 ohm of sub-ohm R merged and
  one negative capacitor (`C1263`, -4.87 fF) dropped. These counts match the
  extraction the paper's post-layout settling figures were first taken from,
  and section 1 reproduces those figures.
* The cell's 29.8686 uA / 98.566 uW is the **SCH** operating point at
  u = 0, v = 1 (sum of 12 leg currents), not the post-layout current at the
  402 ns operating point. The time constant of 45.9 ns is also SCH.

Harness: die context (no IOFF2/IOFF3), ideal 0.5 uA `IPB` into the harness diode `XPB`,
`out` clamped at 0.9 V, ve 0.55 V, vrefb 1.2 V. The cell's vdd is metered alone (`VAMC`), and the
reference diode separately (`VAMR`). Simulator settings are those of the other characterization decks in `../`:
`.options method=gear maxord=2 reltol=1e-5 abstol=1e-15 vntol=1e-9`, `tran 5n 40u`, no `uic`
(the run starts from the converged DC OP of the *off* state). The row count, 8016, matches the
record's 8017. ngspice-46.

## 1. Baseline reproduction (cell powered, input step)

| | record | this run |
|---|---|---|
| PEX 1 % settling, u -1.5 -> +1 | 402 ns | **401.9 ns** (band rel. step); 395.9 ns (rel. final) |
| PEX 0.1 % / 0.01 % | 497 / 642 ns | 501.5 / 645.0 ns (S); 498.6 / 636.2 ns (F) |
| PEX overshoot | 2.17 % | **2.17 %** |
| PEX I_vdd at u = -1.5 / +1 | 29.032 / 31.583 uA | **29.032 / 31.583 uA** |
| SCH 1 % / 0.1 % / 0.01 % (F) | 339 / 419 / 899 ns | 339.7 / 419.1 / 900.2 ns |
| SCH I_vdd at u = 0 | 29.8686 uA (leg sum) | 29.882 uA (whole pin, includes about 13 nA of well leakage) |
| PEX I_vdd at u = 0 | not on record | 29.833 uA = 98.45 uW |
| PEX io at u = +1 | 2.914 | 2.9139 |

**Reproduced.** The integrated supply energy over the 402 ns window (PEX, the actual
29.0 -> 31.6 uA trajectory) is **40.4 pJ**, against the paper's 39.62 pJ. The reverse step (u +1 -> -1.5) settles to 1 % (F) in
404.6 ns and costs 40.0 pJ.

## 2. Wake-up (PEX, input held at u, v = 1; t measured from the start of the gating edge; band relative to the final value)

| case (PEX unless SCH) | u | 1 % | 0.1 % | E to 1 % (integrated) | E to 0.1 % | Pstat x t(1 %) | peak I_vdd / peak output |
|---|---|---|---|---|---|---|---|
| powered, input step (baseline) | -1.5 -> +1 | 402 ns | 502 ns | **40.4 pJ** | 50.8 pJ | 41.9 | 31.6 uA / 1.5 uA |
| (a) bias gating, Iref 0 -> 0.5 uA, 10 ns edge | +1 | **3873 ns** | 4725 ns | **141.1 pJ** | 229.4 | 403.7 | 39 uA / 11 uA |
| (a) same | 0 | 3840 ns | 4694 ns | 443.8 pJ | 527.4 | 378.0 | **272 uA / 130 uA** for about 0.5 us |
| (a) same | -1.5 | 3577 ns | 4490 ns | 100.4 pJ | 186.8 | 342.6 | 29 uA / 1.5 uA |
| (a) 1 ns edge | +1 | 3869 ns | 4720 ns | 141.1 pJ | 229.4 | | edge-insensitive |
| (b) supply gating, pfet header W20/L0.5, gate 3.3 -> 0 in 10 ns, Iref gated with it | +1 | **3459 ns** | 4315 ns | **157.0 pJ** | 245.6 | 360.4 | 968 uA inrush (6 ns) / 35 uA |
| (b) same | 0 | 3423 ns | 4281 ns | 190.9 pJ | 274.8 | 336.9 | 968 uA / 45 uA |
| (b) same | -1.5 | 3145 ns | 4078 ns | **967.6 pJ** | 1055.8 | 301.3 | 1011 uA; 55-300 uA for about 1.2 us / 190 uA |
| (b) 1 ns edge | +1 | 3455 ns | 4311 ns | 157.0 pJ | 245.6 | | |
| (b') ideal VDD source 0 -> 3.3 V, 10 ns (see caveat 3) | +1 | 3082 ns | 3934 ns | 156.4 pJ | 244.6 | | back-feed -44 uA while off |
| IDEAL fast-start: pbias forced to 2.059 V for 20 ns, then released | +1 | **657 ns** | 1235 ns | **67.0 pJ** | 126.9 | 68.5 | 5.1 mA for 1 ns / 190 uA |
| same | 0 | 723 ns | 811 ns | 315.6 pJ | 324.2 | 71.2 | |
| same | -1.5 | 893 ns | 1013 ns | 85.1 pJ | 96.6 | 85.6 | |
| SCH, (a) bias gating | +1 | 3532 ns | 4325 ns | 128.5 pJ | 210.5 | | |
| SCH, (b) header | +1 | 3427 ns | 4220 ns | 132.0 pJ | 214.0 | | |

The "E (integrated)" column is the energy actually drawn from the 3.3 V rail by the cell. It is the
energy spent if the cell stays on from the gating edge until it settles. "Pstat x t" is what the same
time would cost at the settled power. The cell draws less than Pstat during the dead time of the
wake-up, so "Pstat x t" overstates the cost. The harness reference leg adds a further 2.3 pJ to each
wake-up, against 0.66 pJ for the powered baseline.

**Mechanism.** About 2.3 us of the wake-up is `pbias` slewing from about 3.3 V down to 2.06 V. The only
current available to slew it is about 0.44 uA from the reference, which implies about 0.77 pF of
pfet-gate load. The remaining time (about 1-1.5 us) is the servos and the 2 pF Miller capacitors
recovering from their discharged state. Many runs also show a large start-up excursion: the output
mirror conducts tens to hundreds of uA before the servos take hold. That excursion depends on the
operating point (u = 0 for bias gating, u = -1.5 for header gating) and drives most of the energy spread.
**It would also inject a large current into whatever the output feeds.** Checks: a 1 ns tmax rerun
reproduces the result to 0.1 % (`chk_wh10_pex_um15`), and so does a trap rerun (`chk_wb_pex_u0`).

## 3. Seven-cell, depth-3 tree (4 + 2 + 1 cells, 6 links). `tree.py`, `runs/tree.log`

The paper's 420.8 pJ is reproduced exactly: P(7) = 96.95x7 + 85.64x6 + 2.09 = 1194.58 uW, multiplied by
T7 = 1.19 x (166 + 2 x 65) = 352.2 ns. Of this, cells contribute 239.0 pJ, links 181.0 pJ and div 0.7 pJ.
Every one of these inputs is the SCH chain law and the SCH chain latency, inflated by the 1.19 PEX factor.
Note that **T7 (352 ns) is shorter than one 402 ns cell window**. The chain's first stage, at 166 ns, is
the ln port; the 402 ns window is the exp port.

| scheme | tree E (cells only) | + links | latency |
|---|---|---|---|
| (i) spatial, all on for T7 (paper) | 239.0 pJ | **420.8 pJ** | 352 ns |
| (ii-A) ideal level-gated, 39.62 pJ / 402 ns per cell | 277.3 | 487.3 | 1206 ns |
| (ii-B) ideal level-gated, chain-consistent window 1.19 x 166 = 198 ns | 134.1 | **235.6** | 593 ns |
| (ii) reuse one 4-cell layer for 3 logical levels, all on | 475.4 | n/a | 1206 ns |
| (iii) bias-gated, u = +1 (range over u) | 988 (702-3107) | **1736** (1234-5459) | 11.6 us |
| (iii) header-gated, u = +1 (worst u) | 1099 (6773) | 1931 (11901) | 10.4 us |
| (iii) ideal fast-start, u = +1 (worst u) | 469 (2209) | 824 (3881) | 2.0 us |

Assumptions:
* The levels are strictly sequential: a level is gated on only after the previous level has settled.
* Link (glue + gamma MDAC) wake-up was **not simulated**. Links are assumed to wake like a cell,
  scaled by 85.64 / 96.95.
* S/H costs and mux/switch costs are excluded.
* The tree is treated as the chain law, as the paper does.

## 4. Sample-and-hold estimate (`tree.py`, `sh_leak.spice`)

* **kT/C does not bind** for a voltage-mode hold at a 1 V full scale: below 0.1 fF for 6 bits.
* If the held quantity is a subthreshold mirror gate voltage (current mode; dI/I = dV / 33.6 mV),
  the requirement for 6 bits is 60 fF at full-scale current and **6 pF at 1/10 FS**. For 4 bits the same
  two figures are 3.8 fF and 0.38 pF.
* Switch off-leakage is 1.0-2.5 pA at 1 V, from SCH devices only. With 60 fF that gives a droop of
  0.02-0.05 mV over 3 x 402 ns and 0.2-0.5 mV over 3 x 3.9 us. The allowed droop at 6 bits FS is 0.26 mV,
  so droop is marginal under gating latency and fine without it.
* **A buffer / V-to-I is required.** The next cell's `nu` / `nv` are current inputs, so a held voltage cannot drive them.
  That V-to-I is an active block. Its power was not simulated; the output mirror's 3.5 uW is a
  reasonable lower bound.

## Caveats

1. The netlist is a faithful rebuild, not the original file. Every documented count and DC/transient figure matches.
2. The bias reference is an ideal 0.5 uA source with the harness diode. The real `bias_core` has its own
   start-up, which would add to the wake-up figures, not subtract from them.
3. In (b') the hard 0 V source sinks a back-feed current from the clamped `out`, ve and vrefb rails
   while "off". (b), the pfet header, avoids this, which is why (b) is the reported case.
4. The fast-start row uses an ideal forced `pbias`. It is a lower bound, not a design.
5. Only u was varied (v = 1). The start-up excursion is operating-point dependent, and the worst case may lie elsewhere.
6. Only tt / 27 C was run.

## Files

* `extract/` holds `mk_pex.py`, the raw `emlcell_b.spice`, `pex_ship.inc`, `pex_ctrl.inc` and `magic.log`.
* `gen.py` is the deck generator. `analyze.py` computes settling and energy (`wrdata` layout t,y,t,y...).
* `pb.py` and `spike.py` are probes.
* `base_*.spice` are the baseline decks. `wb*` is bias gating, `wh*` the header, `ws*` and `wsr*` the
  ideal VDD source, and `wbf*` fast-start. `chk_*` are the numerical checks and `dc_*` the DC gate.
* `runs/*.dat.gz` and `runs/*.log` hold the waveforms and logs.
