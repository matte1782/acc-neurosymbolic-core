# Stage 4 · Part 2 — Generalize the requirement model + externalize the applicability table (WRITES production code, VERDICT-NEUTRAL)

Repo: `acc-neurosymbolic-core` (Slice A). Part 1 (`/stage41stpart`) is done: the baseline +
frozen design is `sandbox/STAGE4_BASELINE.md` (artifact-grounded, orchestrator-re-verified). This
command **implements** the two lowest-risk, **verdict-neutral** pieces of the rescoped Stage 4:
(1) generalize the 4-float `Thresholds` into a record-backed model with a **backward-compatible
accessor**, and (2) externalize `classify()` + the `check_space` applicability branches into a
**declarative table**. **No graph. No gate change. No new rule.** The gate extension (Part 3) and
the monostanza 2nd rule (Part 4) are **authored later from Part 2/3 results — do NOT attempt or
pre-write them here.**

> **Why verdict-neutral first.** Part 1 proved the model is rigid (`Thresholds` has exactly 4
> fields, `checker.py:66-69`; `from_rules_json` whitelists exactly 4 keys, `checker.py:76-78`;
> `thr.<newkey>` would `AttributeError`). Generalizing it is the prerequisite for rule #2, but it
> must move **zero verdicts**. The acceptance test is a per-`GlobalId` **table-driven-vs-current-
> Python** equality, captured BEFORE the refactor and asserted after.

> **Working directory.** Run everything from the repo root
> `C:/Users/matte/Desktop/Desktop OLD/AI/Università AI/courses/personal_project/industrial.review/acc-neurosymbolic-core`.
> If the session started elsewhere, `cd` there first. Paths below are relative to it; checker/test
> commands run from `sandbox/`.

## BOOT (read first)
`sandbox/STAGE4_BASELINE.md` (the frozen schema + numbers + debt boundary you must honor — esp.
§3 generalization surface, §4 table schema, §6 frozen GlobalId anchors, §7 debt, §8 safety
invariant), `docs/decisions.md` (ADR-004 newest), `CLAUDE.md`, `ROADMAP.md` Stage 4 (`:117-127`)
and the rescope context, `sandbox/checker.py` (the file you edit), `sandbox/parser.py` (read-only
here — you do NOT edit it in Part 2).

## START CONTROLS (run first from `sandbox/` — if any is off, STOP: env/regression, not Stage 4)
- `python tests/test_gate.py` → **19/19**; `python tests/test_height_keys.py` → **9/9**;
  `python tests/test_geometry_fallback.py` → **12/12**.
- `python checker.py data/AC20-FZK-Haus.ifc --json data/AC20-FZK-Haus_report.json` → **5**;
  `--salva-casa` → **1**.
- `python checker.py data/AC20-Institute-Var-2.ifc --json data/AC20-Institute-Var-2_report.json` →
  **2** (spaces **402/403**); `--salva-casa` → **2**.
- `python checker.py data/Duplex_A_20110907.ifc --json data/Duplex_A_20110907_report.json` →
  **0 / 21 undetermined** (both modes; exit ≠ 0 EXPECTED).
- `python probe_controls.py` → **FROZEN CONTROLS HELD** (FZK 5/1, Institute 402/403 both modes).
- If a `data/*.ifc` is missing (git-ignored), re-acquire per `stage32ndpart.md:22-27` (Duplex via the
  `media.githubusercontent.com` LFS endpoint, ~2 380 763 bytes, starts `ISO-10303-21`).

## HARD RULES
- **Edit `sandbox/checker.py` only**, plus **ADD**: one declarative data file under `sandbox/rules/`
  and tests under `sandbox/tests/`. Do **NOT** touch `parser.py`, the law `.md`, the compiled rule
  JSON, or `ROADMAP.md` (the gate generalization + monostanza + ADR/ROADMAP flip are Parts 3/4).
- **`SpaceFinding`/`compliant` (`checker.py:96-108`) is UNTOUCHED** (Stage-3 Part-3 keystone).
- **Fix the code, not the harness.** Never weaken a check or a control to make a number pass.
- **One task at a time, in order.** After EACH task run the full **REGRESSION BLOCK** and confirm the
  invariant before the next. **If any control moves, revert that task and stop.**
- **The 4 frozen numbers must resolve BYTE-IDENTICALLY** (`2.70 / 2.40 / 2.40 / 0.125`) through the
  new accessor. **Fail-closed:** an unknown key/metric **raises** (mirror the `parser.py` gate-raise),
  never a silent default.
