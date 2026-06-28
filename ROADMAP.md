# Production Roadmap — `acc-neurosymbolic-core`

> **Single source of truth for build progress.** This file guides the whole production path
> from sandbox prototype to a scalable, graph-anchored compliance engine.
>
> **Update protocol (mandatory, minimal).** Every iteration that changes the system updates
> this file in TWO touches and no more:
> 1. flip the affected stage **Status** (and the at-a-glance table);
> 2. add **one line** to the *Iteration Log* at the bottom.
>
> Nothing ships without a roadmap touch. Rationale: keep the process ordered and avoid *«un
> programma bello da vedere ma pieno di errori»* — a demo that looks good but is full of bugs.

**Status legend:** 🔴 not started · 🟡 in progress · 🟢 done · ✅ done + verified on real data

## Progress at a glance

| Stage | Title | Done when… | Status |
|---|---|---|---|
| 0 | Foundation — research baseline + sandbox prototype | Pipeline halves run end-to-end at €0 | ✅ |
| 1 | **Dynamic wiring** — parser JSON drives the checker | Edit the law text → verdict changes, no `.py` edit | ✅ |
| 2 | **Local brain** — Ollama, 100% offline | Internet off → full cycle runs at €0 locally | ✅ |
| 3 | **Multi-software robustness** — stress test | Clean verdict, no runtime errors, on ≥3 IFC from different tools | 🟢 3/3 |
| 4 | **Generalize + verify** — record-backed model, gate-verified applicability/selection, a real 2nd rule (monostanza), **no graph** | Model admits a 2nd rule at every layer; applicability/selection gate-verified; monostanza honest-undetermined | 🟢 |
| 4b | **Graph anchoring** — Knowledge Graph | Checker queries the graph, not a flat file | 🟢 *(seam built — ✅ at scale)* |

---

## Stage 0 — Foundation ✅ *(done + verified)*

Research baseline and a working sandbox proving the neuro-symbolic bridge on one real rule.

- **Delivered:** `research/FACTUAL_BASELINE.md`; `sandbox/parser.py` (NL → RASE rule JSON,
  pydantic-validated, offline fallback); `sandbox/checker.py` (IfcOpenShell → deterministic
  height + aeroilluminating checks); rule `sandbox/rules/dm_1975_salva_casa.md`.
- **Verified:** `ifcopenshell` 0.8.5 / Python 3.13 on `AC20-FZK-Haus.ifc` →
  baseline **5 violations**, `--salva-casa` **1 violation** (residual = true window-ratio failure).
- **Known limitation that opens Stage 1:** the two scripts do **not** talk. `checker.py`
  thresholds (2.70 / 2.40 / 0.125) are still **hard-coded Python constants**; the parser's
  JSON is not consumed.

---

## Stage 1 — Dynamic wiring (low-code) ✅ *(done + verified)*

- **Goal:** editing only the law text (`rules/dm_1975_salva_casa.md`) regenerates a JSON
  (e.g. `soglia_altezza: 2.40`) that `checker.py` reads to change its verdict on the 3D model —
  **without touching a single line of Python.**
- **Needed (X/Y/Z):**
  - X — `parser.py` writes the RASE rule to a stable artifact (`sandbox/rules/compiled/<id>.json`).
  - Y — a small mapping/IO layer: RASE clauses → checker thresholds (height by occupancy,
    aeroilluminating ratio, Salva-Casa exception value).
  - Z — `checker.py` gains a `--rules <json>` input and drives every constant from it
    (constants become *defaults*, overridden by the JSON).
- **Done when:** you change a number by hand in the law text (e.g. `2,70` → `2,40`), re-run the
  parser, and the verdict on the 3D model changes on its own, with **zero `.py` edits**.
- **Acceptance test:** flip habitable height to 2,40 in the `.md` → re-parse → FZK-Haus baseline
  violations drop the same way `--salva-casa` does today.
- **✅ Verified (2026-06-17):** `parser.py --out` emits `{rule, thresholds, source}` from the law
  text (regex extraction, `source=text-extraction`); `checker.py --rules` drives every threshold
  from it (constants are now only defaults). Editing `2,70 → 2,40` in the `.md`, re-parsing, and
  re-checking dropped FZK-Haus baseline **5 → 1** with no `.py` edit (then reverted). The regex
  extractor is the low-code placeholder Stage 2 replaces with the local LLM.

---

## Stage 2 — Local brain (AI integration) ✅ *(done + verified)*

- **Goal:** make text comprehension autonomous and 100% private. The local LLM reads the Italian
  legal text and emits **only** the structured RASE JSON — no invented text, no hallucinated numbers.
