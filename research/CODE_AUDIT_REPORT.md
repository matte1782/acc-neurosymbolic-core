# ACC Neurosymbolic Core - Code Audit Report

Date 2026-06-27 · Scope = Stages 1-4 + 4b · Method = multi-agent static + functional audit (map, four stage audits, e2e trace, functional-health run), adversarially verified (refuted candidates dropped), all claims cited to file:line opened during the audit.

---

## 1. Current System Architecture Map

Two decoupled lanes meet at a compiled-rule boundary. The NEURO lane (parser.py) extracts statute numbers via a local Ollama model behind a verify-never-trust gate and is exercised end-to-end only on an explicit `python parser.py` invocation. The SYMBOLIC lane (checker.py) is the live runtime verdict path; it resolves thresholds from a record-backed model, reads quantities from IfcOpenShell, and delegates room→occupancy classification to graph.py (rdflib + SPARQL). The Ollama call is NOT on the default runtime path; parser.py is nonetheless on the live path *indirectly* because graph.py imports it to run the 4-token Art.1 anchor gate against the statute prose on every run.

```
LEGEND  [LIVE]=on a plain `python checker.py model.ifc` run   [CLI]=only on an explicit flag/invocation
        [TEST]=test-only/offline   [DEAD@default]=present but not read unless --rules

============================ NEURO LANE (parser.py) ============================
 rules/dm_1975_salva_casa.md  (Italian statute prose; answer-key after "## Target rule"
   is STRIPPED by crosscheck_corpus  parser.py:262-270)
        |  python parser.py rules/...                                   [CLI]
        v
   parse_rule(text, offline=False)                       parser.py:737-755
     |- parse_with_ollama(text)                          parser.py:708-734  [CLI]
     |    POST /api/chat  format=RULE_JSON_SCHEMA  temp0/seed0/top_k1  -> Rule.model_validate_json
     |    (RAISES on unreachable/HTTP/schema; NEVER silently degrades)
     |- verify_rule_against_text(rule, text)             parser.py:346-400  <-- VALIDATION GATE
     |    per-key: re-derive number from corpus (metric-anchored regex, unique-or-RAISE),
     |    bind clause only on value+op>=+unit+discriminator; any miss RAISES
     |  python parser.py rules/... --offline                            [CLI]
     |    extract_thresholds_from_text :142-162 ; MISSING keys backfilled from
     |    DEFAULT_THRESHOLDS, source="text-extraction"/"defaults"  (NO gate)  <-- the one unverified path
        v
   main() writes {rule, thresholds, source}  parser.py:758-780  --out--> compiled JSON

   STANDALONE GATES (not called by parse_rule):
     verify_accessory_selection_against_text  parser.py:466-501   [LIVE via graph.py]
     verify_monostanza_against_text           parser.py:589-651   [TEST only]
     gate_verified_selection                  parser.py:684-705   [CLI offline-compile only]

========================= COMPILED RULE (the seam) ============================
 rules/compiled/dm_1975_salva_casa.json  {thresholds:{2.7,2.4,2.4,0.125}, selection[], source:"llm"}
        |  Thresholds.from_rules_json(path)  checker.py:211-229   ONLY if `--rules FILE`  [CLI]
        v   (NB on a plain run this file is [DEAD@default]: run() uses Thresholds() defaults :553-554)

============================ SYMBOLIC LANE (checker.py) ========================
 model.ifc (FZK-Haus / Institute-Var-2 / Duplex)
        |  python checker.py model.ifc [--salva-casa] [--rules F] [--json OUT]
        v
   main() :592-631 -> run(path, salva_casa, thr) :553-589                        [LIVE]
     |- ifcopenshell.open(path) ; uu.calculate_unit_scale -> scale (->m)  :555-556
     |- for each IfcSpace: check_space(space, scale, salva_casa, thr) :425-472
     |     |- _applicability() load rules/applicability.json  :334-397  (fail-closed; anti-drift guard)
     |     |- classify(space) :400-408 -> graph.occupancy_via_graph(Name,LongName) graph.py:177-198
     |     |     _ontology() build+cache build_ontology() seeded from applicability.json;
     |     |     GATE verify_accessory_selection_against_text (4 Art.1 tokens vs statute .md);
     |     |     SPARQL 1.1 SELECT (accessory-first ORDER BY, LIMIT 1, CONTAINS); no row -> "unknown";
     |     |     empty ontology -> RAISE  => accessory | habitable | unknown
     |     |- space_height :288-296 (Qto-only multi-key, Height-first; None -> note, NO geom fallback)
     |     |- space_floor_area :299-304 ; windows_serving :411-422 -> window_area :307-313
     |     |- required = thr.resolve("min_height", height_metric) :438 ; salva_casa swap :439-440
     |     |- height_ok / aero_ok -> SpaceFinding(.compliant :246-258: any applicable None -> None)
     |- materialize_ifcspaces(model,scale) :528-550  (per-run rdflib store; NODES counted, NOT on verdict)
     |- monostanza_status(model) :493-525  (UNIT-level channel; "undetermined" on all 3 fixtures)
        v
   report {schema, thresholds, spaces_evaluated, violations, spaces_undetermined,
           ifcspace_store_nodes, monostanza, findings[]}
     |- --json OUT -> <model>_report.json  [CLI]
     |- main() prints verdict + violations + undetermined; exit 1 if (violations OR undetermined) [LIVE]
        v  VERDICT

KEY RUNTIME FACTS
 * Neuro & symbolic lanes are DECOUPLED at default runtime: checker.run() never imports parser
   and never reads the compiled JSON unless --rules. Dependency direction checker -> graph -> parser
   (one-directional, no cycle). The statute .md IS read live each run via the graph anchor gate.
 * Geometry fallback PROBED then DECLINED (ADR-004): space_height is strictly Qto-only; None stays
   undetermined, never a fabricated pass.
```