- **Hint set stays SET-EQUAL to the Python tuples including codepoints** — the `"küche"` U+00FC vs
  ASCII `"kuche"` pair (`checker.py:48`) is load-bearing for FZK 5→1 (baseline §4).
- **Observation separate from interpretation**; cite `checker.py:<line>` in notes for each change.
- **PRODUCTION-SAFETY INVARIANT (must hold after every task):** never silently mark an unmeasurable
  space COMPLIANT; missing data ⇒ `undetermined`, never a pass (baseline §8).

## STEP 0 — capture the equivalence ORACLE (do this BEFORE editing checker.py)
Freeze the current Python's per-`GlobalId` verdict-relevant state into a **committed golden
fixture**, so the refactor is judged against the pre-refactor truth (it must survive the edit —
do NOT put it under git-ignored `data/`):
```
# from sandbox/ — writes the golden fixture the new test asserts against (commit it)
python - <<'PY'
import json, ifcopenshell, ifcopenshell.util.unit as uu, checker
FIX = ["data/AC20-FZK-Haus.ifc","data/AC20-Institute-Var-2.ifc","data/Duplex_A_20110907.ifc"]
oracle = {}
for path in FIX:
    m = ifcopenshell.open(path); scale = uu.calculate_unit_scale(m)
    for sc in (False, True):
        for s in m.by_type("IfcSpace"):
            f = checker.check_space(s, scale, sc, checker.Thresholds())
            oracle[f"{path}|{sc}|{f.global_id}"] = [
                f.occupancy, f.height_required_m, (f.occupancy != "accessory"),
                f.height_ok, f.aero_ok, f.compliant]
json.dump(oracle, open("tests/equiv_oracle.json","w"), indent=0)
print("oracle rows:", len(oracle))   # expect 7*2 + 82*2 + 21*2 = 220
PY
```
The binding acceptance test (`tests/test_applicability_table.py`, added in Task 2) re-runs this
projection against the **refactored** checker and asserts **every row equals**
`tests/equiv_oracle.json` — per `GlobalId`, both modes, all 3 fixtures: `(occupancy,
height_required_m, aero_applies, height_ok, aero_ok, compliant)`. Run it **before trusting** the
refactor; any drift = revert. (Golden lives under `tests/` so it is version-controlled and cannot
be silently regenerated post-refactor — `data/` is git-ignored and would lose the "before".)

## REGRESSION BLOCK (run after EVERY task — from `sandbox/`)
```
python tests/test_gate.py                                                                 # 19/19
python tests/test_height_keys.py                                                          # 9/9
python tests/test_geometry_fallback.py                                                    # 12/12
python tests/test_applicability_table.py                                                  # (Task 2+) all green
python checker.py data/AC20-FZK-Haus.ifc            --json data/AC20-FZK-Haus_report.json            # viol 5
python checker.py data/AC20-FZK-Haus.ifc --salva-casa --json data/AC20-FZK-Haus_report_sc.json       # viol 1
python checker.py data/AC20-Institute-Var-2.ifc     --json data/AC20-Institute-Var-2_report.json     # viol 2
python checker.py data/AC20-Institute-Var-2.ifc --salva-casa --json data/AC20-Institute-Var-2_report_sc.json # viol 2
python checker.py data/Duplex_A_20110907.ifc        --json data/Duplex_A_20110907_report.json        # 0 / 21 undet
python checker.py data/Duplex_A_20110907.ifc --salva-casa --json data/Duplex_A_20110907_report_sc.json # 0 / 21 undet
python probe_controls.py                                                                   # FROZEN CONTROLS HELD
```
**Global invariant (byte-identical, every task):** `test_gate` 19/19, `test_height_keys` 9/9,
`test_geometry_fallback` 12/12; violations `FZK 5→1`, `Institute 2→2` (**GlobalIds**
`0jbV$RErb7o9P7rp7ALEd$`=402, `3txvJd9V1BPhyU$48F$mnF`=403), `Duplex 0 / 21 undetermined` both
modes; `spaces_undetermined` = `{FZK:0, Institute:0, Duplex:21}`; FZK frozen set =
`{0Lt8gR_E9ESeGH5uY_g9e9, 17JZcMFrf5tOftUTidA0d3, 2RSCzLOBz4FAK$_wE8VckM, 2dQFggKBb1fOc1CqZDIDlx,
347jFE2yX7IhCEIALmupEH}`, salva-casa = `{2dQFggKBb1fOc1CqZDIDlx}`. **Part 2 changes structure, not
a single verdict** — any movement means revert.

