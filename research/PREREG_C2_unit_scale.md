# PREREGISTRATION — C-2: absent/unresolved length unit → silent 1.0 scale → 1000× misread → false pass

> **FROZEN BEFORE candidate generation/judging.** Same bias-resistance contract as
> `PREREG_C1_window_geometry.md` §0: external ground truth, pinned expected verdicts, frozen
> objective/gates/decision-rule, the shipped fix entered as one candidate. Freeze hash at commit.

## 0. The bias this design fights
`ifcopenshell.util.unit.calculate_unit_scale` returns **1.0** when there is no `IfcProject`, no
`UnitsInContext`, or no `LENGTHUNIT` — silently assuming metres. The 3 fixtures all declare `METRE`
(scale 1.0), so the **circular control oracle cannot see this defect at all** (a metre model and a
unitless model both read as scale 1.0 there). Ground truth must be **external**: the IFC unit model
+ the physical fact that *scale is unknowable without a declared unit*. Expected verdicts are pinned
from the spec, not from running the code.

## 1. Question (falsifiable)
What is the **optimal** way to ensure that a model whose project length unit is **absent or
unresolved** is treated as **not-certifiable** (refused), rather than silently scaled at 1.0 (which
reads a millimetre-authored model as metres → a 2400 mm room becomes 2400 m and clears the 2.70 m
bar → silent false pass) — while a model that **correctly declares** its unit (SI metre, SI
millimetre, or conversion-based foot/inch) still scales normally and is **not** over-rejected?

## 2. External ground truth (code-independent oracle)
- **IFC unit model:** the project length unit is an `IfcSIUnit` or `IfcConversionBasedUnit` with
  `UnitType = LENGTHUNIT` under `IfcProject.UnitsInContext`. **Absent ⇒ scale is undefined** — it is
  *not* "assume metre". Present (SI or conversion) ⇒ a defined scale to metres.
- **Production-safety invariant:** unknowable scale ⇒ the model cannot be measured ⇒
  **not-certifiable**, never a guessed pass.
- **Magnitude independence:** the spec verdict for "no LENGTHUNIT" is *not-certifiable* **regardless
  of the quantity magnitudes** — the danger is precisely that we cannot tell mm from m.

## 3. Candidate space (≥3 genuinely different; shipped fix is ONE entry)
- **C2-A — null / pre-fix incumbent:** `scale = calculate_unit_scale(model)` as-is. The defect
  (proceeds at 1.0 on a unitless model). Differential baseline; must FAIL the safety gate.
- **C2-B — shipped hard-raise (commit `ec07b03`):** require an explicit `LENGTHUNIT`, else
  `raise ValueError`. Evaluated impartially.
- **C2-C — classified not-certifiable (ties M-6):** C2-B but caught in `main()` → clean non-zero
  exit + "model not certifiable: no length unit" message, not a raw traceback. Operability vs the
  bare raise.
- **C2-D — operator override:** if no unit resolves, refuse unless the operator passes
  `--assert-length-unit {m,mm,ft,...}`; then scale by the asserted unit. Usability vs a hard stop;
  risk = an operator can assert wrongly (moves trust to a human, auditable).
- **C2-E — reframe (granular unit resolution):** bypass `calculate_unit_scale`'s silent default;
  classify the unit state into {SI-resolved, conversion-resolved, **absent → undetermined**,
  **present-but-unsupported → undetermined**} and scale explicitly per case. Most granular; largest
  change.

## 4. Evaluation sets
- **Adversarial corpus** (`research/corpus/adversarial/c2_*.ifc`, generated from the fixtures;
  gitignored): minimum set —
  - `c2_no_unit`: `LENGTHUNIT` removed → **expected: not-certifiable (refuse)**. Differential: C2-A
    proceeds (defect), C2-B+ refuse.
  - `c2_no_project_units`: empty `UnitsInContext.Units` → **expected: not-certifiable**.
  - **Control `c2_mm_declared`** (negative-control against over-rejection): quantities the checker
    reads (`Qto` Height/area + window `Overall*`) scaled ×1000 **and** unit correctly set to
    `MILLIMETRE` → **expected: processes normally (scale 0.001), NOT refused.** Any candidate that
    refuses this is over-rejecting (GATE-N failure).
  - **Control `c2_metre`** = the stock conformant fixtures (scale 1.0, processes).
- **Oracle-free tests:** `test_metamorphic.py` — *unit-scale metamorphic*: a model and its
  correctly-rescaled-unit twin (e.g. metre vs correctly-declared-mm of the same building) must yield
  the **same height verdicts** (scale invariance under a correct unit change); and "remove the unit"
  must change the outcome from *a verdict* to *refusal* (the defect's signature).
- **Held-out:** open-repo IFCs in mm and in ft if obtainable (blind generalization); else record the
  gap.

## 5. Objective function (frozen) + HARD GATES
**Hard gates (disqualifying):**
- **GATE-S (safety):** every `c2_no_*` (unitless) file is **refused / not-certifiable** — none may
  produce a normal compliance verdict.
- **GATE-N (neutrality / no over-reject):** the 3 conformant fixtures + frozen controls unchanged
  (FZK 5/1, Institute 2/2, Duplex 0/21), AND `c2_mm_declared` **processes** (is not refused), AND a
  conversion-based (foot/inch) unit resolves rather than raising.
- **GATE-X (no unintended crash):** a refusal must be a **classified** signal (raise/typed
  exit/undetermined), distinguishable from a checker bug.

**Weighted score (0–5) among survivors:**
| Criterion | Weight |
|---|---|
| Safety coverage (all unitless states refused; mm/ft/declared handled) | 0.30 |
| Correctness / no over-rejection on conformant + declared-non-metre data | 0.25 |
| Spec-faithfulness (IFC unit model) | 0.15 |
| Simplicity / maintainability | 0.15 |
| Operability (classified message vs raw traceback; auditability) | 0.10 |
| Performance | 0.05 |

## 6. Decision rule (frozen)
Identical procedure to `PREREG_C1` §6: drop gate-failers; pick max weighted; **stability clause** —
keep shipped C2-B if within **0.3** of the max; record all scores + negatives →
`research/DECISION_MATRIX.md`. Note: C2-C is C2-B + an operability increment, so if operability
proves decisive the recommendation may be "C2-B → C2-C", recorded explicitly.

## 7. Falsification criteria
A candidate dies on any hard-gate failure (esp. GATE-N over-rejection of `c2_mm_declared` or a
foot-unit file, and GATE-S letting a unitless file produce a verdict). Null C2-A is expected to fail
GATE-S; if it does **not**, the corpus failed to express the defect and must be strengthened first.
