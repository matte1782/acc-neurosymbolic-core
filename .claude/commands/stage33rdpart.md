---
description: "Stage 3 · Part 3 — geometry fallback (height/area/window-containment) for the no-quantity class (Revit Duplex's 21 undetermined spaces). WRITES production code. Geometry is a strict, ground-truth-validated fallback: it fires only when key-lookup returns None, is proven on FZK/Institute (Qto known) before it is trusted on Duplex, and stays `undetermined` rather than fabricate a pass. First hardens the `compliant` property so a partial (height-without-aero) result can never silently pass."
---

# Stage 3 · Part 3 — Geometry fallback for the no-quantity class (WRITES production code)

Repo: `acc-neurosymbolic-core` (Slice A). Parts 1 (`/stage31stpart`, baseline) and 2 (`/stage32ndpart`,
mechanical hardening) are **done**. Part 3 closes the **remaining baseline gaps** —
`STAGE3_BASELINE.md` Gap 2 *geometry half* (height), Gap 3 (area), Gap 4 (window-by-containment) —
for the **no-quantity class** of files (Revit **Duplex**: 21/21 spaces `compliant=None` → today reads
"0 violations, 21 undetermined / not certifiable"). A *meaningful* Duplex verdict needs quantities
derived from the **3D geometry** when Qto/Pset/boundaries are absent or semantically wrong.

> **This is the highest-risk change in the project.** It derives compliance-determining numbers from
> geometry, which is wrong-number-prone (gross-vs-net height, GSA/BOMA-vs-net area, wrong window→room
> mapping, unit-scale slips). The command is built around ONE principle: **geometry is a strict fallback
> validated against ground truth.** (i) It fires *only* when key-based lookup returns `None`, so
> FZK/Institute — which resolve via Qto — are **physically untouched**. (ii) Each geometry method is
> **proven on FZK/Institute** (where the Qto answer is *known*) *before* it is trusted on Duplex (where it
> is the *only* source). (iii) If geometry cannot produce a defensible **net** quantity, the space **stays
> `undetermined`** — an honest "not certifiable" is the correct output; a fabricated *or* incomplete
> number that flips a real violation to a pass is the worst possible defect.

> **Working directory.** Run everything from the repo root
> `C:/Users/matte/Desktop/Desktop OLD/AI/Università AI/courses/personal_project/industrial.review/acc-neurosymbolic-core`.
> If the session started elsewhere, `cd` there first. Paths below are relative to it; checker/test
> commands run from `sandbox/`.

## BOOT (read first)
`docs/decisions.md` (ADR chain = memory; **ADR-003** newest), `sandbox/STAGE3_BASELINE.md` (Gaps 2/3/4 +
the numbers you must preserve; the Duplex "no usable Qto / `Unbounded Height` is floor-to-floor" finding;
the §152-157 untracked-report housekeeping note), `CLAUDE.md`, `ROADMAP.md` Stage 3 (`:90-108`),
`sandbox/checker.py` (the file you edit), `sandbox/tests/test_height_keys.py` (the offline
`get_psets`-mocking unit-test pattern — note it mocks the **Qto** surface, *not* `ifcopenshell.geom`).

## START CONTROLS (run first — if any is off, STOP: env/regression, not Stage 3)
From `sandbox/`:
- `python tests/test_gate.py` → **19/19**; `python tests/test_height_keys.py` → green.
- `python checker.py data/AC20-FZK-Haus.ifc --json data/AC20-FZK-Haus_report.json` → **5**; `--salva-casa` → **1**.
- `python checker.py data/AC20-Institute-Var-2.ifc --json ...` → **2**; `--salva-casa` → **2**.
- The 3 fixtures must be on disk (git-ignored `data/*.ifc`). If a `data/*.ifc` is missing, re-acquire per
  the Part-2 URLs (FZK in-repo; Institute from steptools; Duplex from the **media.githubusercontent.com**
  LFS endpoint — the raw/gh-raw URLs return a 132-byte pointer). See `stage32ndpart.md:22-27`.
- **Geometry API present:** `python -c "import ifcopenshell, ifcopenshell.geom; print('geom OK')"` →
  `geom OK`. (Confirmed available 2026-06-18, ifcopenshell 0.8.5.) **Part 3 cannot proceed without it** —
  if it fails, STOP: env problem, not a code change.
