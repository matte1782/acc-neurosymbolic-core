# PREREGISTRATION — C-1b: trustworthy-window aero semantics (C1-F absurd-area + windows_serving laundering)

> **FROZEN BEFORE candidate generation/judging.** Same bias-resistance contract as `PREREG_C1`/`C2`
> §0. These two audit residuals are **coupled** — both hinge on "what the aero check does when a
> serving window's area cannot be trusted" — so they are decided together. The already-shipped code
> (`C1-B` positivity guard + the `or 0.0` laundering) is entered as the null/incumbent, not the default.

## 0. The bias this design fights + the grounded facts that constrain it
The frozen control oracle is circular and all conformant windows are plausible, so it cannot see
either residual. Ground truth = **physics** (a window cannot have absurd area; the aero ratio
`openable/floor` with an unmeasurable term is only a *lower bound*) + **ADR-003** (unmeasurable ⇒
`undetermined`, never a laundered value or a guessed verdict). **Measured facts (probe 2026-06-29,
must be honored by any candidate):**
- **Attribute area (`OverallHeight×OverallWidth`, a bounding box) legitimately differs from the Qto
  net glazing area** — FZK windows show `attr 1.0` vs `Qto 0.785` (~21%). ⇒ **an attr==Qto equality
  cross-check is INVALID** (it would flag real windows). Any cross-check must tolerate this, and
- **cross-check coverage is uneven:** FZK 11/11 and Institute 206/206 carry both paths, **Duplex
  0/24** (Revit emits no window Qto Area) ⇒ a cross-check has nothing to check on Duplex.
- The C1-F target space `2dQFggKBb1fOc1CqZDIDlx` has **2 serving windows** (1.0 m² each), floor
  74.509 m², aero 0.0268 (< 0.125, a violation). A `500×500` window → 250000 m² → ratio passes →
  space flips **compliant** (FZK 5→4) — a residual false-pass `C1-B` does not catch.