---

## TASK 1 — Generalize the requirement/threshold model (backward-compatible)  *(lowest risk)*
- **Target:** `Thresholds` dataclass (`checker.py:62-79`: 4 fields `:66-69`, `from_rules_json`
  `:71-79`); consumers `check_space` (`checker.py:195-197` height bar, `:222` aero ratio) and the
  `run()`/`main()` `asdict(thr)` + print (`checker.py:251, 280-281`).
- **Gap (baseline §3):** 4 hardcoded float fields + a 4-key whitelist; a 5th metric (monostanza,
  Part 4) cannot reach the checker (`from_rules_json` drops it; `thr.<newkey>` raises). The model
  must become extensible **without** moving the 4 frozen numbers.
- **Change (single concern):** introduce a record-backed requirement model — a small internal
  collection of `{rule_id, metric, applicability, operator, value, unit, salva_casa_value?}` — and
  keep `Thresholds` as a **backward-compatible accessor view**: the four names
  `min_height_habitable_m / min_height_accessory_m / min_height_salva_casa_m /
  aero_illuminating_ratio` resolve through the records to the **same floats**
  (`2.70/2.40/2.40/0.125`). `from_rules_json` still reads today's compiled JSON (4 thresholds)
  identically; unknown metrics are stored but **never** silently defaulted. **Fail-closed:**
  resolving an absent metric **raises** (mirror `parser.py:329-332/365-367`), it does not return a
  default. Keep `asdict(thr)`/the print line producing the same 4 values (the report `thresholds`
  block must be byte-identical — adjust serialization if the dataclass shape changes, e.g. a
  `to_legacy_dict()`).
- **Expected verdict delta:** **NONE.** All REGRESSION BLOCK counts + GlobalId sets + the report
  `thresholds` block byte-identical. This task changes representation only.
- **Acceptance (run before trusting):** STEP-0 oracle equality (added as the test in Task 2 covers
  the per-space projection; for Task 1 specifically also assert
  `Thresholds().min_height_habitable_m == 2.70` etc. and `Thresholds.from_rules_json(
  "rules/compiled/dm_1975_salva_casa.json")` yields the same 4 floats; assert an unknown-metric
  access **raises**). Add these as `tests/test_requirement_model.py`.
- **Invariant:** global invariant holds; the 4 numbers byte-identical; unknown-key access raises.

## TASK 2 — Externalize the applicability/selection table  *(higher risk in Part 2; control-coupled)*
- **Target:** `classify()` + `_HABITABLE_HINTS`/`_ACCESSORY_HINTS` (`checker.py:45-59, 166-172`),
  the `check_space` height-bar selection (`:195-197`) and aero-applicability branch (`:219-226`)
  incl. the salva-casa swap.
- **Gap (baseline §4):** the occupancy vocabulary + occupancy→{height-bar, aero-applies} map +
  salva-casa regime are hardcoded Python. Externalize them into a **declarative data file** that
  `check_space` reads; `classify()` and the two `if`s become **table lookups**. **No graph, no
  SPARQL.**
- **Data file (ADD):** `sandbox/rules/applicability.json` (JSON for zero-dependency consistency
  with `rules/compiled/*.json`; TOML via stdlib `tomllib` is acceptable). Schema = baseline §4:
  per occupancy class `{hints[], statute_anchor, provenance, height_metric, aero_applies}` +
  `salva_casa_regime.swaps`. **Carry the provenance/debt flag now** (`"art1"` vs
  `"cross-lingual-glossary"`, baseline §7) so Part 3 can consume it — but do NOT verify it here
  (that is Part 3).
- **Critical correctness semantics (baseline §4 — bake into the loader/lookup):**
  - **`unknown` = strict complement** of (accessory ∪ habitable) — never a stored positive entry
    (protects Institute 402/403 `Dachboden` from being stolen into accessory and losing their aero
    check).
  - **Accessory-first precedence** (test accessory, else habitable, else unknown — mirror
    `checker.py:168-172`).
  - **Fail-closed:** a NOT-FOUND lookup → `undetermined`/`None`, never a pass.
  - **Hint set SET-EQUAL to the Python tuples incl. codepoints** — generate the table from the
    tuples (or assert byte-equality both ways), so the `"küche"` U+00FC pair cannot drift.