- **Needed (X/Y/Z):**
  - X — local **Ollama** install with a light model (**Mistral 7B** or **Llama 3 8B**).
  - Y — the definitive system prompt in `parser.py` (RASE-only, JSON-schema-constrained,
    `temperature 0`, refuse-to-invent).
  - Z — a validation gate: parser output must pass the pydantic schema *and* a numeric
    cross-check against the source text before it reaches the checker.
- **Done when:** you disconnect the internet and the whole cycle (Law → Local AI → JSON →
  Geometric check) runs **at zero cost, locally**.
- **Note:** the Ollama code path already exists in `parser.py`; this stage hardens the prompt,
  installs the model, and replaces the offline fallback with a verified local generation.
- **✅ Verified (2026-06-18):** pinned local `llama3.1:8b` (id `46e0c10c039e`, Q4_K_M, localhost, €0)
  emits the RASE JSON; an untrusted-LLM VALIDATION GATE (`verify_rule_against_text`) re-derives each
  threshold from the statute (answer-key block excluded, unique metric anchor) and rejects any
  unbound/decoy/partial/ambiguous value — no fallthrough to defaults (`source=='llm'`). ORACLE
  `2.70/2.40/2.40/0.125`, TRACK `2,70→2,73`, NO-INVENT→reject all reproduce ≥3× identical; pipeline
  still gives FZK-Haus **5 → 1**. Self-test `tests/test_gate.py` 19/19 (incl. 6 adversarial-audit
  regressions: anchor-shadowing false-pass fixed, bilingual false-fails fixed).

---

## Stage 3 — Multi-software robustness (stress test) 🟢 *(Parts 2–3 done — 3/3 run clean; geometry probed in Part 3 and DECLINED on evidence — Duplex is gross-only; ✅ on the no-quantity class needs a net-geometry fixture)*

- **Goal:** the same script must survive the slightly different IFC exports of Revit, ArchiCAD,
  Allplan. A tool that only works on `FZK-Haus` has no commercial value.
- **Needed (X/Y/Z):** the already-identified extra fixtures — **Revit `Duplex`** and the
  **KIT files** (`AC20-Institute-Var-2`).
- **Done when:** the identical script emits a clean, **runtime-error-free** compliance verdict on
  **≥3 IFC models from different software**.
- **Status detail (Part 2 — 2026-06-18):**
  - ✅ `AC20-FZK-Haus` (ArchiCAD/IFC4) — 5 → 1 violations, 0 undetermined.
  - 🟢 `AC20-Institute-Var-2` (ArchiCAD-KIT/IFC4) — runs clean: 2 → 2 violations (spaces 402/403),
    0 undetermined; classification recovered (0 → 55 habitable) after the German/KIT vocab fix.
  - 🟡 `Duplex_A` (Revit/IFC2X3) — runs clean but **not certifiable**: 0 violations / **21 undetermined**
    (no Qto height, no area Qto; only a wrong-quantity Pset `Unbounded Height`). **Part 3 probed geometry
    and declined it on evidence:** geom Z-extent reproduces the *net* Qto height exactly on FZK/Institute
    prismatic spaces, but on Duplex it ≈ the **gross** `Unbounded Height` (R301 exactly 3.000); geom
    footprint == **GrossFloorArea** (not net); window-by-containment is not exact on any fixture. So the
    no-quantity/gross-only class stays **honestly undetermined** — ✅ here needs a fixture carrying **net**
    geometry. Only the Part-3 safety keystone shipped (occupancy-aware `compliant`, no partial-evidence pass).
    See ADR-004 + `sandbox/STAGE3_PART3_PROBE.md`.
- **Naming divergences to map** (the heart of this stage): quantity-set name
  (`BaseQuantities` vs `Qto_SpaceBaseQuantities` — already handled), and height key variants
  (`Height` vs `ClearHeight` vs `FinishCeilingHeight` vs vendor-local `AltezzaNetta`).
  Plus: containment fallback when space boundaries don't resolve windows.

---

## Stage 4 — Generalize the model + gate-verified applicability/selection + a real 2nd rule (no graph) 🟢 *(Parts 1–4 done — verdict-neutral; monostanza honest-undetermined, ✅ needs a monolocale fixture)*

- **Goal (rescoped 2026-06-19 → ADR-005).** A 7-lens adversarial audit (`sandbox/STAGE4_BASELINE.md §1`)
  found the minimal graph migration a **premature abstraction**: a vocab-only graph leaves `classify()`
  in Python before any query, the safety "proof" is circular (the frozen controls are *outputs of* the
  current Python), and the `getattr` indirection is cosmetic against a fixed-4-field dataclass. The
  *real* unsolved problems were a **verification gap** (applicability/selection unverified) and
  **unproven generalization past one rule** — Stage 4 attacks those WITHOUT a graph.
