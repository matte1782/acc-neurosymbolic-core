# Stage 3 · Part 2 — Harden `checker.py` for multi-software robustness (WRITES production code)

Repo: `acc-neurosymbolic-core` (Slice A). Part 1 (`/stage31stpart`) is done: the diagnostic baseline
is `sandbox/STAGE3_BASELINE.md` (artifact-grounded, re-verified). This command **implements** the
mechanical, control-preserving subset of those gaps in `checker.py`. The high-risk geometry fallback
is **deferred to `/stage33rdpart`** (do NOT attempt it here).

> **Working directory.** Run everything from the repo root
> `C:/Users/matte/Desktop/Desktop OLD/AI/Università AI/courses/personal_project/industrial.review/acc-neurosymbolic-core`.
> If the session started elsewhere, `cd` there first. Paths below are relative to it; checker/test
> commands run from `sandbox/`.

## BOOT (read first)
`sandbox/STAGE3_BASELINE.md` (the gap list + numbers you must preserve), `docs/decisions.md`
(ADR-002 newest), `CLAUDE.md`, `ROADMAP.md` Stage 3 (`:90-106`), `sandbox/checker.py` (the file you edit).

## START CONTROLS (run first — if any is off, STOP: env/regression, not Stage 3)
From `sandbox/`:
- `python tests/test_gate.py` → **19/19**.
- `python checker.py data/AC20-FZK-Haus.ifc --json data/AC20-FZK-Haus_report.json` → **5**;
  add `--salva-casa` → **1**.
- The 3 fixtures must be on disk (git-ignored `data/*.ifc`). If a `data/*.ifc` is missing, re-acquire:
  - FZK: already in repo.
  - Institute: `curl -L -o data/AC20-Institute-Var-2.ifc https://www.steptools.com/docs/stpfiles/ifc/AC20-Institute-Var-2.ifc`
  - Duplex (**Git-LFS** — the raw/gh-raw URLs return a 132-byte pointer; use the **media** endpoint):
    `curl -L -o data/Duplex_A_20110907.ifc "https://media.githubusercontent.com/media/buildingsmart-community/Community-Sample-Test-Files/main/IFC%202.3.0.1%20(IFC%202x3)/Duplex%20Apartment/Duplex_A_20110907.ifc"`
    (must start `ISO-10303-21`, ~2 380 763 bytes).

## HARD RULES
- **Edit `sandbox/checker.py` only.** Do NOT touch `parser.py`, the law `.md`, the compiled rule JSON,
  or `ROADMAP.md` in this command (the ROADMAP flip + ADR happen after Part 2/3 verification, not mid-edit).
  You MAY add a focused test under `sandbox/tests/` if a task needs unit coverage.
- **Fix the code, not the harness.** Never weaken a check, the gate, or a control to make a number pass.
- **One task at a time, in order.** After EACH task, run the full **REGRESSION BLOCK** and confirm the
  invariant before starting the next. If a control moves unexpectedly, revert that task and stop.
- **Observation separate from interpretation**; cite `checker.py:<line>` in the commit/notes for each change.
- **PRODUCTION-SAFETY INVARIANT (must hold after every task):** the checker must **never silently mark
  an unmeasurable space COMPLIANT**. Missing height/area/window ⇒ the space is flagged `undetermined`
  with a note; a model containing undetermined spaces must **never** print a bare "0 violations" pass.

