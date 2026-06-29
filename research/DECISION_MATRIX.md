# C-1 / C-2 Fix Candidate Decision Matrix

*Date: 2026-06-29.*
*Method: frozen prereg (`PREREG_C1_window_geometry.md`, `PREREG_C2_unit_scale.md`) → independent blind analysts (judge / refuter / critic) → adversarial refutation → judge under the frozen decision rule (§6). Ground truth = IFC schema + DM-1975 statute + the pinned adversarial corpus (`research/corpus/expected_verdicts.json`), **NOT** the circular control oracle (FZK 5/1 etc., which are outputs of the current code and are circular for C-1/C-2 per PREREG §0).*

All numbers below were **re-run and independently reproduced** by the synthesizer from
`cd "…/acc-neurosymbolic-core"` on 2026-06-29: `gen_adversarial.py` (5 fixtures), `eval_corpus.py`,
`sandbox/tests/test_metamorphic.py` (4/4), `sandbox/tests/test_mutation.py` (6/6), plus targeted
probes against `sandbox/checker.py`. Citations are `file:line` or measured output.

---

## C-1 — non-physical window geometry → fabricated area → false-compliant verdict

**Issue.** A negative / zero / NaN / inf / non-numeric / one-missing `IfcWindow.OverallHeight`·
`OverallWidth` (stored by `ifcopenshell` as a raw DOUBLE, **not** range-checked despite the schema
typing it `IfcPositiveLengthMeasure`) can fabricate window area and let a habitable space false-pass
the DM-1975 art.5 1/8 aero check. Scored on the frozen PREREG_C1 rubric (gates GATE-S/N/X; weights:
pathology-coverage .30, correctness .25, spec .15, simplicity .15, operability .10, performance .05;
stability clause = keep shipped C1-B if within 0.3 of the max).

| Candidate | GATE-S | GATE-N | GATE-X | Weighted total | Verdict |
|---|---|---|---|---|---|
| **C1-A** (null / pre-fix `if h and w`) | **FAIL** | n/a | n/a | — (dropped) | **DISQUALIFIED** — the documented defect |
| **C1-B** (shipped per-dim + central `_qty` guard) | PASS | PASS | PASS | **4.45** | **WINNER — KEEP** |
| **C1-C** (model-wide schema pre-pass) | PASS | UNSURE→pass | PASS | 3.90 | survivor, loses (neutrality unmeasured, large blast radius) |
| **C1-D** (reframe: Qto-Area only) | PASS | PASS (today) | PASS | 3.50 | survivor, loses (real coverage loss) |
| **C1-E** (partial guard: attr only, NOT `_qty`) | **FAIL** | n/a | n/a | — (dropped) | **DISQUALIFIED** — proves `_qty` is load-bearing |

### Winner: **C1-B** (shipped). Shipped fix IS optimal.

C1-B is the unambiguous weighted max (**4.45**), leading the next survivor C1-C (3.90) by **0.55** —
well beyond the 0.3 stability band. The **stability clause is NOT invoked**: C1-B wins on the merits,
not by incumbency. It is the only candidate that clears GATE-S/N/X **and** guards both positivity
sites:
- per-dim attribute guard at `checker.py:326-334` (each dim must be present, numeric, `math.isfinite`,
  and `> 0` — checking each dim, so `(-h)*(-w)` cannot sneak a positive product through), and
- the central `_qty` guard at `checker.py:292` (`if not math.isfinite(val) or val <= 0: return None`),
  which the C1-E ablation **proves is necessary** (see negatives).

### Corpus differential evidence (pre-fix vs fixed — observed 2026-06-29)
From `python research/corpus/eval_corpus.py` (verbatim):

| Fixture | Expected | PRE-FIX | FIXED |
|---|---|---|---|
| `c1_neg_window.ifc` | viol=5 | **viol=4 undet=0 [WRONG]** | viol=5 undet=0 [ok] |
| `c1_zero_window.ifc` | viol=5 | viol=5 undet=0 [ok] | viol=5 undet=0 [ok] |

- Pre-fix on `c1_neg_window.ifc` fabricates `(-50)*(-50) = +2500 m²` and flips the target habitable
  space `2dQFggKBb1fOc1CqZDIDlx` to compliant, dropping FZK 5→4 (false pass). Fixed restores viol=5.
