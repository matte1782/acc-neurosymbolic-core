# Stage 3 — Multi-software robustness · Part 1 baseline (diagnostic, READ-ONLY on code)

> **Status of this document.** Facts, not code. Produced by `/stage31stpart` on **2026-06-18**.
> No tracked source was edited (no `checker.py`, `parser.py`, `*.md` law, or `ROADMAP.md` change;
> no ROADMAP flip; no ADR). Every headline number below was **re-derived by the orchestrator**
> directly from the saved `sandbox/data/*_report.json` plus an independent `ifcopenshell` 0.8.5
> re-count — not trusted from subagent prose. Three diagnostic subagents profiled one fixture each
> (Workflow `wf_1769ee7c-f79`); their numbers matched the artifacts exactly (zero divergences).

## Controls (must hold — verified this session)
- `cd sandbox && python tests/test_gate.py` → **19/19** (Stage-2 gate intact).
- FZK-Haus control reproduced **from the artifact**: baseline **5**, `--salva-casa` **1**.
- Environment: Python 3.13.14, `ifcopenshell` 0.8.5; all three `.ifc` are real STEP files
  (`ISO-10303-21` header), all declare **METRE** length unit (`calculate_unit_scale = 1`).

## Acquisition (deterministic, recorded)
| Fixture | Resolved source | Bytes | Note |
|---|---|---|---|
| AC20-FZK-Haus | in-repo control `data/AC20-FZK-Haus.ifc` (git-ignored) | 2 526 544 | not downloaded |
| AC20-Institute-Var-2 | `https://www.steptools.com/docs/stpfiles/ifc/AC20-Institute-Var-2.ifc` | 10 786 515 | clean download |
| Duplex_A_20110907 | `https://media.githubusercontent.com/media/buildingsmart-community/Community-Sample-Test-Files/main/IFC%202.3.0.1%20(IFC%202x3)/Duplex%20Apartment/Duplex_A_20110907.ifc` | 2 380 763 | **see Git-LFS note** |

> **Git-LFS acquisition finding (reproducibility).** The buildingSMART repo stores these IFCs via
> **Git LFS**. The README-style `raw.githubusercontent.com` URL **and** the `gh api … -H "Accept:
> application/vnd.github.raw"` fallback both returned only a **132-byte LFS pointer**
> (`oid sha256:b347a2c8…`, declared size 2380763), **not** the model. The real object resolves only
> via the LFS **media** endpoint (`media.githubusercontent.com/media/…`). The architectural model
> (`Duplex_A_…`, carrying `IfcSpace`+`IfcWindow`) was selected over the MEP/Electrical/Plumbing/
> `ROOMS_AND_SPACES` variants. Any future re-acquisition must use the media URL above.

## Evidence table (one row per fixture — all values artifact-derived)
| Fixture | Schema (tool) | IfcSpace / IfcWindow / Boundary (README) | Crashed? | Violations base → salva | none height/area/aero | Windows resolved | Classification hab/acc/unk | compliant None/True/False |
|---|---|---|---|---|---|---|---|---|
| **AC20-FZK-Haus** | IFC4 (ArchiCAD) | 7 / 11 / 81 (✅ exact) | no | **5 → 1** | 0 / 0 / 0 | 6 / 7 | 4 / 2 / 1 | 0 / 2 / 5  (sc 0 / 6 / 1) |
| **AC20-Institute-Var-2** | IFC4 (ArchiCAD/KIT) | 82 / 206 / 1000 (✅ exact) | no | **2 → 2** | 0 / 0 / 0 | 73 / 82 | 0 / 25 / 57 | 0 / 80 / 2 |
| **Duplex_A_20110907** | IFC2X3 (Revit) | 21 / 24 / 265 (✅; README gives 21/24, boundary count not stated) | no | **0 → 0** | **21 / 21 / 21** | 8 / 21 | 9 / 6 / 6 | **21 / 0 / 0** |

Supporting per-fixture facts (artifact-derived):
- **FZK** — `BaseQuantities.Height` present on all 7 spaces (`scale=1`); `BaseQuantities` also exposes
  `ClearHeight`, `FinishCeilingHeight`, `FinishFloorHeight` (none read by the checker). 6/7 spaces
  resolve a window via `IfcRelSpaceBoundary`; 5/81 boundaries have `RelatedBuildingElement=None`.
- **Institute** — same `BaseQuantities.Height` family present (all H=2.7). The **2 violations are
  spaces `402`/`403`** — `unknown`-classified, 71 m² each, `height_ok=True`, but **`win=0`** (no
  `IfcWindow` among their boundaries) → `aero=0 < 0.125`. 73/82 spaces resolve a window; **8/1000
  boundaries have `RelatedBuildingElement=None`**. `classify()` returns **0 habitable** (German/KIT
  room codes match neither hint list); `unknown` rooms still get the habitable-strength aero check,
  so the verdict over-flags rather than launders — the safe direction.