## 1. Questions (falsifiable, coupled)
**(C1-F)** How to detect a serving window whose area is non-physical on the **upper** side (absurd
positive — the positivity/finiteness lower side is already `C1-B`), without over-rejecting real
windows (incl. the legitimate ~21% attr/Qto gap and Duplex's Qto-less windows)?
**(Laundering)** How should the aero check treat a serving window whose area is untrustworthy
(non-positive, non-finite, absurd, or unmeasurable)? Today `windows_serving` does
`total += window_area(elem) or 0.0` (`checker.py:442`), silently coercing an unmeasurable window to a
*measured* 0.0 and reporting a definite verdict — violating ADR-003.

## 2. External ground truth (code-independent oracle)
- **Physics:** total openable window area cannot exceed what the room can hold; a single window with
  area ≫ the floor it serves is implausible. The aero ratio over an unmeasurable numerator term is a
  **lower bound**, not a point value.
- **Statute (DM 1975 art.5):** habitable aero = openable/floor ≥ 1/8; the numerator must be the area
  of **trustworthy** windows.
- **ADR-003 keystone:** if the aero ratio cannot be bounded to a definite pass/fail, the space is
  `undetermined` (compliant=None), never a laundered pass **or** a guessed fail.

## 3. Candidate space (the shipped behavior is the null; ≥3 genuinely different per sub-decision)
**Upper-bound detection (C1-F):**
- **F-A — null/incumbent:** no upper bound (the documented residual; must FAIL GATE-S).
- **F-B — absolute per-window cap:** reject a window whose area exceeds a fixed large constant.
  (Calibration-arbitrary; magic constant.)
- **F-C — relative-to-floor plausibility:** in `check_space`, a serving-window total exceeding the
  floor area (ratio > 1, physically impossible for openable area) ⇒ the windows are untrustworthy.
  Calibration-light; uses the room's own scale. (Edge: a small room with a large window wall — assess.)
- **F-D — attr↔Qto tolerance-band cross-check:** trust a window only if `attr` and `Qto` agree within
  a generous band (e.g. 0.5×–2×, honoring the measured 21% gap); fall back to a plausibility bound
  where only one path exists (Duplex). (Most complex; band is itself a calibration.)
- **F-E — ratio cap:** clamp the aero ratio numerator at the floor area (ratio ≤ 1) silently. (Hides
  the anomaly rather than surfacing it — assess against ADR-003 honesty.)

**Untrustworthy-window aero semantics (laundering):**
- **L-0 — null/incumbent:** `None → 0.0`, report a definite verdict (over-strict false-FAIL + masks).
- **L-1 — strict undetermined:** any untrustworthy serving window ⇒ aero `undetermined`.
- **L-2 — lower-bound (precise):** aero **passes** if the trustworthy windows alone clear 1/8; else
  if any window is untrustworthy ⇒ `undetermined`; else (all trustworthy, bar not cleared) ⇒
  violation. Fewer undetermined, ADR-003-faithful in both directions.

## 4. Evaluation sets
- **Adversarial corpus** (extend `gen_adversarial.py`; pinned expected in `expected_verdicts.json`):
  - `c1_absurd_pos_window` — target window set to 500×500. **Expected: space NOT compliant**
    (undetermined under L-1/L-2, since the window is untrustworthy). Differential: incumbent →
    compliant (FZK 5→4, false pass).
  - `c1_neg_window` — **re-pinned**: under the laundering fix the target's negative window is
    untrustworthy and the trustworthy window (1.0/74.5 = 0.013) cannot clear the bar ⇒ **space
    undetermined** (FZK viol=4, undet=1), the honest outcome. (The old pin viol=5 encoded the
    laundering bug.)
  - `c1_unmeasurable_partial` — a space with one trustworthy + one absurd window where the
    trustworthy area alone already clears 1/8 ⇒ **L-2 must PASS** (lower bound already satisfied),
    distinguishing L-2 from L-1. (If no fixture space naturally fits, construct or record as a gap.)
- **Conformant control set:** the 3 fixtures + frozen controls — **GATE-N**: byte-identical
  (FZK 5/1, Institute 2/2 on 402/403, Duplex 0/21). The ~21% attr/Qto gap must NOT cause any flip.
- **Oracle-free:** extend `test_metamorphic.py` — an absurd window may only move a verdict toward
  undetermined/violation (never compliant); extend `test_mutation.py` — re-inject `or 0.0` laundering
  and the no-upper-bound and assert the mutants fail.

## 5. Objective function (frozen) + HARD GATES
**Gates (disqualifying):**
- **GATE-S:** 0 false-pass on the C-1b corpus — `c1_absurd_pos_window`'s target must never read
  compliant.
- **GATE-N:** conformant fixtures + frozen controls byte-identical, AND no over-rejection caused by
  the legitimate attr/Qto gap or by Duplex's Qto-less windows (no conformant space flips to
  undetermined/violation).
- **GATE-X:** no unintended crash; a classified `undetermined` is the intended signal.
**Weighted (0–5) among survivors:** coverage/safety-margin .30, correctness/no-new-false-fail .25,
spec-faithfulness (physics + ADR-003 honesty) .15, simplicity/maintainability .15, operability
(clear "why undetermined" diagnostic) .10, performance .05. **Optimal = max weighted; record all.**

## 6. Decision rule (frozen)
Drop gate-failers; pick the max weighted (an upper-bound candidate × an aero-semantics candidate may
be chosen together as one coherent fix); no incumbent to protect (the nulls F-A/L-0 are the
disqualified status quo, so no stability clause applies). Record negatives →
`research/DECISION_MATRIX.md` (append a C-1b section). Implementation follows the decision.

## 7. Falsification criteria
A candidate dies if it (a) lets `c1_absurd_pos_window` pass (GATE-S), (b) flips any conformant verdict
— especially via the 21% attr/Qto gap or Duplex's one-path windows (GATE-N), (c) crashes (GATE-X), or
(d) reports a definite verdict where the aero ratio is genuinely unbounded (ADR-003 violation). The
nulls F-A/L-0 are expected to fail; if the corpus cannot demonstrate that, it is inadequate and must
be strengthened before judging.