- `c1_zero_window` is a no-effect control (0 is falsy; the pre-fix also fell through) — both pass.
- GATE-N controls re-run byte-identical to frozen: **FZK 7 IfcSpace / 5 viol / 0 undet**,
  **Institute 82 / 2 / 0**, **Duplex 21 / 0 / 21**. Metamorphic 4/4, mutation 6/6 PASS.

### Negative results (what lost and why — no file-drawer)
- **C1-A (DISQUALIFIED GATE-S):** the differential baseline; fabricates +2500 m², FZK 5→4 (verified).
  Expected to fail; did. Most criteria ≈0–1.
- **C1-E (DISQUALIFIED GATE-S, refuter-constructed):** guards the attribute dims but NOT the `_qty`
  fallback. The refuter built the prereg-named Qto-negative pathology (attr dims absent +
  `Qto_WindowBaseQuantities.Area = -9999`): C1-B's `_qty` guard (`checker.py:292`) returns `None`,
  while the C1-E ablation returns `-9999` → fabricated negative area poisons the aero numerator. This
  proves C1-B's `_qty` guard is load-bearing. **The frozen corpus omits this fixture** (recorded gap,
  see residual risks #3); a refuter-confirmed disqualifier counts per the procedure.
- **C1-C (3.90):** highest *raw* pathology coverage (a model-wide non-positive scan), but GATE-N
  neutrality is **UNSURE** — the broadest blast radius (prereg §3), unimplemented, and **no corpus
  fixture exercises a model-wide scan path**, so byte-neutrality on FZK/Institute cannot be asserted
  without an empirical build. Correctness 3 / simplicity 2.5 drag it 0.55 below C1-B.
- **C1-D (3.50):** elegantly removes the fabrication surface (simplicity 4.5) but the refuter measured
  a real coverage/correctness regression: **Duplex 0/24 windows carry a Qto Area**, and **2/11 FZK
  windows' Qto Area disagrees with `OverallHeight×OverallWidth` by >0.01 m²**. It is GATE-N-neutral on
  the current fixtures **only** because Duplex is already fully undetermined (21/21) — but it trades a
  whole valid measurement path for narrowness (cov 3.5 / corr 2.5).

### Residual risks / recommended follow-ups (C-1)
1. **ABSURD-POSITIVE window dim (critic C1-F — synthesizer-VERIFIED):** `window_area` has **no upper
   bound**. Measured: `C.window_area(win, 1.0)` with `OverallHeight=OverallWidth=500.0` returns
   **250000.0** (probe 2026-06-29; code at `checker.py:317-334`). A finite, `>0`, both-present absurd
   dimension fabricates area and can flip the FZK aero target to compliant. The frozen GATE-S corpus
   only tests `≤0`/zero, so this is **NOT a frozen-gate failure for C1-B** (scored on the frozen
   rubric per the bias rules) but it is a genuine safety hole shared by A/C/D/E. **FOLLOW-UP:** add a
   `c1_absurd_pos_window.ifc` fixture; consider **C1-G** (attribute↔Qto cross-validation — critic
   verified FZK 11/11 windows carry both paths, so the cross-check is computable) or a
   physical-plausibility bound.
2. **`windows_serving` None→0.0 LAUNDERING (refuter — VERIFIED at `checker.py:442`,
   `total += window_area(elem, scale) or 0.0`):** an unmeasurable serving window is silently coerced
   to a *measured* 0.0 contribution and the space is **not** marked undetermined; the diagnostic at
   `checker.py:489` ("no window via IfcRelSpaceBoundary — aero ratio may be understated") then
   misreports the cause. Violates ADR-003 (unmeasurable ⇒ undetermined, never a laundered value).
   Inherited by **every** C1 candidate that routes through `windows_serving`.