### Inventory (load-bearing files)

| Path | Role | Live? |
|---|---|---|
| sandbox/checker.py | Symbolic verdict engine: IfcOpenShell Qto reads, table-driven applicability, classify()→graph, Thresholds.resolve, fail-closed compliant/undetermined, monostanza channel, CLI + JSON report. | [LIVE] |
| sandbox/parser.py | Neuro layer: Ollama RASE extractor (+ --offline regex) and verify-never-trust gates. Imported by graph.py for the live 4-token Art.1 anchor; Ollama call itself CLI-only. | [LIVE] (gate) / [CLI] (LLM) |
| sandbox/graph.py | Stage 4b: builds/caches rdflib ontology seeded from applicability.json, statute-gates 4 Art.1 tokens, answers occupancy via one SPARQL 1.1 SELECT (accessory-first, strict-unknown, subClassOf+). Fail-closed on empty ontology. | [LIVE] |
| sandbox/rules/dm_1975_salva_casa.md | Raw DM 5/7/1975 statute prose; the source-of-truth all parser gates re-derive numbers/enumeration from. | [LIVE] (read by gate) |
| sandbox/rules/compiled/dm_1975_salva_casa.json | Compiled {thresholds, selection, source:"llm"}; consumed by checker ONLY via --rules. Provenance label "llm" inconsistent with offline-gate selection content. | [DEAD@default] |
| sandbox/rules/applicability.json | Declarative occupancy/selection table; read LIVE by checker._applicability() AND seeded into the graph ontology. Untracked in git but load-bearing. | [LIVE] |
| sandbox/tests/test_gate.py | Offline positive/negative control for parser gates (37 cases). | [TEST] |
| sandbox/tests/test_height_keys.py | Unit test of multi-key Qto height lookup (mocked psets). | [TEST] |
| sandbox/tests/test_geometry_fallback.py | SpaceFinding.compliant completeness + records the geometry-DECLINE decision. | [TEST] |
| sandbox/tests/test_requirement_model.py | Pins record-backed Thresholds + from_rules_json round-trip. | [TEST] |
| sandbox/tests/test_applicability_table.py | Pins the externalized table as verdict-neutral vs equiv_oracle.json. | [TEST] |
| sandbox/tests/test_graph.py | Pins the graph seam: oracle reproduction, synthetic subClassOf+ inference, 4/51 anchoring, fail-closed paths. | [TEST] |
| sandbox/tests/equiv_oracle.json | Frozen golden projection captured pre-refactor; the un-editable equivalence oracle. | [TEST] |
| sandbox/data/AC20-FZK-Haus.ifc | Fixture (ArchiCAD IFC4): Qto Height under set 'BaseQuantities'. git-ignored, on disk. | fixture |
| sandbox/data/AC20-Institute-Var-2.ifc | Fixture (ArchiCAD/KIT IFC4): German room names, aero violations. | fixture |
| sandbox/data/Duplex_A_20110907.ifc | Fixture (Revit IFC2X3): no net-height Qto → the undetermined class. | fixture |
| sandbox/requirements.txt | Stack: ifcopenshell, pydantic, requests, rdflib==7.6.0. | config |
| docs/decisions.md | Append-only ADR chain ADR-001..006 (project memory; claims to verify). | doc |

