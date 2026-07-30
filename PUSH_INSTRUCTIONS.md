# Pushing EML Fabric to Tiny Tapeout — instructions

Template: https://github.com/TinyTapeout/ttsky-analog-template

There are **two milestones**, deliberately separate. Do #1 now (cheap, gets
CI running). Do #2 only when the layout is finished (see "Blockers" at the
bottom — the analog GDS is not yet in the submission).

---

## Part A — things only YOU can do (GitHub account + auth)

### A1. Create the repo from the template
1. Open https://github.com/TinyTapeout/ttsky-analog-template
2. Click **Use this template → Create a new repository**
3. Owner: your account. Name: `tt-eml-fabric` (or anything unique).
   Visibility: **Public** (TT requires public for the shuttle).
4. Do **not** initialise with anything extra — the template brings its own
   files.
5. Copy the new repo's URL, e.g. `https://github.com/<you>/tt-eml-fabric`.

### A2. Give me push access — pick ONE
- **Option P (you push):** after I stage everything, run this in the chat
  with the `!` prefix so your credentials authenticate:
  `! git -C /Users/cteusche/data/projects/eml/code/silicon/tt_submission push -u origin main`
- **Option G (gh once):** `brew install gh && gh auth login` — then I can
  push directly from now on.

### A3. (At final submission only) the voucher
Enter the voucher + the repo URL on the Tiny Tapeout submission page when
you actually submit. Nothing in this repo touches it.

---

## Part B — what I do once you hand me the URL

Our work currently lives in a local repo (`silicon/tt_submission`) that was
NOT made from this template, so it lacks the template's `gds`/`docs` GitHub
Actions. I will:

1. Add the template repo as a remote.
2. Reconcile onto the template: keep the template's `.github/workflows/`
   (the gds + docs Actions), and overlay OUR content —
   - `info.yaml`               (pinout, tiles=2x2, analog_pins=3, uses_vapwr)
   - `docs/info.md`            (the datasheet, already written)
   - `src/tt_um_teuscher_eml_fabric.v` (the wrapper: 4 level shifters + macro)
   - `src/cfgdig.v`            (config-chain RTL)
   - `openlane/cfgdig/`        (the LibreLane recipe — our extra CI job)
3. **Fill `src/project.v`** — TT requires a blackbox stub of the top module
   (`tt_um_teuscher_eml_fabric`) with the exact TT pin list. The current
   `project.v` was the dead `tt_um_example` template and I deleted it; I'll
   regenerate a correct blackbox.
4. Commit. Then either you push (Option P) or I do (Option G).

CI then runs and hardens `cfgdig` on clean Ubuntu — independent proof of the
12-run hvl config recipe I validated only in local Docker.

---

## Part C — what MUST be true before the FINAL submit (not yet done)

TT analog submission requires, per https://tinytapeout.com/specs/analog/ :

| requirement | path | status |
|---|---|---|
| analog GDS | `gds/tt_um_teuscher_eml_fabric.gds` | **MISSING** — our GDS is `silicon/layout/toplevel_routed.gds`, not yet copied in or renamed to the tt_um cell |
| analog LEF | `lef/tt_um_teuscher_eml_fabric.lef` | **MISSING** — must be generated (pin locations + outline) |
| top cell name | must be `tt_um_teuscher_eml_fabric` | our top cell is `eml_fabric_top` — needs renaming in the export |
| `info.yaml` | pinout etc. | DONE |
| `docs/info.md` | datasheet | DONE |
| `src/project.v` | blackbox stub | to fill (Part B step 3) |

### Blockers on the GDS itself (design, not GitHub)
- **The layout is 71/76 routed** — 5 nets still open (`iref`, `sum_Bv`,
  `moh6/7`, `mohb6`). Two touch analog function.
- **The cfgdig swap** (LibreLane macro, closes the 7 decode opens) is
  verified as a block (docker15: DRC 0, LVS MATCH) and a top-level pipeline
  run was in progress at the time of writing — not yet confirmed clean.
- **Top-level LVS has never been run on the assembled chip.** Every serious
  bug this project hit was invisible until a connectivity check ran; the
  assembly's is the one still outstanding.
- The GDS→submission mechanism (copy, rename top cell to `tt_um_...`,
  generate LEF) does not exist yet — it's a script I still need to write.

**Bottom line:** push now for CI (Parts A+B). Submit only after the GDS is
finished, integrated, renamed, LEF'd, and the top level is LVS-clean.