3. **CORPUS GAPS vs the prereg's own §4 minimum set:** no Qto-negative fixture (the C1-E disqualifier
   is only refutable by a hand-built file), no NaN/inf file (gen_adversarial deems them
   unrepresentable — the refuter showed `1E400` parses to `inf` and IS readable, so the claim is
   false; C1-B's `isfinite` guard happens to catch it), and no held-out IFC4-with-Qto blind check.
4. **C1-C / C1-E gate calls rest on reasoning + probes, not full builds** (C1-C/C1-E are unimplemented).
5. **Dead `> 0` guard at `checker.py:312`** in `space_floor_area` is redundant after the `_qty` guard
   (`checker.py:292`) — minor maintainability landmine, not a correctness defect.

---

## C-2 — absent/unresolved length unit → silent 1.0 scale → 1000× misread → false pass

**Issue.** `ifcopenshell.util.unit.calculate_unit_scale` silently returns 1.0 when there is no
`IfcProject` / no `UnitsInContext` / no resolvable `LENGTHUNIT` — a millimetre-authored model reads as
metres (1000× under-read) → silent false pass. EXTERNAL ground truth (PREREG_C2 §2): the project
length unit absent **OR** present-but-unresolvable ⇒ scale undefined ⇒ **not-certifiable**. Scored on
the frozen PREREG_C2 rubric (same gate/weight/decision structure as C-1).

| Candidate | GATE-S | GATE-N | GATE-X | Weighted total | Verdict |
|---|---|---|---|---|---|
| **C2-A** (null / pre-fix) | **FAIL** | n/a | n/a | 2.35 (dropped) | **DISQUALIFIED** — proceeds at 1.0 |
| **C2-B** (shipped hard-raise, presence check) | **FAIL** | PASS | weak | 4.45 (dropped) | **DISQUALIFIED** — present-but-unsupported false pass |
| **C2-C** (C2-B + classified exit in `main()`) | **FAIL (inherited)** | PASS | PASS | 4.575 (dropped) | **DISQUALIFIED** — inherits the hole |
| **C2-D** (operator `--assert-length-unit` override) | **FAIL (inherited)** | PASS | PASS | 3.55 (dropped) | **DISQUALIFIED** — override never fires + human-trust risk |
| **C2-E** (reframe: granular resolvability classification) | **PASS** | PASS (by design) | PASS | 4.45 | **WINNER (conditional on build)** |

### Winner: **C2-E** (reframe). Shipped fix is **NOT** optimal.

The shipped **C2-B is DISQUALIFIED on GATE-S** — overturning its input "shipped/correct" status on the
rubric. Because C2-B is disqualified, it is dropped *before* the weighted comparison, so the §6
**stability clause cannot keep it** (the clause only protects a *gate-surviving* shipped fix).

**The disqualifier — independently REPRODUCED by the synthesizer (probe 2026-06-29):** C2-B's guard
`length_scale_to_m` (`checker.py:587-600`) gates only on `_has_length_unit` (`checker.py:574-584`),
which returns `True` for **any** units entry with `UnitType=='LENGTHUNIT'` regardless of
resolvability. I replaced FZK's `METRE` `IfcSIUnit` with a schema-valid `IfcContextDependentUnit`
(`UnitType=LENGTHUNIT, Name='SMOOT'`) and measured:

```
has_length_unit: True
calculate_unit_scale: 1
length_scale_to_m: 1
run result: scale=1 viol=5 undet=None spaces=...   ← NORMAL verdict, NOT a refusal
```

A mm-magnitude SMOOT model is therefore a **silent 1000× false pass**. The external oracle (PREREG_C2
§2: present-but-unsupported ⇒ scale undefined ⇒ not-certifiable; §0: the 1000× threat) pins this as
`not_certifiable`. The pinned corpus only tests **absent** units (`c2_no_unit`, `c2_empty_units` —
both correctly refused), so it cannot see this class; the refuter's adversarial fixture can, and the
procedure states "a refuter-confirmed disqualifier counts." **C2-C and C2-D reuse the identical
`_has_length_unit` / `calculate_unit_scale` path and inherit the hole.** Only **C2-E**'s design
(absent→undetermined **and** present-but-unsupported→undetermined, scaling explicitly per case)
classifies that state correctly per §2.

### Corpus differential evidence (pre-fix vs fixed — observed 2026-06-29)
From `python research/corpus/eval_corpus.py` (verbatim):

| Fixture | Expected | PRE-FIX | FIXED (C2-B) |
|---|---|---|---|
| `c2_no_unit.ifc` | not_certifiable | **viol=5 undet=0 [WRONG]** | refused [ok] |
| `c2_empty_units.ifc` | not_certifiable | **viol=5 undet=0 [WRONG]** | refused [ok] |
| `c2_mm_declared.ifc` (GATE-N control) | processes | viol=7 undet=0 [ok] | viol=7 undet=0 [ok] |

C2-B genuinely fixes the **absence** class (both unitless fixtures refused; mm control still
processes at scale 0.001; foot `IfcConversionBasedUnit` probed at `length_scale_to_m=0.3048`, no
over-reject). It is a **partial fix** that left the **present-but-unresolvable** class open.

### Negative results (what lost and why — no file-drawer)
- **C2-C scored the HIGHEST weighted total (4.575)** and was the modal analyst top-pick, yet it
  **loses**: disqualified on GATE-S by inheritance (identical guard to C2-B). This is exactly why the
  decision rule drops gate-failers *before* the weighted comparison — a high weighted total is moot
  once a gate fails.
- **C2-B (shipped, 4.45)** and **C2-E (4.45)** tie numerically, but C2-B is disqualified and C2-E is
  not, so the tie is irrelevant.
- **C2-A (2.35):** the pre-fix null; dead on GATE-S exactly as the prereg predicts (it proceeds at 1.0
  on the 2 unitless fixtures). Its failure confirms the corpus *does* express the C-2 defect.
- **C2-D (3.55):** lowest survivor-grade score; disqualified twice over — inherited silent-1.0 hole
  **and** the `--assert-length-unit` override never fires on a present-but-unresolvable unit (it looks
  "present"), **plus** the human-assertion re-opens the 1000× defect under operator error (spec-dinged).

### Residual risks / recommended follow-ups (C-2)
1. **WINNER IS UNBUILT.** Grep confirms only C2-A (pre-fix) and C2-B (shipped) exist in the repo; no
   granular `unit_state` / resolvability code. **C2-E's GATE-N over-rejection behavior is UNMEASURED**
   — if its supported-unit whitelist is too narrow it could reject valid foot/inch/mm and FAIL GATE-N.
   The recommendation is **conditional on implementing it and re-running the corpus**.
2. **Corpus gaps:** `expected_verdicts.json` has NO present-but-unsupported fixture and NO
   conversion-unit (foot/inch) fixture. GATE-S (the disqualifier) and the GATE-N foot clause are
   currently verified only by ad-hoc probes, not by the frozen corpus. Add
   `c2_contextdependent_unit` / `c2_bogus_unit` (expected `not_certifiable`) + `c2_foot` (expected
   `processes`) so both are regression-pinned.
3. **Harness masks GATE-X:** `eval_corpus.py` catches bare `Exception` and labels ANY exception
   "refused", so a clean classified refusal and an unhandled crash score identically — the C2-B-vs-C2-C
   operability delta is invisible to the differential.
4. **C2-B refusal is a RAW TRACEBACK (synthesizer-VERIFIED):** `python sandbox/checker.py
   research/corpus/adversarial/c2_no_unit.ifc` prints a full `ValueError` traceback and `EXIT=1` — but
   a violations run *also* exits 1, so an operator/CI cannot distinguish "refused: no unit" from "5
   violations" by exit code. (`run()` raises at `checker.py:597`; `main()` at `checker.py:642+` never
   catches it.) Whatever replaces C2-B should also fix this — the **C2-C operability increment**.