> Git-tracking note: graph.py, applicability.json, equiv_oracle.json and 4 of 6 test files are UNTRACKED on the current branch yet present on disk and load-bearing — the "current architecture" lives partly outside committed history.

---

## 2. Deterministic Health Matrix (Stages 1-4)

| Stage | Status | SOTA Compliance Level | Technical Gaps & Vulnerabilities |
|---|---|---|---|
| **Stage 1 — Dynamic coupling** (thresholds from compiled JSON, no hardcoded bars in verdict path) | **IMPLEMENTED** | Production-adjacent. Height/aero bars resolve through `thr.resolve` / accessors (checker.py:438,440,466); module constants are default-params only (no verdict use). Empirically verified: editing JSON habitable→2.40 drops FZK 5→1, →3.50 holds 5 with H=3.5 in the print line. | Coupling scoped to the JSON `thresholds` block only — the RASE `requirement`/`selection`/`exception` arrays are inert (checker.py:219), so human-readable clauses can silently diverge from machine-read numbers. Monostanza statute numbers (28/38/20/28) are hardcoded into the model, not JSON-parameterized (checker.py:142). Which-bar-applies (occupancy) is anchored to frozen Python tuples, not JSON-editable (checker.py:368). All low; none reach a height/aero comparison. |
| **Stage 2 — Local LLM + verify-never-trust gate** | **IMPLEMENTED** | Strong prototype; the gate is genuinely SOTA-grade (deterministic re-derivation, unique-value-or-RAISE anti-shadowing, answer-key corpus exclusion, disjoint discriminators for the two 2.40 values, no-fallthrough test-proven). Suite 37/37. | **HIGH:** code default model tag is the floating `llama3.1`, not the ADR-pinned `llama3.1:8b` digest — pinning lives only in an env var, with no runtime digest assertion (parser.py:713). **MED:** no automated determinism harness backing the ">=3x identical" DONE-WHEN (docs/decisions.md:12). **MED:** Ollama response indexed `resp.json()['message']['content']` with no structural guard — a 200 with an unexpected body raises raw KeyError, not a domain error (parser.py:732-734). The `--offline` path backfills DEFAULT_THRESHOLDS ungated (see §3). |
| **Stage 3 — Multi-software robustness** (IfcOpenShell parsing) | **IMPLEMENTED** | Strong prototype. Honest-undetermined keystone is real and load-bearing (compliant=None on any applicable null, never laundered; non-zero exit). Multi-key Qto height + dual set names ('BaseQuantities' is load-bearing for ArchiCAD), Qto-only area, unit scaling, None-safe BoundedBy/get_psets all verified on 3 real fixtures, 2 authoring tools. Geometry fallback correctly ABSENT (ADR-004). | **CRITICAL:** negative window dims pass the truthiness guard and fabricate a positive area → false-compliant pass (see §3). **CRITICAL:** unit scale silently defaults to 1.0 when no LENGTHUNIT resolves → 1000× misread can pass a too-low room (see §3). **MED:** unguarded `float()` in window_area crashes on non-numeric dims; no per-space exception isolation in run() (checker.py:557). **LOW:** non-metric scale path never exercised by a fixture; Duplex area recoverable but deliberately unread (honest-undetermined). |
| **Stage 4 + 4b — Generalized model + applicability + graph anchor** | **PARTIAL** | Strong prototype. The graph IS built in 4b: classify() delegates entirely to a SPARQL 1.1 query over an in-memory rdflib==7.6.0 store (checker.py:408 → graph.py:190); the Python substring branch is physically deleted and structurally test-enforced; empty ontology RAISES; suite 23/23. **But it is occupancy-only**: thresholds, applicability/selection, and rule values remain flat-JSON/Python. The graph is verdict-equivalent to the flat table BY CONSTRUCTION (seeded from the same applicability.json) and the one graph-exclusive capability (rdfs:subClassOf+ inference) fires only on a SYNTHETIC 'vestibolo' node — not yet a scaled rule graph. | **HIGH:** rules are NOT stored as semantic relations for execution; only room→occupancy is graph-backed (checker.py:436-438). **MED:** equivalence is by-construction, not independent (graph.py:11-14); transitive inference unexercised by real data (graph.py:46-53). **MED:** SPARQL CONTAINS substring matching can misclassify (see §3). **LOW:** compiled JSON source="llm" is optional/not the runtime substrate; doc drift "220-row" vs live 110-row oracle. |