- **CAPTURE THE CONTROL VIOLATION IDENTITIES (not just counts).** From the START reports, record the
  **set of `global_id`s** of the violating spaces for FZK (the 5) and Institute (the 2 — the spaces named
  **`402`/`403`**), in **both** modes. These GlobalId sets — not the integer counts — are the frozen
  anchors below (a count-only check cannot catch a violation-*set swap*).
- **Pre-existing dirty tree (do NOT touch / do NOT revert):** `sandbox/parser.py` and
  `sandbox/rules/compiled/dm_1975_salva_casa.json` are already **modified** (uncommitted Stage-2/Part-2
  work, per ADR-002/003 "not yet committed"); `STAGE3_BASELINE.md` and `tests/` are untracked. Leave them
  as-is — Part 3's diff is **only** the additional `checker.py` + new `tests/` (+ the final ADR/ROADMAP).

## HARD RULES
- **Edit `sandbox/checker.py` only** (+ focused tests under `sandbox/tests/`). Do NOT touch `parser.py`,
  the law `.md`, the compiled rule JSON, or `ROADMAP.md` mid-edit (the ROADMAP flip + ADR-004 happen
  **after** the full regression+validation is green, per the update protocol). `.gitignore` is an allowed
  write (housekeeping below).
- **Fix the code, not the harness.** Never weaken a check, the gate, or a control to make a number pass.
  **Never fabricate — *or partially complete* — a geometry quantity to clear an `undetermined`.**
- **GEOMETRY IS A STRICT FALLBACK.** It MUST fire **only when the existing key-based lookup returns
  `None`**. Wire it as `val = <existing key lookup>; if val is None: val = <geometry lookup>` — never
  reorder so geometry runs first, never let it override a non-None Qto. ⇒ FZK/Institute cannot move.
- **GEOMETRY OUTPUT IS ALREADY IN METRES — DO NOT APPLY `scale`.** `ifcopenshell.geom.create_shape`
  returns vertices in **SI metres** (`convert-back-units` defaults `False`), regardless of model unit. The
  `_qty` `scale**power` convention (`checker.py:123`) applies **only** to raw *Qto attribute* values
  (native units) — **never** to geom output. Multiplying geom output by `scale`/`scale**power` is a silent
  1000×/1e6× error on a non-metre (e.g. mm Revit) export that the FZK/Institute/Duplex fixtures (**all
  `scale=1`**) **cannot** catch — so it must be prevented by rule **and** by the synthetic mm-unit test
  below, not by the live cross-check.
- **VALIDATE-BEFORE-TRUST.** No geometry-derived quantity is trusted on Duplex until the *same function*
  reproduces the **known Qto value** on FZK & Institute within the Phase-0 tolerance, **for the same
  geometric class** (prismatic vs sloped). If it disagrees on the ground-truth fixtures, the method is
  wrong — fix it, don't proceed.
- **COMPLIANT-COMPLETENESS (Task A0 makes this true, then it MUST hold).** A space may read
  `compliant=True` **only if every check *applicable to its occupancy* was actually evaluated**:
  habitable/unknown need **both** `height_ok` *and* `aero_ok` non-None; accessory needs `height_ok`
  (aero is N/A). If any applicable check is `None`, `compliant` is `None` (**undetermined**) — never a
  pass on partial evidence. (Closes the hole where a real geometry *height* alone flips a habitable space
  to compliant while its 1/8 aero ratio was never checked.)
- **PRODUCTION-SAFETY INVARIANT (unchanged from Part 2).** Never silently mark an unmeasurable space
  COMPLIANT. A geometry result that is **missing, out of sane bounds, a known-wrong quantity, or
  incomplete (one applicable check still None)** ⇒ the space **stays `undetermined`** with a note.
- **One task at a time, in order.** Run the full **REGRESSION BLOCK** after EACH task and confirm the
  frozen invariant before the next. If a control moves, revert that task and stop.
- **Observation separate from interpretation**; cite `checker.py:<line>` in the commit/notes per change.