5. **Multi-project divergence (refuter major, unreproduced here, plausible):** `_has_length_unit`
   scans **all** `IfcProject`s (`checker.py:577`) while `calculate_unit_scale` uses `projects[0]` only
   — a multi-project file with LENGTHUNIT on a non-first project could pass the guard while scale
   resolves to 1.0. Low likelihood (IFC mandates one IfcProject) but a real present-yet-wrong-scale
   path.
6. **Present-but-WRONG unit (critic C2-I, missed candidate):** mm quantities mislabeled `METRE` — a
   residual 1000× false pass that **none** of the five candidates catch (all trust the declared unit).
   A magnitude-plausibility cross-check (habitable-room height band) is an orthogonal defense-in-depth
   layer; the §4 scale-invariance metamorphic (MR3 flips the unit LABEL without rescaling quantities)
   does not actually test scale-invariance, so this invariant is unverified.
7. **No held-out third-party mm/ft IFC** (prereg §4 gap) — all C-2 evidence derives from surgical
   mutation of the single FZK fixture.

### Recommendation (C-2)
**Adopt C2-E** (resolvability-based granular unit classification), **conditioned on** implementing it
and re-running the corpus. Required before merge: **(a)** validate that the project LENGTHUNIT resolves
to a defined, positive, finite, METRE-dimensioned scale — the critic's **C2-F** (harden
`_has_length_unit` into a resolvability check on top of C2-B) is effectively the same fix and is the
**minimal viable in-place form**, worth benchmarking against the full C2-E reframe; **(b)** add pinned
fixtures `c2_contextdependent_unit` / `c2_bogus_unit` (expected `not_certifiable`) + a foot/mm GATE-N
fixture; **(c)** re-run `eval_corpus` + metamorphic + mutation to confirm GATE-N (foot 0.3048 and mm
0.001 still process; FZK 5 / Institute 2 / Duplex 0,21 unchanged) before trusting it. Fold in the
C2-C classified-exit increment so the refusal is a clean signal, not a raw traceback.