## REGRESSION BLOCK (run after EVERY task — from `sandbox/`)
```
python tests/test_gate.py                                                                 # MUST be 19/19
python checker.py data/AC20-FZK-Haus.ifc        --json data/AC20-FZK-Haus_report.json         # viol MUST be 5
python checker.py data/AC20-FZK-Haus.ifc --salva-casa --json data/AC20-FZK-Haus_report_sc.json # viol MUST be 1
python checker.py data/AC20-Institute-Var-2.ifc --json data/AC20-Institute-Var-2_report.json   # viol MUST be 2
python checker.py data/AC20-Institute-Var-2.ifc --salva-casa --json data/AC20-Institute-Var-2_report_sc.json # viol MUST be 2
python checker.py data/Duplex_A_20110907.ifc    --json data/Duplex_A_20110907_report.json      # viol MUST be 0
python checker.py data/Duplex_A_20110907.ifc --salva-casa --json data/Duplex_A_20110907_report_sc.json # viol MUST be 0
```
**Global invariant for all tasks:** `test_gate.py` 19/19 **and** violations `FZK 5→1`, `Institute 2→2`,
`Duplex 0→0` stay exactly as above. (Tasks change *reporting* and *latent robustness*, not these counts —
re-evaluating the Duplex spaces is Part 3.) Verify a number changed only where a task says it should.

---

## TASK 1 — Surface unmeasurable spaces (production-safety keystone)  *(lowest risk, highest value)*
- **Target:** `SpaceFinding.compliant` (`checker.py:91-94`), `run()` serialization + summary
  (`checker.py:203-223`), `main()` verdict print (`checker.py:226-252`); the missing-height note path
  (`checker.py:184-187`) and the `is False` violation filter (`checker.py:213`).
- **Gap (baseline §1):** `compliant` returns `None` for a space with zero measurable checks; the run
  counts only `compliant is False`, so unmeasurable spaces vanish from the verdict.
- **Fixture that exercises it:** **Duplex** — 21/21 spaces `compliant=None` → today prints "0 violations".
  (FZK/Institute have 0 such spaces.)
- **Change (single concern):** compute `undetermined = [d for d in serialized if d["compliant"] is None]`;
  add `"spaces_undetermined": len(undetermined)` to the report dict; in `main()` print it in the
  verdict line and list each undetermined space with its note. Do **not** reclassify `None` as `False`
  (that would falsely mark unmeasured as violating) and do **not** change the `violations` definition.
- **Expected verdict delta (before → after):**
  - FZK `5→1`, Institute `2→2`, Duplex `0→0` **violations unchanged**.
  - Report gains `spaces_undetermined`: FZK **0**, Institute **0**, **Duplex 21** (both modes).
  - Duplex CLI line changes from a bare "0 violation(s)" to one that also shows "21 undetermined /
    not certifiable" — the observable safety fix.
- **Regression:** run the REGRESSION BLOCK; additionally confirm
  `python - <<'PY'\nimport json;print({f:json.load(open(f))["spaces_undetermined"] for f in ["data/AC20-FZK-Haus_report.json","data/AC20-Institute-Var-2_report.json","data/Duplex_A_20110907_report.json"]})\nPY`
  → `{FZK:0, Institute:0, Duplex:21}`.
- **Invariant:** all REGRESSION BLOCK counts hold; the global invariant holds.

## TASK 2 — Multi-key Qto height lookup (`"Height"` first)  *(low risk; future-proofing)*
- **Target:** `space_height()` (`checker.py:117-118`); candidate tuple `_SPACE_QTO` (`checker.py:100-101`),
  read via `_qty(..., qtos_only=True)` (`checker.py:104-114`).
- **Gap (baseline §2):** only the literal `"Height"` key is read; vendor net-height variants
  (`ClearHeight`/`FinishCeilingHeight`/`NetHeight`/`AltezzaNetta`) are ignored.
- **Fixtures:** FZK & Institute carry these variants (currently unused); a future non-`Height` vendor
  file is the real beneficiary.
- **Change (single concern):** make `space_height()` try a key tuple
  `("Height","ClearHeight","FinishCeilingHeight","NetHeight","AltezzaNetta")`, **`"Height"` FIRST**,
  returning the first non-None. Keep `qtos_only=True`.
  **Do NOT** scan Psets and **do NOT** read Duplex's `PSet_Revit_Dimensions."Unbounded Height"** — it is
  a Pset and the wrong quantity (floor-to-floor span, not net room height); recovering Duplex height is
  Part 3 geometry work.