---

## 3. Critical Code Vulnerabilities & Edge Cases

> The list below contains ONLY adversarially-confirmed findings. **2 candidate findings were refuted/dropped during verification** — this is a filtered list, not raw output. Several confirmed findings were calibrated down in severity by the verifiers (notably the floating-model-tag and graph-only-occupancy items); their facts hold and they are retained at their cited severity with that mitigation noted inline.

### CRITICAL

**C-1. Negative window dimensions fabricate a positive area → false-compliant pass (safety-keystone breach)**
- Location: `checker.py:310-312` (window_area); reached via `windows_serving:421` → `check_space:430,466` → `SpaceFinding.compliant:246-258`.
- What/trigger: the guard `if h and w:` rejects only None/0.0 — negative reals are truthy. A schema-valid garbage export with `OverallHeight=-2.0, OverallWidth=-1.0` (IfcLengthMeasure REALs) yields `+2.0 m²`. This is the *preferred* path (Qto is only the fallback at :313). End-to-end verified: a habitable space (h=2.8, area=10) with such a window reads aero_ratio=0.2, aero_ok=True, **compliant=True** on fabricated geometry — directly violating "never launder a garbage value into a pass."
- Deterministic fix: reject non-positive dimensions — `if h and w and h > 0 and w > 0:` — and validate the _qty/area result is `> 0`, else fall through to None (undetermined).

**C-2. Unit scale silently defaults to 1.0 (metres) when LENGTHUNIT is missing → 1000× misread can pass a non-compliant model**
- Location: `checker.py:556` (`scale = uu.calculate_unit_scale(model)`, consumed unvalidated at `checker.py:282` and `checker.py:456`).
- What/trigger: `ifcopenshell.util.unit.calculate_unit_scale` returns `1` when there is no IfcProject, when UnitsInContext is falsey, or when no LENGTHUNIT entry exists (verified by reading the installed source and reproducing all three branches). run() never validates that a length unit actually resolved. A millimetre-authored model that lost/omitted its LENGTHUNIT is read as metres: a 2500 mm room becomes 2500 m and trivially clears the 2.70 m bar → **silent false pass** of a too-low room. (Requires a non-conformant IFC; all 3 fixtures correctly declare METRE, so it is latent — but it is the dangerous direction and is undetected.)
- Deterministic fix: fail-closed when no LENGTHUNIT resolves — detect the absent-unit case explicitly (e.g. inspect `model.by_type("IfcProject")[0].UnitsInContext` for a LENGTHUNIT) and raise / mark the whole model not-certifiable rather than defaulting to 1.0.

### HIGH

**H-1. Model with zero IfcSpaces exits 0 = compliant → vacuous pass on an uncheckable model**
- Location: `checker.py:557` (`model.by_type("IfcSpace")`), report at `:567,571`, exit at `:631`.
- What/trigger: findings derive only from IfcSpace. A model with rooms modeled as IfcZone/IfcBuildingElementProxy, or no spaces at all, gives findings=[] → violations=0, undetermined=0 → `main()` returns `1 if (violations or undetermined) else 0` = **0**. Verified: a valid project with no IfcSpace prints "0 IfcSpace | 0 violation(s) | 0 undetermined" and exits 0. This is the same vacuous-pass class the per-space undetermined keystone was built to prevent, occurring below its granularity (spaces_evaluated==0).
- Deterministic fix: in `main()`/`run()`, treat `spaces_evaluated == 0` as not-certifiable — exit non-zero with an explicit "no IfcSpace measured" status.