- **Delivered (Parts 1–4, each verdict-neutral, controls byte-frozen after every code task):**
  - **Generalized requirement model** — the rigid 4-float `Thresholds` is now a backward-compatible
    accessor *view* over a `Requirement` record list; a 5th metric resolves without a dataclass edit,
    fail-closed (absent metric RAISES); the four frozen numbers resolve byte-identically (Part 2).
  - **Externalized, gate-verified applicability/selection** — the occupancy vocabulary +
    occupancy→{height-bar, aero-applies} map moved into `rules/applicability.json` (pinned set-equal to
    the frozen Python tuples incl. codepoints); the Italian Art.1 accessory tokens are gate-anchored to
    the statute prose; the cross-lingual glossary is **declared, unanchored debt**; the compiled
    `selection` is populated **gate-verified at compile time** (Parts 3–4).
  - **A real 2nd rule — alloggio monostanza** — its four surfaces (28/38/20/28) are **gate-verified
    against the statute** (person-count-qualified, unique-value-or-raise; montani 2,55 + seismic stay
    rejected; the prompt decoy un-suppressed), held in the requirement model, and evaluated UNIT-level →
    **`undetermined` on all 3 fixtures** (no monolocale unit + person count) — never a fabricated pass.
    The per-space verdicts and the four frozen numbers move by **zero** (Part 4).
- **Done when:** the model admits a genuine 2nd rule at every layer (gate + model + honest undetermined
  channel) with the controls byte-frozen — **met**. **✅** (positive monostanza evaluation) needs a
  **monolocale fixture** (a single-room dwelling unit + person count), mirroring Stage-3's net-geometry
  deferral (ADR-004).
- **Honesty boundary (carried, not over-claimed):** the monostanza gate is **test-enforced, not
  runtime-wired** (like the Part-3 selection gate); the checker's hardcoded monostanza records are **not**
  gate-checked (a mis-transcription surfaces only when a monolocale fixture exercises them); the
  cross-lingual accessory glossary remains declared, unanchored debt. See ADR-005.

---

## Stage 4b — Graph anchoring (scalability) 🟢 *(seam established + verdict-neutral; ✅ deferred to the scale/inference load that justifies a production graph)*

- **Goal:** turn the exercise into a commercial asset. Flat JSON is fine for a handful of rules; it
  collapses at ~150 rules (e.g. the Milano building code). Store rules as nodes and relations in a
  **Knowledge Graph**, and let the checker **query the Graph** to discover which requirements apply to a
  specific room — the room/`IfcSpace` must actually enter the graph store (else the done-when is met in
  letter only).
- **Store (pre-decided — `STAGE4_BASELINE.md §1` decision 4):** **rdflib `==7.6.0`** (standard Store API
  + SPARQL 1.1, so **Oxigraph** is a one-line backend swap and the documented upgrade path). **Neo4j
  rejected** (GPL-3.0 on a commercial asset).
- **Done when:** the checker no longer queries a flat text/JSON file but **queries the Graph** to
  discover which requirements apply to a specific room.
- **Delivered (ADR-006, 2026-06-24):** the room→occupancy decision now flows from a **SPARQL 1.1 query
  over an rdflib store into which each IfcSpace is materialized at runtime** (`sandbox/graph.py`);
  `classify()`'s substring branch is **replaced** (proven via raise-on-empty-ontology +
  `inspect.getsource` substring-absent, not just output-equivalence); controls byte-frozen THROUGH the
  graph path (FZK 5→1, Institute 2→2 on 402/403, Duplex 0/21; 220-row 0-drift). **Honesty (bounded, not
  over-claimed):** on the 3 fixtures the graph is **verdict-equivalent to the flat table by construction**
  (all real occupancy is flat-substring-decidable) — reproducing the controls is *necessary-but-
  insufficient*; non-circularity is **bounded, not eliminated** (**4 of 51** tokens statute-anchored to
  Art.1; 47 reproduced-not-verified; cross-lingual = declared debt); transitive `subClassOf+` inference is
  demonstrated on a **synthetic** divergence room (no fixture needs it). The graph carries **occupancy
  only**; requirement values + monostanza stay out (un-gate-checked constants must not become graph
  "facts").
- **Trigger for ✅ / the rest:** only when room-type hierarchies / multi-jurisdiction conflict / ~150
  rules actually need inference or scale — not before (avoid the premature abstraction Stage 4 rejected).
  Remaining (not started): requirement VALUES in the graph; the Oxigraph backend swap at scale.

---

## Iteration Log

*(append one line per iteration — newest at top)*