## REGRESSION BLOCK (run after EVERY task — from `sandbox/`)
```
python tests/test_gate.py                                                                 # MUST be 19/19
python tests/test_height_keys.py                                                          # Qto key precedence — MUST stay green
python tests/test_geometry_fallback.py                                                    # NEW (Task A0 onward) — compliant-completeness + geom gate + unit + cross-check
python checker.py data/AC20-FZK-Haus.ifc        --json data/AC20-FZK-Haus_report.json         # viol MUST be 5  (same GlobalId set)
python checker.py data/AC20-FZK-Haus.ifc --salva-casa --json data/AC20-FZK-Haus_report_sc.json # viol MUST be 1  (same GlobalId set)
python checker.py data/AC20-Institute-Var-2.ifc --json data/AC20-Institute-Var-2_report.json   # viol MUST be 2 = spaces 402/403
python checker.py data/AC20-Institute-Var-2.ifc --salva-casa --json data/AC20-Institute-Var-2_report_sc.json # viol MUST be 2 = 402/403
python checker.py data/Duplex_A_20110907.ifc    --json data/Duplex_A_20110907_report.json      # CHANGES (see below); exit != 0 EXPECTED
python checker.py data/Duplex_A_20110907.ifc --salva-casa --json data/Duplex_A_20110907_report_sc.json # CHANGES; modes may DIVERGE; exit != 0 EXPECTED
```
**Frozen invariant (geometry fires only on `None`):** `test_gate.py` **19/19**, the Qto + geometry unit
tests green, and the violating-space **GlobalId sets** for **FZK** (5) and **Institute** (`402`/`403`,
both modes) are **byte-identical to the START capture** — assert the *identities*, not just the counts
`5/1` and `2/2`. **If a FZK/Institute violation count *or* its GlobalId set moves, the fallback leaked into
a Qto-bearing space → revert that task.**
**Duplex is the only fixture allowed to change**, and only *after* its quantities are Phase-0-validated:
`spaces_undetermined` drops from **21** only for spaces that got a **validated** quantity; the rest **stay
undetermined** (honest). The two Duplex modes may **legitimately diverge** once Task A lands a net height
(habitable bar drops 2.70 m → 2.40 m under `--salva-casa`, `checker.py:186-188`) — **report both**, with
per-space height; **neither Duplex number is a frozen control.** Duplex's process exit is **expected
non-zero** while any space is undetermined/violating (`checker.py:289`) — that is correct, not a
regression; key the control check off the printed counts + `spaces_undetermined`, never the raw `$?`.

---

## PHASE 0 — ENV + METHOD PROBE (READ-ONLY on `checker.py`; MANDATORY; use the Workflow tool)
**This is the make-or-break.** Do NOT write production code until Phase 0 decides, *per quantity*,
whether geometry yields a defensible **net** number for Duplex. Invoking this command is the opt-in to run
a Workflow: a parallel probe across the 3 fixtures, then an orchestrator VERIFY that re-derives every
number from artifacts (untrusted-subagent stance — admit an agent's number only if it pasted the command +
raw stdout; re-compute it yourself). Probe (read-only; may write `sandbox/probe_*.py` scratch + the
deliverable note, never `checker.py`):

1. **`create_shape` works?** Per fixture: `settings = ifcopenshell.geom.settings()`,
   `ifcopenshell.geom.create_shape(settings, space)` on real `IfcSpace`s; capture per-fixture
   success/failure (+ traceback). A fixture whose spaces can't be shaped ⇒ its spaces **stay
   undetermined** (recorded), not a crash.
2. **Enumerate the REAL API — do NOT assume signatures.** Paste `dir(ifcopenshell.util.shape)` and
   `help(...)` for the helpers actually present in 0.8.5. Verified-present names to confirm:
   `get_z` (= **max−min Z extent**, i.e. it **overestimates** sloped/vaulted ceilings — see step 3),
   `get_footprint_area`, `get_bbox`, `get_bbox_centroid`, `get_volume`, `get_vertices`. ⚠️ *Do not* use
   `get_element_bounding_box` (it does **not** exist in 0.8.5). Fallback for a raw Z-extent: `verts`
   reshaped to `(-1,3)`, `zmax−zmin`. **State the unit rule in the note: geom output is metres; no `scale`.**