- **Duplex** — the silent-false-pass stressor. **No space Qto/`BaseQuantities` at all**; the only
  height-like key is `PSet_Revit_Dimensions."Unbounded Height"` — a **Pset** (so invisible to
  `_qty(qtos_only=True)`, `checker.py:106`) keyed `Unbounded Height` (not the literal `Height`
  `space_height()` demands), and semantically a Revit floor-to-floor span, **not** a net room
  height. No `NetFloorArea/GrossFloorArea`. Result: height/area/aero = `None` for all 21 → `compliant`
  = `None` for all 21 → none land in the `is False` violation filter → **"0 violations" over a model
  where nothing was verified**, in both modes. Windows do resolve (8 spaces, `win` 1.65–14.1 m²,
  `scale=1`); the binding constraint is the **None area** that blocks `aero` upstream
  (`aero_ratio = win/area if area else None`, `checker.py:178`), **not** window resolution.

## Prioritized GAP LIST  *(describe only — no implementation in Part 1)*
Each gap: `{symptom · fixtures affected · checker.py:line · minimal fix}`.

1. **SILENT FALSE-PASS — an unmeasurable space is dropped from the verdict, never flagged.**
   `compliant` returns `None` when a space has zero measurable checks (`checker.py:91-94`); the run
   counts only `compliant is False` (`checker.py:213`), and a missing height merely appends a note
   while leaving `height_ok=None` (`checker.py:184-187`). **Duplex: 21/21 spaces → "0 violations"**
   reads as a clean pass. *(Latent on FZK/Institute: 0 None spaces there.)*
   **Minimal fix:** add a distinct `undetermined`/`spaces_undetermined` status for `compliant is None`
   and surface it in the report + CLI verdict so a fully-unmeasured model can never print a bare
   "0 violations" pass. **This is the production-safety keystone and needs no geometry.**

2. **HEIGHT key is single-literal `"Height"` — vendor net-height variants are not read.**
   `space_height()` reads only `"Height"` from `_SPACE_QTO` (`checker.py:117-118`); the candidate set
   is the fixed pair `_SPACE_QTO`/`_WINDOW_QTO` (`checker.py:100-101`). FZK & Institute also carry
   `ClearHeight`/`FinishCeilingHeight`/`FinishFloorHeight` (unused); **Duplex carries no Qto height at
   all**. **Minimal fix (Part-2-safe):** try a Qto-level key tuple
   (`"Height","ClearHeight","FinishCeilingHeight","NetHeight","AltezzaNetta"`) with `"Height"` **first**
   (preserves FZK/Institute), first non-None wins. ⚠️ This does **not** recover Duplex (its only
   height is a Pset `Unbounded Height` = the wrong quantity); recovering Duplex height is geometry work → Part 3.

3. **AREA is single-source (`NetFloorArea`/`GrossFloorArea`, Qto-only) — Revit/GSA areas unseen.**
   `space_floor_area()` tries only those two keys (`checker.py:121-126`), Qto-only (`checker.py:106`).
   **Duplex: all 21 area=None** (areas live in `GSA Space Areas` / `PSet_Revit_*`, never tried).
   **Minimal fix:** add area key/source fallbacks — but the choice between GSA/BOMA/Revit area
   definitions risks the wrong number, so a *reliable* Duplex area is geometry work → **Part 3**.

4. **WINDOWS resolve only via `IfcRelSpaceBoundary`; the containment fallback is an unimplemented TODO.**
   `windows_serving()` sums windows from `space.BoundedBy` and returns 0.0 otherwise
   (`checker.py:147-158`, TODO at `:150-151`). **Institute: spaces 402/403 → `win=0` → the only 2
   violations** (probable false-positives from 8/1000 `RelatedBuildingElement=None` boundaries).
   Duplex windows *do* resolve, so this is not Duplex's binding constraint. **Minimal fix:** associate
   windows by storey containment / hosting wall when boundaries don't resolve them — inference that
   *risks wrong window→room association* → **Part 3** (alongside geometry).

5. **CLASSIFICATION heuristic is Italian/German-word-based — non-matching names fall to `unknown`.**
   `classify()` keys off `_HABITABLE_HINTS`/`_ACCESSORY_HINTS` (`checker.py:138-144`). **Institute:
   0 habitable / 25 accessory / 57 unknown** (numeric KIT room codes match nothing). Safe direction
   (`unknown` gets the habitable-strength check), so this is precision, not safety. **Minimal fix:**
   extend the hint vocabularies (Büro/Labor/Treppe/…). ⚠️ **Control-coupled**: any hint that flips a
   space to `accessory` lowers its required height and skips its aero check → can change FZK **5→1** /
   Institute **2→2**. Must re-verify both controls after editing.