- **Expected verdict delta:** **NONE.** Counts, GlobalId sets, classification distribution
  (FZK 5h/2a; Institute 55h/25a/2u; Duplex 9h/6a/6u — baseline §6) all unchanged.
- **Acceptance test (ADD `tests/test_applicability_table.py`; run BEFORE trusting):**
  1. **Equivalence (binding):** the per-`GlobalId` projection `(occupancy, height_required_m,
     aero_applies, height_ok, aero_ok, compliant)` over all 3 fixtures **both modes** equals
     `tests/equiv_oracle.json` (STEP 0) — all **220** rows identical.
  2. **Hint byte-equality incl. codepoints:** the table's accessory+habitable hint sets are
     **set-equal** to the original `_HABITABLE_HINTS`/`_ACCESSORY_HINTS` tuples, asserting U+00FC is
     present in `"küche"` and absent in `"kuche"`.
  3. **`unknown` = strict complement:** a synthetic space whose name matches no hint → `unknown`;
     no table entry stores `unknown`.
  4. **Accessory-precedence collision:** a name matching BOTH an accessory and a habitable hint
     (e.g. `"Badezimmer"` → `bad`+`zimmer`) classifies **accessory**.
  5. **Fail-closed:** a missing/empty table file or an absent occupancy lookup raises / yields
     `undetermined`, never a silent pass.
- **Invariant (HARD):** if ANY control count or GlobalId set moves, or any of the 220 oracle rows
  differs, the table is wrong — **revert this task**. Ship only if every control + the equivalence
  test is green.

---

## DECIDE / HAND-OFF
- Part 2 delivers an **extensible, record-backed model** + a **declarative, provenance-tagged
  applicability table**, with **zero verdict movement** (220-row equivalence + frozen controls).
  This is the prerequisite the graph-rescope identified: the model now admits a 2nd rule's metric
  and the applicability logic is data, not Python — **without** a premature graph.
- **Part 3 (`/stage43rdpart`) — author it AFTER Part 2 is green, from Part 2's results
  (NOT pre-written):** extend the verify-never-trust gate to applicability/selection —
  anchor the **Italian accessory tokens to Art.1** (`dm_1975_salva_casa.md:9-10`), **declare +
  test-pin the cross-lingual glossary as named debt** (baseline §7 boundary), `test_gate.py` grows
  but stays green, **no verdict change**.
- **Part 4 (`/stage44thpart`) — authored later, from Part 2/3 results:** add the monostanza 2nd
  rule end-to-end + extend the gate to its numbers (`28/38/20/28`), un-suppress the monostanza
  decoy (`parser.py:101`) while keeping **montani 2,55 and seismic decoys rejected** (regression
  test); monostanza **`undetermined`** on all 3 fixtures (no monolocale/person-count data —
  baseline §6), never a pass; then ADR-005 + ROADMAP renarrow + Stage-4b split.

## DONE-WHEN (Part 2)
1. `checker.py` edited for Task 1 (record-backed model + backward-compatible accessor, fail-closed)
   and Task 2 (table-driven `classify()`/`check_space`), each a single-concern change citing
   `checker.py:<line>`; `SpaceFinding`/`compliant` untouched; `parser.py`/law `.md`/compiled
   JSON/ROADMAP untouched.
2. ADDED: `sandbox/rules/applicability.json` (provenance-tagged), `sandbox/tests/equiv_oracle.json`
   (committed 220-row golden), `sandbox/tests/test_requirement_model.py`,
   `sandbox/tests/test_applicability_table.py`.
3. REGRESSION BLOCK green after every task: `test_gate` 19/19, `test_height_keys` 9/9,
   `test_geometry_fallback` 12/12, new tests green, `probe_controls.py` = HELD; violations
   `FZK 5→1`, `Institute 2→2` (402/403), `Duplex 0/21` both modes — **byte-identical**.
4. The binding **220-row equivalence** (table-driven vs `tests/equiv_oracle.json`) passes; the 4
   frozen numbers resolve byte-identically; unknown-metric access raises.
5. **No ROADMAP flip, no ADR** in Part 2 (verdict-neutral structural refactor; the renarrow +
   ADR-005 land in Part 4). `.idos/events.jsonl`: append a line **only** on a real STOP/GATE/DEFECT.
Then **STOP** and hand back the diff, the regression + equivalence output, and confirm Part 3 is
ready to be authored from these results (do not start Part 3).
