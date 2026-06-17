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
| 1 | **Dynamic wiring** — parser JSON drives the checker | Edit the law text → verdict changes, no `.py` edit | 🔴 |
| 2 | **Local brain** — Ollama, 100% offline | Internet off → full cycle runs at €0 locally | 🔴 |
| 3 | **Multi-software robustness** — stress test | Clean verdict, no runtime errors, on ≥3 IFC from different tools | 🟡 1/3 |
| 4 | **Graph anchoring** — Knowledge Graph | Checker queries the graph, not a flat file | 🔴 |

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

## Stage 1 — Dynamic wiring (low-code) 🔴 *(next)*

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

---

## Stage 2 — Local brain (AI integration) 🔴

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

---

## Stage 3 — Multi-software robustness (stress test) 🟡 *(1/3 models)*

- **Goal:** the same script must survive the slightly different IFC exports of Revit, ArchiCAD,
  Allplan. A tool that only works on `FZK-Haus` has no commercial value.
- **Needed (X/Y/Z):** the already-identified extra fixtures — **Revit `Duplex`** and the
  **KIT files** (`AC20-Institute-Var-2`).
- **Done when:** the identical script emits a clean, **runtime-error-free** compliance verdict on
  **≥3 IFC models from different software**.
- **Status detail:**
  - ✅ `AC20-FZK-Haus` (ArchiCAD/IFC4) — verified in-repo.
  - 🔴 `AC20-Institute-Var-2` (IFC4) — not yet run in-repo.
  - 🔴 `Duplex_A` (Revit/IFC2X3) — known to lack space quantity sets and to have
    `IfcRelSpaceBoundary.RelatedBuildingElement = None`.
- **Naming divergences to map** (the heart of this stage): quantity-set name
  (`BaseQuantities` vs `Qto_SpaceBaseQuantities` — already handled), and height key variants
  (`Height` vs `ClearHeight` vs `FinishCeilingHeight` vs vendor-local `AltezzaNetta`).
  Plus: containment fallback when space boundaries don't resolve windows.

---

## Stage 4 — Graph anchoring (scalability) 🔴

- **Goal:** turn the exercise into a commercial asset. Flat JSON is fine for one rule; it
  collapses at ~150 rules (e.g. the Milano building code). Store rules as nodes and relations
  in a **Knowledge Graph**.
- **Needed (X/Y/Z):** a lightweight native graph DB — **Oxigraph** (Python, RDF/SPARQL, Apache-2.0)
  or a local **Neo4j** instance — chosen per the audited OSS stack in `research/FACTUAL_BASELINE.md`.
- **Done when:** the checker no longer queries a flat text/JSON file but **queries the Graph** to
  discover which requirements apply to a specific room.
- **Note:** this is where applicability/selection logic (which rule applies to which space type)
  moves from Python conditionals into graph queries.

---

## Iteration Log

*(append one line per iteration — newest at top)*

- **2026-06-17** — Roadmap created. Stage 0 ✅ (sandbox verified on FZK-Haus: 5 → 1 violations).
  Stages 1–4 scoped; Stage 1 (dynamic wiring) is the active next target.