**H-2. Code default model tag is the floating `llama3.1`, not the ADR-pinned digest** *(mitigated: gate blocks a wrong verdict)*
- Location: `parser.py:713` (`model = model or os.environ.get("ACC_LLM_MODEL", "llama3.1")`).
- What/trigger: ADR-002 (docs/decisions.md:11) claims a pinned `llama3.1:8b` id `46e0c10c039e`; the digest appears nowhere in code, and there is no runtime model-identity assertion. A registry retag silently changes the neuro layer's output. The verify-never-trust gate means a retag cannot launder a *wrong threshold* into the checker (it would surface as a gate RAISE), so the real exposure is reproducibility/availability and ADR-vs-code divergence, not a silent compliance bypass — but for a zero-hallucination framework the model identity should be pinned in code.
- Deterministic fix: default `ACC_LLM_MODEL` to the digest-pinned tag and assert the served model digest at runtime in `parse_with_ollama`.

### MEDIUM

**M-1. `--offline` path backfills DEFAULT_THRESHOLDS and emits source='defaults'** — `parser.py:753-755` (defaults at :129-134). When the regex finds nothing, the 4 statutory numbers are silently filled from hardcoded defaults and shipped as a usable compiled rule; partial extraction backfills missing keys under a "text-extraction" label too. checker.py never inspects `source` (only :218-219 reads `thresholds`), so the result is downstream-indistinguishable from a gate-verified rule. *Fix:* on `--offline`, RAISE on any unmatched key instead of backfilling; have the checker reject any compiled rule whose `source` is not `llm`.

**M-2. Ollama HTTP response indexed without a structural guard** — `parser.py:732-734`. `resp.json()['message']['content']` assumes the envelope; a 200 with an unexpected body (model-not-found error, proxy HTML, partial stream) raises raw KeyError/TypeError, not a clean ValidationGateError. *Fix:* `.get()`-guard the envelope and raise a typed domain error with remediation text.

**M-3. window_area unguarded `float()` crashes on a non-numeric vendor dim** — `checker.py:310-312`. When OverallHeight/Width are present-but-non-numeric, `float(h)*float(w)` raises ValueError with no try/except; with no per-space isolation in run() (`checker.py:557`) it aborts the whole report. Asymmetric with the guarded `_qty` (:281-284) and `_positive_int` (:486-489). *Fix:* wrap in `try/except (TypeError, ValueError): return None`, mirroring `_qty`; add a per-space try/except in run() that marks one quirky space undetermined.

**M-4. classify() substring CONTAINS matching relaxes a habitable room to the accessory bar** — `graph.py:63-80,189-198`; consumed `checker.py:436-466`. Accessory-first ORDER BY + pure substring CONTAINS means a habitable label containing an accessory token is classified accessory → height_metric 2.40 (not 2.70) AND aero_applies=False (the 1/8 check is skipped). Verified: `occupancy_via_graph('Soggiorno con bagno', None) → 'accessory'`; reverse false-positive `'Messeraum' → 'habitable'` via the 'ess' fragment. *Fix:* word-boundary / token-set matching instead of CONTAINS; reconsider accessory-first precedence for mixed labels.

**M-5. space_floor_area accepts a negative area (`if val:`) feeding the aero division** — `checker.py:299-304,449,465-466`. A negative area is truthy and is returned; the aero ratio is then computed over a negative denominator. Current fail direction is a spurious VIOLATION (compliant=False), not a pass — but a physically-impossible value is consumed as real, and combined with C-1 the sign handling is unsound. No positivity/finiteness check exists on any extracted quantity. *Fix:* require `val > 0` (use `is not None and val > 0`), else None.

**M-6. ifcopenshell.open() exceptions propagate uncaught → raw traceback** — `checker.py:555` / call site `:603`. A malformed/missing IFC raises `ifcopenshell.Error`/`FileNotFoundError` with a full traceback (plus a `__del__` finalizer KeyError). Fail-closed (non-zero, no false pass) but not classified — callers cannot distinguish "model unreadable → not certifiable" from a checker bug. *Fix:* wrap open() and emit a deterministic classified error.

**M-7. `_qty` swallows malformed quantities → 'present but corrupt' is indistinguishable from 'absent'** — `checker.py:280-285`. A non-numeric vendor value returns None, collapsing into the same 'undetermined' bucket as a genuinely missing quantity and mislabeling the cause ("geometry fallback needed"). Safe (no false pass) but masks data errors and inflates the undetermined count. *Fix:* distinguish a parse-error class from absence and surface it.