3. **GROUND-TRUTH CROSS-CHECK (the core of Part 3's validity).** FZK & Institute spaces **have Qto
   `Height` and area**. For each, compute geometry height (Z-extent) and geometry footprint area, and
   **tabulate geometry-vs-Qto per space** (paste the table). **Classify each space prismatic vs
   non-prismatic** and investigate every divergence before trusting the method — e.g. FZK space `7` has
   Qto `Height=4.0` but a sloped/galerie ceiling, so `get_z` over-reads (~3.4–4.0); a percentage alone
   hides this. Pick the tolerance **per geometric class**, not globally.
4. **DUPLEX NET-vs-GROSS GATE (the critical correctness question).** For each Duplex space compute the
   geometry Z-extent **and** read `PSet_Revit_Dimensions."Unbounded Height"` (the floor-to-floor span the
   baseline rejected). **`Z-extent ≈ Unbounded Height` ⇒ geometry is the SAME gross quantity ⇒ height
   STAYS undetermined for Duplex** (honest; record it). **`Z-extent meaningfully smaller`** is **necessary
   but NOT sufficient** to call it net: it could exclude only the upper slab while still including a
   raised-floor/finish zone or a Revit *Limit Offset*. It may be trusted as net **only if** the *same*
   geom method reproduced the known Qto **net** height on FZK/Institute within tolerance **for the same
   geometric class**. **Absent an independent net ground truth for Duplex, default to `undetermined` even
   when `Z-extent < Unbounded Height`.** Ask the same net-vs-gross question of the geometry **area**.
5. **Window-by-containment feasibility.** On FZK/Institute the `space.BoundedBy` mapping is *known*. Test
   whether a containment rule reproduces it **exactly**: window position inside the space's **world-XY**
   *footprint* — use **world coordinates** (`settings.set("use-world-coords", True)` and *verify*
   `settings.get("use-world-coords")` is `True`, or transform local verts by the `ObjectPlacement`
   matrix), restricted to the **same storey**, and tested as **point-in-footprint-polygon** (or window
   centroid in the projected footprint), **not** a 2D bbox (a bbox over-reads on L-shaped/non-rectangular
   rooms and can mis-assign a window). Quantify adds/drops vs the boundary mapping; **one** mis-assign on a
   ground-truth fixture means the rule is not safe to ship.

**Deliverable:** `sandbox/STAGE3_PART3_PROBE.md` (artifact-grounded, numbers pasted) that **DECIDES, per
quantity (height / area / window)**: "geometry trustworthy for Duplex within tol X, validated on
FZK/Institute class Y" **or** "must stay undetermined — reason". **Tasks A/B/C below are CONDITIONAL on
this note: implement a fallback ONLY for the quantities Phase 0 proved sound.** A quantity Phase 0 cannot
validate is *not* a failure — it is a correct, honest `undetermined`, and you skip its task.

## TASK A0 — compliant-completeness (SAFETY KEYSTONE — do FIRST; verdict-neutral on all current fixtures)
- **Target:** `SpaceFinding.compliant` (`checker.py:96-99`).
- **Gap:** `compliant` returns `all(checks)` over only the **present** (non-None) checks, so a
  habitable/unknown space with one applicable check resolved and the other `None` reads `True` — a silent
  pass on partial evidence. Part 3 makes this reachable with a **real** number (Task A height without Task
  B area, or vice-versa), so the anti-fabrication rules don't catch it. **Land this BEFORE any geometry**
  so every later task is safe to ship incrementally.
- **Change (single concern):** make `compliant` occupancy-aware — required checks are `{height_ok}` for
  `accessory` (aero N/A) and `{height_ok, aero_ok}` for `habitable`/`unknown`; if **any required check is
  `None` ⇒ return `None`** (undetermined); else `all(required)`.
- **Verdict-neutral proof (must hold):** on the current fixtures every habitable/unknown space already has
  **both** height and area evaluated (so both non-None) and every accessory has height — so no current
  space changes class. **Expected delta: FZK 5→1, Institute 2→2 (same GlobalId sets), Duplex 0 viol /
  21 undetermined — ALL UNCHANGED.** If any moves, the occupancy mapping is wrong — revert.
- **Acceptance:** unit test in `tests/test_geometry_fallback.py` — a habitable `SpaceFinding` with
  `height_ok=True, aero_ok=None` asserts `compliant is None` (not `True`); an accessory with
  `height_ok=True, aero_ok=None` asserts `compliant is True`; a habitable with both `True` asserts `True`.
  Run it + the full REGRESSION BLOCK; confirm the frozen GlobalId sets.

## TASK A — geometry-derived HEIGHT fallback  *(implement only if Phase 0 validated net height)*
- **Target:** `space_height()` (`checker.py:129-137`).
- **Change (single concern):** after the `_SPACE_HEIGHT_KEYS` loop returns `None`, try a geometry Z-extent
  helper — gated on `create_shape` success **and** sane bounds (≈ 2.0–4.0 m) **and** the Phase-0
  net-not-gross + same-class finding. Key first, geometry second; first non-None wins. **Geom output is
  metres — do NOT multiply by `scale`.** Return `None` (not a guess) on shape failure / out-of-bounds /
  not-net.
- **Acceptance (test must actually exercise geometry):** in `tests/test_geometry_fallback.py` — (i) call
  the geometry helper **directly** on a real FZK/Institute space and assert it ≈ the Qto value within the
  Phase-0 tolerance (do **not** route through `space_height`, which returns at the Qto key loop and never
  reaches geometry); (ii) **spy** that a Qto-bearing space's `space_height()` returns **without calling
  `create_shape`** (patch the geom helper to raise; assert the Qto value still returns); (iii) a
  **synthetic mm-unit** case (mock `scale=0.001`) asserts the geometry path returns ~2.5, **not** ~2500 or
  ~0.0025 (guards the unit-scale double-application the live fixtures can't). Run it + the REGRESSION BLOCK.
- **Expected delta:** **FZK 5→1, Institute 2→2 (frozen GlobalId sets)**; Duplex `height_m` populated only
  for the spaces Phase 0 cleared, `None` for the rest (which stay undetermined via Task A0).

## TASK B — geometry-derived AREA fallback  *(implement only if Phase 0 validated net area)*
- **Target:** `space_floor_area()` (`checker.py:140-145`) + the **call site** `check_space` (`checker.py:183`).
- **Wiring (avoid the `if val:` 0.0-trap):** do **not** add geometry inside `space_floor_area` (it uses
  `if val:`, 0.0-falsy, `checker.py:143`, which would conflate a 0.0 geom result with "no Qto"). Gate at
  the **call site**: `area = space_floor_area(space, scale); if area is None: area = _geometry_area(space, settings)`.
  Leave the existing `if val:` inside `space_floor_area` unchanged. The geometry helper returns a
  footprint area **validated in Phase 0 to be the floor area (not total surface area)**, gated on shape
  success + sane bounds + net-not-gross, and **returns `None` (never 0.0)** on any failure — so the
  existing `if area else None` aero guards (`checker.py:197, 212`) keep the space undetermined. **Geom
  output is metres — no `scale`.**
- **Downstream:** once area resolves, the **8** Duplex window-resolved spaces (baseline §Duplex) get a
  real `aero_ratio` (`checker.py:197`). The 13 windowless spaces depend on Task C; until then they stay
  undetermined via Task A0 (aero_ok None), **not** a pass.
- **Acceptance:** unit test vs FZK/Institute Qto area within tolerance (call helper directly); spy that a
  Qto-bearing space never hits geometry; mm-unit synthetic case (~area, not ×1e6). Run it + REGRESSION BLOCK.
- **Expected delta:** controls **frozen** (GlobalId sets); Duplex `floor_area_m2` + `aero_ratio` populated
  where validated.

## TASK C — window-by-containment fallback  *(implement only if Phase 0's mapping was EXACT; HIGHEST risk)*
- **Target:** `windows_serving()` (`checker.py:166-177`, the `TODO` at `:169-170`).
- **Direct control-leak risk (why this is the most dangerous task):** Institute's frozen violations
  `402`/`403` violate **precisely because `win=0`** — the exact condition Task C's fallback fires on. A
  containment **mis-assign that gives 402/403 a window would erase a real code violation** (worst defect),
  and a count-only check would hide it if a different aero violation surfaced elsewhere — which is why the
  frozen invariant pins **GlobalId sets**.
- **Change (single concern):** when `space.BoundedBy` yields **no** `IfcWindow`, associate `IfcWindow`s by
  **storey-scoped, world-XY point-in-footprint** containment (world coords **verified** `True`, or
  `ObjectPlacement`-transformed; footprint polygon, **not** bbox). Keep the boundary path first; this is
  the fallback only. **Conservative:** if association is ambiguous, count `0.0` — understating windows
  surfaces as an aero note / `undetermined`, **never** a false pass. Use a window shape with the **correct
  world frame** — do **not** reuse a non-world-coords shape from Task A/B.
- **Acceptance (HARD):** on FZK/Institute the containment mapping **must equal** the boundary mapping
  (a per-space **add/drop diff that is empty — zero new assigns**) **and** the frozen GlobalId sets hold
  (Institute stays exactly `402`/`403`). If containment can't be made exact on the ground-truth fixtures,
  **drop Task C** and leave those Duplex spaces `undetermined`.
- **Expected delta:** controls **frozen**; Duplex windowless-but-actually-windowed spaces resolve their
  `win`/`aero`.

---

## AFTER TASKS — Duplex re-evaluation + honesty check
Re-run Duplex (**both** modes). `spaces_undetermined` drops from 21 to `21 − (validated-measurable
count)`; the remainder **stay undetermined** because geometry couldn't give a defensible net quantity —
that is **correct, not a shortfall**. Report **both** Duplex `violations` numbers (base + `--salva-casa`,
which may legitimately diverge around the 2.40–2.70 m band) and `spaces_undetermined`, and state, per
space class, *why* each space is now determined or still undetermined. The verdict must be **meaningful**
(real numbers from validated geometry) **or** honestly **undetermined** — never fabricated or partial.
Re-confirm the production-safety invariant from the report JSON: **no `finding` has `compliant==true`
while a check applicable to its occupancy is `null`** (machine-checkable; Task A0 enforces it).

## DECIDE / ROADMAP / ADR (only after the full regression + validation is green)
- **If geometry validated and Duplex now yields a meaningful verdict** → flip Stage 3 **🟢→✅** ("verified
  on real data across tools, incl. the no-quantity class") + **ADR-004** + Iteration-Log line.
- **If Phase 0 showed Duplex height/area are irrecoverably gross-only** (geometry ≈ `Unbounded Height`, or
  no independent net ground truth) → Stage 3 **stays 🟢** with a recorded, defensible finding: *"the
  no-quantity/gross-only class is honestly undetermined; ✅ on this class requires a fixture carrying net
  geometry."* **ADR-004** records THAT result. Either close is legitimate — **state which and the
  evidence.** (Exactly **one** ROADMAP touch, after green, per the update protocol.)

## DONE-WHEN (Part 3)
1. `sandbox/STAGE3_PART3_PROBE.md` written (artifact-grounded; per-quantity net-vs-gross decision for
   Duplex + the chosen per-class tolerance + the containment add/drop diff).
2. `checker.py`: Task A0 (compliant-completeness) landed first; geometry fallbacks added **only** for
   Phase-0-validated quantities, each single-concern, **strictly gated on key-lookup-`None`**, **never
   `scale`-multiplying geom output**, citing `checker.py:<line>`; new `tests/test_geometry_fallback.py`
   (geom gate + spy + mm-unit + Qto cross-check).
3. REGRESSION BLOCK green after every task: `test_gate.py` 19/19, the unit tests green; **FZK and
   Institute violation GlobalId sets FROZEN** (identities, both modes), Institute = `402`/`403`; the
   geometry method validated against FZK/Institute Qto ground truth within the Phase-0 per-class tolerance
   (cite the table).
4. Duplex re-evaluated in **both** modes: undetermined dropped only for **validated** spaces; remaining
   undetermined honest; **machine-checked** that no finding is `compliant==true` with an applicable check
   `null`; `$?` non-zero while any space is undetermined.
5. **Per-space validation link (no laundering):** for every Duplex space whose `compliant` is no longer
   `None`, its report note carries the geometry-source tag, the `STAGE3_PART3_PROBE.md` row that authorized
   it, and the orchestrator re-derives that space's geometry number from raw `create_shape` stdout (paste
   command + stdout, exactly as Phase 0 mandates). A flipped space lacking a re-derivable artifact number
   is **reverted to undetermined**.
6. ROADMAP flip + **ADR-004** + Iteration-Log line **after** green, recording whichever close (✅
   meaningful, or 🟢 honest-undetermined) the evidence supports.
7. **Housekeeping (baseline §152-157):** the `data/*_report.json` reports, `sandbox/probe_*.py` scratch,
   and `STAGE3_PART3_PROBE.md` are **expected UNTRACKED** diagnostic artifacts — the production diff is
   `checker.py` + `tests/` + the final ADR/ROADMAP edits **only**. Optionally add `data/*_report.json` and
   `sandbox/probe_*.py` to `.gitignore` (allowed write). Do not commit diagnostic junk; do not be confused
   by the pre-existing modified `parser.py`/JSON.
8. `.idos/events.jsonl`: append ONE line in the fixed schema (see `.idos/FRAMEWORK_BASELINE.md`), ≤30
   words, **only** on a real STOP/GATE/DEFECT during implementation.
Then **STOP** and hand back: the diff, the regression output (with the frozen GlobalId sets), the Phase-0
net-vs-gross decision, and the new Duplex verdict in both modes (meaningful or honestly undetermined, with
the per-class reasons).