- **Expected verdict delta:** **none** on the 3 current fixtures — FZK `5→1`, Institute `2→2`, Duplex
  `0→0`/21 undetermined all unchanged (FZK/Institute resolve via `"Height"` as before; Duplex still has
  no Qto height). This task adds robustness without a visible delta here.
- **Acceptance (since no fixture exercises it):** add a focused unit test in `sandbox/tests/`
  asserting `space_height` returns the `ClearHeight` value when a synthetic/mocked space lacks `Height`
  but has `ClearHeight`, and that `"Height"` still wins when both are present. Run it + the REGRESSION BLOCK.
- **Invariant:** global invariant holds; `"Height"` precedence preserved (so FZK/Institute are untouched).

## TASK 3 — Classification vocabulary for German/KIT names  *(highest risk in Part 2; OPTIONAL, control-coupled)*
- **Target:** `_HABITABLE_HINTS` / `_ACCESSORY_HINTS` and `classify()` (`checker.py:45-54, 138-144`).
- **Gap (baseline §5):** Institute classifies **0 habitable / 25 accessory / 57 unknown** — numeric KIT
  room codes match no hint. (Safe today: `unknown` gets the habitable-strength aero check.)
- **Fixture:** Institute (FZK is the coupling risk — see invariant).
- **Change (single concern):** extend the hint vocabularies with office/lab/circulation terms actually
  present (e.g. `büro/buro`, `labor`, `seminar`, `flur`, `treppe`, `wc`) — **additive only**.
- **Expected verdict delta:** classification counts shift (Institute `unknown`↓, `habitable`↑) but
  **violations MUST stay FZK 5→1 and Institute 2→2**. Spaces 402/403 must remain the 2 Institute
  violations (do not let a hint flip them — or anything — to `accessory`, which would skip their aero
  check and erase a violation).
- **Regression:** REGRESSION BLOCK **plus** confirm the Institute violation *names* are still `402`,`403`.
- **Invariant (HARD):** if any control violation count moves (esp. FZK `5→1` or Institute `2→2`), the
  hint set is wrong — **revert this task**. This task is optional precision; ship it only if all controls
  hold. If it cannot be made control-safe, **drop it** and leave classification for later.

---

## DECIDE / HAND-OFF
- Part 2 closes the **safety invariant** (Task 1) + cheap robustness (Tasks 2–3) with **no control
  regression**. After Part 2, the Duplex reads honestly ("0 violations, 21 undetermined") but its 21
  spaces are still **not evaluated**.
- **Part 3 (`/stage33rdpart`) is GO** (trigger recorded in `STAGE3_BASELINE.md`): a *meaningful* Duplex
  verdict needs **geometry-derived height/area + window-by-containment** (baseline gaps 3, 4, and the
  geometry half of 2) — multi-function, wrong-number-prone, with its own verification harness. Author it
  from Part 2's results; do not start it here.

## DONE-WHEN (Part 2)
1. `checker.py` edited for Task 1 (and Tasks 2–3 if control-safe), each a single-concern change citing
   `checker.py:<line>`.
2. REGRESSION BLOCK green after every task: `test_gate.py` 19/19; `FZK 5→1`, `Institute 2→2`,
   `Duplex 0→0`; `spaces_undetermined` = `{FZK:0, Institute:0, Duplex:21}`.
3. Production-safety invariant demonstrably holds (Duplex no longer prints a bare "0 violations" pass).
4. ROADMAP flip (`Stage 3 → 🟢/✅`) + ADR-003 + Iteration-Log line: do these **after** the regression is
   green (one roadmap touch, per the update protocol), or defer the ✅ until Part 3 if "verified on real
   data across tools" is read to require a *meaningful* Duplex verdict — state which and why.
5. `.idos/events.jsonl`: append a line only on a real STOP/GATE/DEFECT during implementation.
Then **STOP** and hand back the diff, the regression output, and whether Part 3 is still GO.