**M-8. aero check depends on IfcRelSpaceBoundary; absent boundaries → spurious violation** — `checker.py:411-422,465-470` (TODO at :414-415 confirms the storey/host fallback is unimplemented). Many exports omit IfcRelSpaceBoundary, so windows_serving returns 0.0 and a habitable room with real windows can be flagged as an aero VIOLATION (false fail), or routed to undetermined if also missing area. *Fix:* implement the storey/host-containment window fallback; treat "no boundaries resolvable" as undetermined rather than aero=0.

**M-9. from_rules_json trusts compiled JSON numbers without re-running the gate** — `checker.py:211-229,602`. `float(t[k])` consumes whatever the JSON says; a hand-edited or `--offline`-defaulted threshold is taken verbatim. The verify-never-trust guarantee lives only at parser compile time; nothing re-checks at check time and provenance is not inspected. *Fix:* re-verify thresholds against the statute at load, or require/inspect a `source=="llm"` provenance stamp.

**M-10. Graph occupancy is verdict-equivalent BY CONSTRUCTION, and transitive inference is synthetic-only** — `graph.py:11-23,46-53,63-80`. The ontology is seeded from the same applicability.json the flat table reads, so oracle reproduction proves a faithful copy of the old classify(), not independent correctness; 47 of 51 tokens are reproduced-not-verified cross-lingual debt; the only graph-exclusive capability (rdfs:subClassOf+) fires only on the hand-authored 'vestibolo' node. The module self-declares this — it is bounded, disclosed debt, not a concealed defect. *Fix:* none required for current scale; revisit when the ~150-rule trigger fires.

### LOW

**L-1. checker monostanza constants hardcoded and NOT gate-checked at runtime** — `checker.py:56-61,142-147`. 28/38/20/28 are Python literals never re-derived from JSON/statute at runtime; `verify_monostanza_against_text` proves them test-side only. Currently always returns 'undetermined' (never a runtime pass), so a wrong constant cannot flip a verdict today — becomes load-bearing only with a monolocale fixture.
**L-2. `parse_rule` all-four-thresholds guard is an `assert`** — `parser.py:751`, stripped under `python -O`. Redundant today (verify_rule_against_text already RAISES on any unresolved key), so no current false-pass; flagged so a future refactor does not lean on a stripped guard.
**L-3. Two divergent-strictness loaders of applicability.json** — `checker.py:334-388` (strict anti-drift) vs `graph.py:85-159` (loose; only the art1 statute gate + empty-ontology raise). The strict frozen-tuple guard runs in the production path (check_space calls _applicability() before classify()), but a standalone classify() caller bypasses it. *partial*: graph still applies the art1 gate, so the bypass is one-directional, currently only in tests.
**L-4. Doc/provenance drift** — compiled JSON `source:"llm"` but its selection[] is byte-identical to the OFFLINE gate output (parser never emits selection on the llm path); and "220-row equivalence" comments vs the live 110-row oracle (`graph.py:152`, `test_graph.py:105` vs `:127`). Cosmetic; binding checks are correct.

---

## 4. Next Action Items (The Engineering Backlog)

Prioritized, deterministic, each tied to a file/function. P0 = ship-blocking soundness; P1 = robustness/discipline; P2 = scale/hygiene.

### P0 — close the silent-false-pass holes (verify-never-trust breaches)
- [ ] **Positivity-validate every extracted quantity.** Fix `window_area` (checker.py:310-312) to require `h>0 and w>0`; fix `space_floor_area` (checker.py:299-304) to require `val>0`; harden `_qty` (checker.py:275-285) to reject non-finite/non-positive. Closes C-1 and M-5.
- [ ] **Fail-closed on an unresolved length unit.** In `run()` (checker.py:556), detect the missing-LENGTHUNIT case and mark the model not-certifiable instead of consuming scale=1.0. Closes C-2.
- [ ] **Reject the vacuous-pass.** In `main()`/`run()` (checker.py:557,631) treat `spaces_evaluated == 0` (no IfcSpace measured) as non-zero exit / not-certifiable. Closes H-1.
- [ ] **Gate the offline + load paths.** On `parser.py --offline` (parser.py:753-755) RAISE on any unmatched key instead of backfilling DEFAULT_THRESHOLDS; have `from_rules_json` (checker.py:211-229) require/inspect `source=="llm"` provenance. Closes M-1 + M-9.