## Min-bar vs real-bar recommendation
- **Min-bar — "clean, runtime-error-free verdict on ≥3 IFC from different software" (ROADMAP:96-97):**
  **already met.** No fixture crashes (no traceback in any of the 6 runs); each emits a verdict
  (FZK 5→1, Institute 2→2, Duplex 0→0). But the Duplex verdict is *hollow* (nothing measured).
- **Real-bar — a *meaningful* verdict.** Requires two distinct things, separable by risk:
  - **(honest) Part 2:** never silently pass an unmeasurable space (Gap 1) + read vendor net-height
    Qto variants (Gap 2) + optional classification vocabulary (Gap 5). Control-preserving, mechanical.
    After Part 2 the Duplex reads **"0 violations, 21 undetermined — not certifiable"** instead of a
    bare pass — safe and honest, though its 21 spaces are still not *evaluated*.
  - **(meaningful) Part 3:** derive height/area (and associate windows) from the **3D geometry** when
    Qto/Pset/boundaries are absent or semantically wrong — the Duplex case (Gaps 3, 4, and the
    geometry half of 2). Multi-function, wrong-number-prone, needs its own verification harness.
- **Recommendation:** do Part 2 now (closes the safety hole + cheap robustness, all controls held);
  spin Part 3 for the geometry fallback.

## REFINE (completeness critic)
- **Under-characterized fixtures — resolved by a targeted read-only probe (no ambiguity carried
  forward):** Duplex *window resolution* and *unit scale* were explicitly tested, not assumed —
  8 spaces resolve windows (1.65–14.1 m²) and the file declares METRE (`scale=1`); the aero block is
  the **None area**, confirmed by the 8 window-resolved spaces all showing `aero=None` because
  `area=None`. Duplex *height keys* were enumerated: exactly one height-like key exists
  (`PSet_Revit_Dimensions."Unbounded Height"`), and it is a Pset (invisible to `qtos_only=True`) and
  the wrong quantity — so multi-key **Qto** lookup cannot recover it; only geometry can.
- **Gap independence / fix order (lowest-risk → highest-risk):**
  - Gap 1 (safety/undetermined) — **independent**, additive to reporting only; current numbers
    unchanged (FZK/Institute have 0 None spaces). **Do first.**
  - Gap 2 (multi-key height, Qto-level, `"Height"` first) — **independent**, additive; **zero verdict
    delta on the 3 current fixtures** (FZK/Institute have `Height`; Duplex has no Qto height). **Do second.**
  - Gap 5 (classification vocabulary) — **independent but control-coupled**; must re-verify FZK 5→1
    and Institute 2→2 after editing. **Do last in Part 2; revert if a control moves.**
  - Gaps 3 & 4 (area + window-containment) — **coupled** to each other and to Gap 2's geometry half,
    all needing geometry-derived quantities and a verification harness. **Deferred to Part 3 as one
    unit.**
- **PRODUCTION-SAFETY INVARIANT (Part 2 & Part 3 MUST honor it):** *the checker must never silently
  mark an unmeasurable space COMPLIANT.* Missing height / area / window ⇒ the space stays **flagged
  with a note as `undetermined`**, and a model with undetermined spaces must **never** print a bare
  "0 violations" pass. (Symbolic analog of the Stage-2 "no-launderer / verify-never-trust" rule:
  absence of evidence is never evidence of compliance.)

## Part 3 decision — **GO (spin `/stage33rdpart` later, authored from Part 2's results)**
**Trigger (reproducible):** the Duplex carries **no usable Qto height and no area Qto**, and its only
height-like value is a Pset `Unbounded Height` that is the **wrong quantity** — so no safe key-based
lookup can make its 21 spaces *measurable*. A *meaningful* (not merely honest) Duplex verdict therefore
requires **deriving height/area from the 3D shape and associating windows by containment** when
quantities/boundaries are absent — work that spans `space_height` + `space_floor_area` +
`windows_serving`, **risks wrong numbers** (gross-vs-net height, GSA/BOMA-vs-net area, wrong
window→room mapping), and **needs its own verification harness**. Per the command's go/no-go rule this
is high-risk + coupled ⇒ it is kept **out of Part 2** and spun as Part 3. Part 2 alone still satisfies
the safety invariant (Gap 1) and the min-bar; Part 3 is required only to reach the real-bar on the
Duplex/no-quantity class of files.

## Housekeeping note (not a defect)
`.gitignore` ignores `*.ifc` (line 32) but **not** `*_report.json`, so the six `data/*_report.json`
artifacts and the pre-existing `data/fzk_report.json` show as **untracked** (the command's wording
"`data/*_report.json` (git-ignored)" is slightly optimistic). The `.ifc` downloads *are* ignored.
No `.gitignore` edit was made (out of Part-1 allowed writes). The DONE-WHEN "no tracked source
changed" requirement is satisfied; the reports are expected untracked diagnostic artifacts.