- **2026-06-24** — Stage 4b 🔴→🟢 (graph **seam** built, verdict-neutral). The room→occupancy decision now
  flows from a **SPARQL 1.1 query over an rdflib `==7.6.0` store** into which each IfcSpace is materialized
  at runtime (`sandbox/graph.py`); `classify()`'s substring branch **replaced** (proven via
  raise-on-empty-ontology + `inspect.getsource` substring-absent). Controls byte-frozen THROUGH the graph
  (FZK 5→1, Institute 2→2 on 402/403, Duplex 0/21; 220-row 0-drift; `test_graph` 23/23). **Honest &
  bounded:** verdict-equivalent to the flat table by construction on the 3 fixtures (reproduction is
  necessary-but-insufficient); **4/51** tokens statute-anchored, 47 reproduced-not-verified, cross-lingual
  = declared debt; transitive inference shown on a **synthetic** load-bearing divergence room; scale
  trigger (~150 rules) **not** fired → **✅ deferred**; graph carries occupancy only (ADR-006).
- **2026-06-20** — Stage 4 🔴→🟢 (rescoped: generalize + verify, **no graph**; graph → Stage 4b). Parts 2–4
  delivered a record-backed requirement model, an externalized + gate-verified applicability/selection
  table (compiled `selection` now populated gate-verified), and a real 2nd rule — **alloggio monostanza**:
  four surfaces (28/38/20/28) gate-verified against the statute (person-count-qualified, unique-or-raise;
  montani 2,55 + seismic stay rejected; prompt decoy un-suppressed), held in the model, evaluated
  UNIT-level → **undetermined on all 3 fixtures** (never a pass). Controls byte-frozen (FZK 5→1, Institute
  2→2 spaces 402/403, Duplex 0/21 both modes; `test_gate` 27→37, `test_requirement_model` 16→25,
  `test_geometry_fallback` 12/12, `test_height_keys` 9/9, `test_applicability_table` 18/18 incl. 220-row
  equivalence 0-drift). ✅ on monostanza needs a monolocale fixture. See ADR-005.
- **2026-06-19** — Stage 3 🟢 Part 3 (geometry fallback, `checker.py` only): **probed then DECLINED on
  evidence**. Phase-0 (workflow-verified, `wf_919ec580-bba`: 3 reproducers match, 3 challengers
  `decision_stands`) found geom Z-extent reproduces *net* Qto height exactly on FZK/Institute prismatic
  but ≈ the **gross** Unbounded Height on Duplex (R301 3.000==3.000), geom footprint == **GrossFloorArea**,
  and window-containment is not exact on any fixture — so height/area/window all stay **undetermined** for
  Duplex (honest). Only the safety keystone shipped: occupancy-aware `compliant` (no partial-evidence pass).
  Controls frozen (FZK 5→1, Institute 2→2 spaces 402/403 GlobalId-identical, Duplex 0/21 both modes);
  `test_gate` 19/19, `test_height_keys` 9/9, new `test_geometry_fallback` 12/12. ✅ on the no-quantity class
  needs a net-geometry fixture. See ADR-004.
- **2026-06-18** — Stage 3 🟢 Part 2 (checker robustness, `checker.py` only): unmeasurable spaces now
  surfaced as `spaces_undetermined` + listed + non-zero exit (Duplex 21/21 no longer reads as a bare
  "0 violations" pass — the production-safety keystone); multi-key Qto height (`Height` first); KIT/German
  classification vocab (Institute habitable 0→55). All controls held (FZK 5→1, Institute 2→2 spaces 402/403,
  Duplex 0→0; `test_gate` 19/19; new `test_height_keys` 9/9). ✅ deferred to **Part 3** (geometry for a
  *meaningful* Duplex verdict). See ADR-003.
- **2026-06-18** — Stage 2 ✅ local brain: pinned offline `llama3.1:8b` emits RASE JSON, hardened by a
  verify-never-trust gate (statute-anchored, answer-key-excluded, unique-value, no default fallthrough).
  ORACLE/TRACK/NO-INVENT verified ≥3× at €0; self-test 19/19; multi-agent audit found+fixed an
  anchor-shadowing false-pass. **Stage 3 (multi-software robustness) is now the active target.**
- **2026-06-17** — Stage 1 ✅ dynamic wiring: `parser.py` extracts thresholds from the law text →
  `{rule, thresholds}` JSON → `checker.py --rules`. Verified the `2,70→2,40` edit flips FZK-Haus
  baseline 5→1 with no Python edit. **Stage 2 (local Ollama) is now the active target.**
- **2026-06-17** — Roadmap created. Stage 0 ✅ (sandbox verified on FZK-Haus: 5 → 1 violations).
  Stages 1–4 scoped; Stage 1 (dynamic wiring) is the active next target.