### P1 — robustness & discipline
- [ ] **Per-space exception isolation.** Wrap the `check_space` comprehension (checker.py:557) so one malformed IfcSpace becomes undetermined rather than aborting the report; mirror `_qty`'s guard in `window_area` for non-numeric dims (M-3).
- [ ] **Classified model-load error.** Wrap `ifcopenshell.open` (checker.py:555) to emit "model unreadable → not certifiable" instead of a raw traceback (M-6).
- [ ] **Implement the window-association fallback.** Resolve the storey/host-containment TODO (checker.py:414-415) so absent IfcRelSpaceBoundary yields undetermined, not a spurious aero violation (M-8).
- [ ] **Word-boundary occupancy matching.** Replace SPARQL CONTAINS (graph.py:63-80) with token/word-boundary matching and re-examine accessory-first precedence; covers the relax-and-skip-aero risk (M-4).
- [ ] **Pin the model in code + assert at runtime.** Default `ACC_LLM_MODEL` to the digest tag and assert the served digest in `parse_with_ollama` (parser.py:713,708-734) (H-2).
- [ ] **Guard the Ollama envelope.** `.get()`-guard `resp.json()['message']['content']` and raise a typed domain error (parser.py:732-734) (M-2).
- [ ] **Distinguish corrupt from absent quantities.** Surface a parse-error class in `_qty` separate from 'undetermined' (checker.py:280-285) (M-7).

### P2 — assurance, scale & hygiene (completeness-critic items)
- [ ] **Automated determinism harness.** Add a real Ollama round-trip + hash-compare test backing the ">=3x identical" DONE-WHEN (docs/decisions.md:12); the live `parse_with_ollama` HTTP/JSON path currently has ZERO test coverage (only a monkeypatched stand-in at test_gate.py:186-196). (M-2, Stage-2 gap.)
- [ ] **Reproducible compiled artifact.** Make `rules/compiled/dm_1975_salva_casa.json` regenerable by a documented command; today it is a git-tracked `source:"llm"` output that no offline path reproduces (README.md:44 emits source/selection that diverge from the committed file). (L-4 + completeness-critic.)
- [ ] **Reproducible environment.** Add a pinned/locked dependency set + CI (no pyproject/lockfile/.github/workflows today; requirements.txt uses floor pins except rdflib); the "verified with IfcOpenShell 0.8.5" claim is unenforced and checker.py:262-264 depends on empirically-observed 0.8.5 Qto naming.
- [ ] **Cross-lingual classifier coverage.** Add fixtures/tests for English Revit names (Duplex 'Stair'/'Utility' match no accessory hint → fall to the 2.70 bar) and short-token false positives ('ess'/'bad'/'wc'); the equivalence oracle cannot catch a name wrong in BOTH oracle and graph since both come from the same substring logic. (Extends M-4/M-10.)
- [ ] **Non-metric & schema-version regression fixtures.** Add a mm/imperial IFC (exercises calculate_unit_scale, guards C-2) and an IFC2X3-vs-IFC4 aero-path test; the non-metric branch is currently unexercised (checker.py:556).
- [ ] **LICENSE + LGPL posture.** Add a project LICENSE and address the LGPL-3.0 IfcOpenShell linking obligation for a commercial asset (requirements.txt:2; the GPL-avoidance decision is documented but the product itself is unlicensed).
- [ ] **Scale/concurrency.** Benchmark per-space SPARQL (graph.py:190, O(spaces×ontology), checker.py:408,557) and per-run full-model materialization (checker.py:528-561, counted-only); make the module-global caches `_ONTOLOGY_CACHE`/`_APPLICABILITY_CACHE` (graph.py:82, checker.py:323) concurrency-safe before wrapping as a service.
- [ ] **Doc/provenance cleanup.** Reconcile the compiled JSON `source` label, the "220 vs 110" oracle comments, and the ADR-002 pinned-model claim with the code (L-4, H-2).
- [ ] **Commit the load-bearing untracked files.** graph.py, applicability.json, equiv_oracle.json and the 4 untracked test files are live but outside committed history.