---

## Methodology & bias controls

- **Preregistration-before-judging.** The question, candidate space, external oracle, metrics, hard
  gates, weights, and decision rule were frozen in `PREREG_C1_window_geometry.md` and
  `PREREG_C2_unit_scale.md` *before* candidate evaluation. No goalpost-moving; scoring used only the
  frozen rubric. The shipped fix (C1-B / C2-B) was entered as **one candidate**, never the
  baseline-of-correctness — and C2-B duly **lost**.
- **External oracle, not the circular control.** Correctness was judged against the IFC schema
  (`IfcPositiveLengthMeasure > 0`; the IFC unit model), the DM-1975 statute (aero numerator = valid
  windows only; unknowable scale ⇒ not-certifiable), and the pinned `expected_verdicts.json` —
  **never** the frozen control oracle (FZK 5/1 etc.), which are outputs of the current code and
  therefore circular for C-1/C-2 (PREREG §0).
- **Blind independent generation.** Separate judge / refuter / critic passes; the synthesizer
  re-derived every load-bearing number rather than trusting the reports.
- **Adversarial refutation.** A dedicated refuter constructed pathologies the corpus omits — the
  Qto-negative fixture (kills C1-E) and the `IfcContextDependentUnit` LENGTHUNIT (kills C2-B); the
  critic surfaced missed candidates (C1-F/G, C2-F/G/H/I) and unverified claims. A refuter-confirmed
  disqualifier counts even when the frozen corpus cannot express it.
- **Frozen decision rule.** Drop gate-failers first; pick max weighted; apply the 0.3 stability clause
  only to a *surviving* shipped fix; record all scores and negatives (no file-drawer). C1-B won
  outright (Δ 0.55 > 0.3, clause not needed); C2-B was disqualified so the clause could not save it.
- **Mutation & metamorphic guards.** `test_mutation.py` (6/6) re-injects the C-1/C-2/H-1 bugs and
  asserts the mutants fail — proving test *power*, not mere presence. `test_metamorphic.py` (4/4)
  asserts oracle-free invariants (a non-conformant window only moves a verdict toward
  undetermined/violation; a unitless model is refused; a declared-mm model processes).

## Limitations (honest)

- **No held-out real-IFC coverage.** PREREG §4 asks for an open-repo IFC4 file with populated window
  Qto (C-1) and third-party mm/ft files (C-2) as blind generalization checks; none were obtainable
  this round. All C-1/C-2 evidence derives from the 3 in-repo fixtures + surgical mutations of FZK.
  The 0.25-weight correctness-on-held-out criterion is scored on zero held-out evidence.
- **Two winners are partly evaluated on reasoning, not full builds.** C1-C/C1-E and C2-E/C2-D are
  unimplemented; their gate calls rest on probes + design reasoning. **The C-2 recommendation (adopt
  C2-E) is explicitly conditional on building it and re-running the corpus** — its GATE-N
  over-rejection behavior is unmeasured.
- **The differential harness cannot distinguish a classified refusal from a crash** (`eval_corpus.py`
  catches bare `Exception`), so GATE-X operability deltas are invisible to it and were checked by
  direct CLI runs instead.
- **The frozen corpus is incomplete against its own §4 minimum set** (no Qto-negative, NaN/inf,
  present-but-unsupported, or conversion-unit fixtures); several disqualifiers are refuter-built rather
  than corpus-pinned and should be added before the next cycle.
