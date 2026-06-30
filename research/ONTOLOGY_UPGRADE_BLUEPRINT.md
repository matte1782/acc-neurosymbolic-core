# Stage 4/4b Ontology Upgrade Blueprint — unified Semantic Rule Graph (RDF/OWL + SHACL/SPARQL)

- **Date:** 2026-06-30
- **Status:** design / RFC
- **Honors:** verify-never-trust (the `parser.py` gate) + the standing CIRCULARITY warning (ADR-005 §1, ADR-006 HONESTY, `graph.py:11-28`).
- **Verification posture (read this first — it bounds every claim below):** all Turtle / SHACL-shapes-as-Turtle / SPARQL in this document was authored against and **parse-validated with the project's pinned `rdflib==7.6.0` on Python 3.13.14** (a unified TBox+ABox = 77 triples parsed clean; the SHACL shapes file = 49 triples parsed clean *as Turtle*; every SPARQL `prepareQuery` succeeds; the anti-circularity `FILTER NOT EXISTS` audit returns **exactly** the one deliberately-laundered node; the `rdfs:subClassOf+` transitive `ASK` returns `True`; the verdict query returns `[]` on the in-bounds sample). **`pyshacl` is NOT installed in this environment (`import pyshacl` → ModuleNotFoundError, verified), and rdflib ships no SHACL engine. Therefore no `sh:validate` has been executed anywhere in this design.** The honest ceiling for every SHACL artifact below is "parses as valid Turtle and uses SHACL-Core constructs"; the *runnable* anti-circularity enforcement adopted by this blueprint is the rdflib-only SPARQL audit (§3, §5), which was actually executed. This correction is the first of the critic's must-fix items, applied globally to supersede any "validated in rdflib 7.6.0" phrasing in the source design notes.

---

## 0. Problem & non-negotiables

### 0.1 What exists today (verified by reading, not assumed)

ACC is a neuro-symbolic habitability checker with two lanes joined at one seam:

- **NEURO lane** (`parser.py`): a local Ollama model (`llama3.1:8b`, digest `46e0c10c039e`, `docs/decisions.md` ADR-002) emits RASE JSON, treated as **untrusted**. The VALIDATION GATE `verify_rule_against_text` (`parser.py:346-400`) admits a threshold **only** if it is provably re-derived from the statute corpus with the answer-key block excluded (`crosscheck_corpus`), is a *unique* source value (ambiguous ⇒ raise, defeating decoy-shadowing), matches operator `>=`, the right unit, and a metric discriminator span. Missing/partial/decoy/swapped ⇒ **RAISE**, never a default. Sibling gates: `verify_accessory_selection_against_text` (`parser.py:466`, the Art.1 selection vocabulary), `verify_monostanza_against_text` (`parser.py:589`).
- **SYMBOLIC lane** (`checker.py`): IfcOpenShell reads IFC quantities; `classify()` → occupancy via a per-token SPARQL query over an rdflib ontology (`graph.occupancy_via_graph`, `graph.py:186-231`, Stage 4b / ADR-006). The keystone is `SpaceFinding.compliant` (`checker.py:247-259`).

The graph today carries **occupancy only**. Thresholds live in `checker.Thresholds` / `_dm1975_requirements` (the constants 2.70 / 2.40 / 2.40 / 0.125) and in the gate-verified compiled JSON `rules/compiled/dm_1975_salva_casa.json:105-110`; applicability lives in `rules/applicability.json` pinned codepoint-set-equal to the frozen Python tuples (`checker.load_applicability`). Monostanza surfaces 28/38/20/28 are **not** runtime-gate-checked (ADR-005 (ii)).

### 0.2 The keystone (must be reproduced byte-for-byte, never weakened)

`SpaceFinding.compliant` (`checker.py:247-259`) is **tri-valued**:

```python
required = ([self.height_ok] if self.occupancy == "accessory"
            else [self.height_ok, self.aero_ok])
if any(c is None for c in required):
    return None          # UNDETERMINED — never a pass on partial evidence
return all(required)
```

- `accessory` → required = `{height_ok}` (aero N/A — DM 1975 art.5 does not apply to accessories);
- `habitable` / `unknown` → required = `{height_ok, aero_ok}` (`unknown` is the strict complement, evaluated at the stricter habitable bar, `graph.py:202`, `checker.py:255`);
- **any applicable check `None` ⇒ `None` (UNDETERMINED)** — and `run()` exits non-zero on undetermined, so `None` is never laundered into a "0 violations" pass (ADR-003, the production-safety keystone). Duplex's all-unmeasured model reads 21/21 undetermined, not a pass.

### 0.3 The three non-negotiables this design is built around

1. **Anti-circularity is the load-bearing axiom.** Putting a legal threshold into the graph as a bare triple **launders an unverified transcription** (ADR-005/006, `graph.py:21-28`). A threshold value in the graph is trustworthy **only** if it carries `prov:wasDerivedFrom` back to a gate-verified statute extraction. This blueprint enforces that with a *runnable rdflib-only SPARQL audit* (the SHACL shape is the documentary form; the SPARQL is the CI gate, because pyshacl is absent — §0 verification posture, must-fix #1).
2. **The frozen controls + equivalence oracles stay reproducible.** FZK 5/1, Institute 2/2 on GlobalIds `0jbV$RErb7o9P7rp7ALEd$` / `3txvJd9V1BPhyU$48F$mnF`, Duplex 0/21 (both modes); the 220-row + 110-row equivalence projections of `equiv_oracle.json`; GATE-S (adversarial, 8/8 false-pass-free) and GATE-N (corpus byte-neutral). These are pinned to the **frozen oracle + the statute gate**, never to the graph's own output (ADR-006).
3. **The UNDETERMINED keystone must survive into the validation layer.** A binary `sh:conforms` cannot express tri-valued `True/False/None`. Any graph validation that collapses "not measured" into "not non-compliant" → "conformant" is **disqualified on the keystone** (the same disqualification C2-B took on GATE-S, `DECISION_MATRIX.md`). §3 solves this structurally.

### 0.4 The honest scope decision (must-fix #5: gate the verdict-into-graph effort)

ADR-006 is explicit that the **~150-rule scale trigger has NOT fired** (2 rules / 3 fixtures) and that the current graph is **verdict-equivalent to the flat table by construction** — a faithful copy of `classify()`, not an independent proof. Moving the *occupancy* decision into the graph (done, ADR-006) is already at the honest altitude for this scale. **Moving the *verdict* (`SpaceFinding.compliant`) into SHACL/SPARQL is a larger commitment that this blueprint does NOT recommend shipping at current scale** — it would be the premature abstraction ADR-005 §1 already caught once. Accordingly:

- **In scope now (justified by provenance integrity, not inference scale):** the T-Box vocabulary (§1), the triple-pattern bridge (§2), and — above all — the **provenance layer + the runnable anti-circularity audit** (§4), because the value of recording the gate's act as queryable triples is independent of rule count.
- **Designed but gated behind the scale trigger / a measured need:** the declarative SHACL verdict (§3) and the migration that inverts JSON↔graph truth-direction (§5 Phase 2+). `SpaceFinding.compliant` remains the **sole live verdict authority**; §3 is the target form for when scale demands it, and is presented with the trap that makes the naive version unsafe so it is never shipped wrong.

This honesty is itself a mitigation against over-claiming "unification" (must-fix #5): recasting the `Requirement` record + `parser.Operator` enum + `applicability.json` as triples is a *serialization*, not new capability, **unless** the rules become executable from the graph — which only the §5 Phase-2 truth-inversion delivers, and which creates a new drift surface this document explicitly polices.

---

## 1. Target T-Box architecture

### 1.1 Namespaces

```turtle
@prefix acc:      <https://acc.local/ontology#> .   # EXISTING — graph.py:41, DO NOT rename
@prefix legal:    <https://acc.local/legal#> .      # NEW — normative layer (law, thresholds, gate)
@prefix building: <https://acc.local/building#> .   # NEW — IFC-evaluation layer (measured facts)
@prefix ex:       <https://acc.local/data#> .       # A-Box instances + gate-run activity nodes
@prefix prov:     <http://www.w3.org/ns/prov#> .
@prefix sh:       <http://www.w3.org/ns/shacl#> .
@prefix owl:      <http://www.w3.org/2002/07/owl#> .
@prefix rdf:      <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs:     <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:      <http://www.w3.org/2001/XMLSchema#> .
@prefix dcterms:  <http://purl.org/dc/terms/> .     # reuse: dcterms:source (statute URL/citation), dcterms:identifier (rule_id)
@prefix skos:     <http://www.w3.org/2004/02/skos/core#> .  # reuse: cross-lingual hint glossary as a lexical layer
```

**Three deliberate namespace decisions.**
- The live `acc:` namespace and its 11 production predicates (`acc:hintText`, `acc:broaderTerm`, `acc:provenance`, `acc:statuteAnchored`, `acc:declaredDebt`, `acc:typeLabel`, plus the materialization predicates `acc:globalId`/`acc:name`/`acc:longName`/`acc:heightM`/`acc:floorAreaM2`) are reused **verbatim** — no rename, no breakage to `graph.py` or `materialize_ifcspaces`. `acc:Habitable`/`acc:Accessory` stay the occupancy classes and are merely **re-parented** under a new `legal:OccupancyClass`.
- `legal:` (law/threshold/gate) is kept **disjoint** from `acc:` so a threshold value can never be smuggled into the occupancy ontology as a bare triple — the ADR-006 honesty boundary made structural.
- **No QUDT, no heavy units ontology (must-fix #6).** The source design notes reached for `qudt:numericValue` / `unit:M`; that is disproportionate and unvetted for four magnitudes, and pulling a large external ontology contradicts the minimal-framework contract (`CLAUDE.md` "Excluded by design") and the supply-chain posture that rejected Neo4j on GPL-3.0. **Units are a plain `legal:thresholdUnit` string + an `xsd:decimal` value.** Likewise **no LKIF/ELI legal ontology** — a 3-term local vocabulary is the honest altitude for 2 rules / 3 fixtures. `dcterms:`/`skos:`/`prov:` are W3C-standard and reused for source/citation, the lexical glossary, and provenance respectively.

### 1.2 Core classes (class diagram)

```
legal:NormativeProvision                 a cited unit of law (article/comma) — NOT a value
  └─ instances: legal:NormProv_DM1975 (art.1+art.5), legal:NormProv_DPR380_art24 (c.5-bis/5-ter)

legal:ComplianceThreshold  ⊑ prov:Entity reified (value, unit, operator) limit; trustworthy ONLY with a derivation edge
  └─ instances: MinHeight_270, MinHeight_240_accessory, MinAeroRatio_0125,
                MinHeight_240_salvacasa (derogation, regime-bound)
                (monostanza surfaces are DELIBERATELY ABSENT — see §0.1 / §4 / §6)

legal:OccupancyClass                     the room→law seam
  ├─ acc:Habitable   (EXISTING, graph.py:56)
  └─ acc:Accessory   (EXISTING, graph.py:56)
       └─ acc:Disimpegno  ⊑ acc:Accessory     (statute-anchored Art.1 type, graph.py:162)
            └─ acc:Vestibolo ⊑ acc:Disimpegno (SYNTHETIC divergence, graph.py:163 — the ONLY
                                               node needing rdfs:subClassOf+ inference)

legal:RegulatoryRegime  ⊑ legal:ApplicabilityCondition-bearing scenario
  └─ instance: legal:SalvaCasa_5ter        (a cumulative-AND scenario — §1.4)

legal:GateVerification  ⊑ prov:Activity   the verify-never-trust run a threshold derives from
legal:StatuteProse      ⊑ prov:Entity     the exact prose bytes the gate consumed (sha256-pinned)

building:EvaluatedSpace                   an IfcSpace materialized into the store
  ├─ building:NonCompliantSpace  ⊑ building:EvaluatedSpace   (compliant == False)
  └─ building:UndeterminedSpace  ⊑ building:EvaluatedSpace   (compliant == None — keystone)
```

**Why `ComplianceThreshold ⊑ prov:Entity`** — this is the move that makes anti-circularity *checkable*: a threshold is a derived entity, so a threshold without a derivation is detectable (§5 audit). **Why only `NonCompliantSpace`/`UndeterminedSpace` are reified and there is no `CompliantSpace`** — this mirrors the tri-valued keystone: `None` (undetermined) must never be laundered into a pass, so the absence of a non-compliant/undetermined assertion is *never* sufficient to conclude compliance. Compliance is a *positively observed* condition (height ≥ bar AND, for habitable/unknown, aero ≥ 0.125), never the open-world default — this directly forecloses the "absence of a positive pass = undetermined" trap the critic flagged (must-fix #4: a not-yet-loaded space must be distinguishable from a measured failure; see §3.4 for how materialization, not open-world default, asserts undetermined). **`unknown` occupancy is not a class** — per `graph.py:202` / `checker.py:255` it maps to `acc:Habitable`'s requirement path (stricter bar + aero) at A-Box time.

### 1.3 Properties (property diagram)

```
OBJECT PROPERTIES
legal:hasThreshold              NormativeProvision → ComplianceThreshold
legal:appliesToOccupancy        ComplianceThreshold → OccupancyClass
legal:underRegime               ComplianceThreshold → RegulatoryRegime    (derogation marker)
legal:hasApplicabilityCondition RegulatoryRegime → ApplicabilityCondition (the AND-conjuncts)
building:hasOccupancy           EvaluatedSpace → OccupancyClass           (the classify() result)
building:violates               EvaluatedSpace → ComplianceThreshold      (DERIVED verdict edge)
prov:wasDerivedFrom             ComplianceThreshold → GateVerification    (REUSED — anti-circularity)
prov:used                       GateVerification → StatuteProse           (REUSED — what prose it read)

DATATYPE PROPERTIES (no QUDT — must-fix #6)
legal:thresholdValue            ComplianceThreshold → xsd:decimal         (2.70, 0.125, 2.40 …)
legal:thresholdUnit             ComplianceThreshold → xsd:string          ("m" | "ratio")
legal:comparisonOperator        ComplianceThreshold → xsd:string          (">=" — mirrors parser.Operator)
building:derivedHeight          EvaluatedSpace → xsd:decimal              (net height, metres)
building:derivedAeroRatio       EvaluatedSpace → xsd:decimal              (openable/floor area)
legal:corpusSha256 / legal:codeVersion / legal:gateOutcome / legal:gateFunction  (on GateVerification — §4)

REUSED (existing acc: substrate, DO NOT redefine)
acc:hintText / acc:broaderTerm / acc:provenance / acc:statuteAnchored / acc:declaredDebt
acc:typeLabel / acc:globalId / acc:name / acc:longName / acc:heightM / acc:floorAreaM2
```

`(value, unit, operator)` is split into three datatype properties mirroring the `Requirement` record (`checker.py` operator/value/unit) and the `parser.Operator` enum **one-to-one** — no semantic gap between the flat model and the graph. `building:derivedHeight`/`derivedAeroRatio` are **derived** (computed by `space_height`/`window_area` *outside* the graph and asserted in, exactly as `acc:heightM`/`acc:floorAreaM2` already are in `materialize_ifcspaces`); the graph does not recompute geometry. **Crucially, the materializer is the trust boundary** for these — see §3.4 / §4.4 / must-fix #2.

### 1.4 Salva-Casa as a cumulative-AND scenario (not a flag) + the merge it must split (must-fix #7)

The compiled rule today merges two distinct things into **one** exception clause's text (`rules/compiled/dm_1975_salva_casa.json:92-103`): the 2.40 m height derogation **and** the monostanza surfaces ("minimum internal height 2,40 m … alloggio monostanza … 20 m² / 28 m²"). This blueprint **splits them**:

- The **2.40 m derogation** becomes a gate-provenanced `legal:ComplianceThreshold` bound to the regime (below).
- The **monostanza surfaces** stay **out of the graph** entirely until `verify_monostanza_against_text` is runtime-wired (§4, §6) — they are not yet runtime-gate-checked (ADR-005 (ii)), so they cannot become graph facts.

The statute (`rules/dm_1975_salva_casa.md`, DPR 380/2001 art.24 c.5-ter) admits comma 5-ter **only if ALL** of: recupero/cambio d'uso **AND** adattabilità DM 236/1989 **AND** concurrent ristrutturazione. The regime is modelled as a class with three conjuncts so the cumulative-AND is graph-visible:

```turtle
legal:SalvaCasa_5ter a legal:RegulatoryRegime ;
    rdfs:label "DPR 380/2001 art.24 c.5-ter (Salva Casa)"@en ;
    dcterms:source <https://www.normattiva.it/dpr-380-2001#art24-c5ter> ;
    legal:hasApplicabilityCondition
        legal:Cond_RecuperoOrCambioUso ,         # patrimonio edilizio esistente
        legal:Cond_Adattabilita_DM236_1989 ,     # requisiti di adattabilità
        legal:Cond_RistrutturazioneConcorrente . # concurrent works
legal:MinHeight_240_salvacasa a legal:ComplianceThreshold ;
    legal:thresholdValue "2.40"^^xsd:decimal ; legal:thresholdUnit "m" ;
    legal:comparisonOperator ">=" ;
    legal:appliesToOccupancy acc:Habitable ;
    legal:underRegime legal:SalvaCasa_5ter ;     # ← scenario gate: bound to the regime, NOT the baseline path
    prov:wasDerivedFrom ex:gateRun_DM1975 .
```

**Honest limitation (must-fix #7, critic-confirmed):** none of the three AND-conditions has IFC-derivable evidence on any current fixture, so the regime is **operator-asserted** — exactly like the existing `--salva-casa` flag (ADR-005). The graph therefore adds *structure and a gate-provenanced derogation value*, **not** verification of the regime's applicability. The frozen control is **FZK `--salva-casa` = 1 violation**; this is reproduced declaratively by the baseline verdict query (§3.5 / §5 Phase-3 DoD) selecting the regime threshold **only** when the operator asserts the regime, and by `FILTER NOT EXISTS { ?thr legal:underRegime ?r }` keeping the default path from ever silently consuming the derogated 2.40 m bar. Until an IFC Pset can ground any conjunct, an asserted-but-unsatisfiable regime surfaces as **undetermined for the derogation path specifically**, never a silent derogation.

### 1.5 What was parse-validated for this section

The TBox above (re-parented `acc:` classes, `legal:`/`building:` classes, the `ComplianceThreshold ⊑ prov:Entity` and `GateVerification ⊑ prov:Activity` axioms, all object/datatype properties) plus a representative A-Box parsed clean in rdflib 7.6.0 (77 triples total). The single inference the codebase exercises — `acc:Vestibolo rdfs:subClassOf+ acc:Accessory` — returns `True` via SPARQL property-path, confirming the design stays within **pure RDFS / OWL-RL** (no cardinality-as-DL, no `owl:Restriction` reasoning, no tableau-forcing disjointness).

---

## 2. Triple-pattern bridge (concrete .ttl)

One IFC-derived space (`ex:Space_7`) linked to the two thresholds that govern it and their gate provenance, **plus** a deliberately-laundered node so the validator (§3, §5) has something to flag. This is the executable heart of the anti-circularity contract: every threshold carries `prov:wasDerivedFrom` a `legal:GateVerification`; `ex:Space_8` shows the **undetermined** case (height present, aero **triple omitted** because the measurement was not trustworthy — see §3.4).

```turtle
@prefix acc:      <https://acc.local/ontology#> .
@prefix legal:    <https://acc.local/legal#> .
@prefix building: <https://acc.local/building#> .
@prefix ex:       <https://acc.local/data#> .
@prefix prov:     <http://www.w3.org/ns/prov#> .
@prefix xsd:      <http://www.w3.org/2001/XMLSchema#> .
@prefix dcterms:  <http://purl.org/dc/terms/> .
@prefix rdfs:     <http://www.w3.org/2000/01/rdf-schema#> .

# 1. PROVENANCE ROOT — the statute prose (sha256-pinned, answer-key excluded) the gate read.
ex:statuteProse_DM1975 a legal:StatuteProse ;
    dcterms:source "DM Sanità 5 luglio 1975, art.1 + art.5" ;
    legal:corpusSha256 "9f2cc4a1deadbeef" ;                 # exact prose bytes verified (placeholder digest)
    legal:corpusScope  "crosscheck_corpus: statute quote blocks only; answer-key Target-rule block excluded" .

# 2. THE GATE ACTIVITY — the verify_rule_against_text run (NOT a bare fact). §4 specifies how it is EMITTED.
ex:gateRun_DM1975 a legal:GateVerification ;
    rdfs:label         "verify_rule_against_text over DM-1975 statute prose"@en ;
    prov:used          ex:statuteProse_DM1975 ;
    legal:gateFunction "parser.verify_rule_against_text" ;
    legal:codeVersion  "git:86a3141" ;                      # WHICH gate code ran (git SHA)
    legal:gateOutcome  "verified" ;                         # ONLY 'verified' licenses a threshold
    prov:endedAtTime   "2026-06-30T14:12:09Z"^^xsd:dateTime .

# 3. THRESHOLD NODES — value + unit + operator + PROVENANCE back to the gate (with the bound span).
legal:MinHeight_270 a legal:ComplianceThreshold ;
    rdfs:label "minimum internal height, habitable room (2.70 m)"@en ;
    legal:appliesToOccupancy acc:Habitable ;
    legal:thresholdValue "2.70"^^xsd:decimal ; legal:thresholdUnit "m" ;
    legal:comparisonOperator ">=" ;
    legal:statuteAnchor "DM1975-art1" ;
    legal:boundSpan "L'altezza minima interna utile dei locali adibiti ad abitazione è fissata in m 2,70"@it ;
    prov:wasDerivedFrom ex:gateRun_DM1975 .

legal:MinAeroRatio_0125 a legal:ComplianceThreshold ;
    rdfs:label "minimum openable-window / floor-area ratio (1/8 = 0.125)"@en ;
    legal:appliesToOccupancy acc:Habitable ;
    legal:thresholdValue "0.125"^^xsd:decimal ; legal:thresholdUnit "ratio" ;
    legal:comparisonOperator ">=" ;
    legal:statuteAnchor "DM1975-art5" ;
    legal:boundSpan "la superficie finestrata apribile non potrà essere inferiore a 1/8 della superficie del pavimento"@it ;
    prov:wasDerivedFrom ex:gateRun_DM1975 .

legal:MinHeight_240_accessory a legal:ComplianceThreshold ;
    legal:appliesToOccupancy acc:Accessory ;
    legal:thresholdValue "2.40"^^xsd:decimal ; legal:thresholdUnit "m" ;
    legal:comparisonOperator ">=" ;
    legal:statuteAnchor "DM1975-art1-reduced" ;
    prov:wasDerivedFrom ex:gateRun_DM1975 .

# 4. THE IFC-DERIVED SPACE (symbolic lane: IfcOpenShell quantities + classify()).
#    MEASUREMENTS, not legal facts — provenance is the IFC model, NOT the gate.
ex:Space_7 a building:EvaluatedSpace ;
    building:hasOccupancy acc:Habitable ;
    rdfs:label "Soggiorno"@it ;
    acc:name "Space_7" ;
    building:derivedHeight    "2.70"^^xsd:decimal ;          # Qto height, m
    building:derivedAeroRatio "0.140"^^xsd:decimal ;         # openable window area / NetFloorArea
    acc:floorAreaM2 "24.00"^^xsd:decimal ;
    acc:provenance "IFC: Qto_SpaceBaseQuantities + IfcRelSpaceBoundary windows" ;
    building:governedBy legal:MinHeight_270 , legal:MinAeroRatio_0125 .

# 4a. COMPLIANT: habitable needs BOTH height_ok + aero_ok (keystone). 2.70>=2.70 AND 0.140>=0.125.
ex:Finding_Space_7 a building:ComplianceFinding ;
    building:ofSpace ex:Space_7 ;
    building:heightOk true ; building:aeroOk true ; building:compliant true .

# 4b. UNDETERMINED: habitable, height present, aeroRatio TRIPLE OMITTED (trust-failed measurement).
#     The materializer wrote NO aeroRatio triple (NOT a laundered 0.0) so the keystone yields None.
ex:Space_8 a building:EvaluatedSpace ;
    building:hasOccupancy acc:Habitable ;
    building:derivedHeight "2.80"^^xsd:decimal .
    # (no building:derivedAeroRatio) — see §3.4 / must-fix #2

# 5. THE LAUNDERED NODE A VALIDATOR MUST FLAG — threshold with NO gate provenance.
legal:MinHeight_240_UNVERIFIED a legal:ComplianceThreshold ;
    rdfs:label "LAUNDERED: 2.40 m with NO gate provenance (falsely anchored)"@en ;
    legal:appliesToOccupancy acc:Accessory ;
    legal:thresholdValue "2.40"^^xsd:decimal ; legal:thresholdUnit "m" ;
    legal:comparisonOperator ">=" .
    # NO prov:wasDerivedFrom  ← the defect §3/§5 catch
```

**Executed result (rdflib 7.6.0):** the bridge + TBox parsed to 77 triples; the §5 anti-circularity audit returned **exactly** `legal:MinHeight_240_UNVERIFIED`; the three gate-derived thresholds passed clean; the verdict query (§3.5) returned `[]` (Space_7 in bounds; Space_8 has no aeroRatio so it is *undetermined*, not a verdict). Threshold values cross-checked against the codebase: habitable 2.70 / accessory 2.40 / aero 0.125 match `rules/compiled/dm_1975_salva_casa.json:106-109` and the gate; the keystone "habitable needs height_ok AND aero_ok" matches `checker.py:255-256`.

---

## 3. Deterministic validation: SHACL vs SPARQL

### 3.1 The question and the disqualifier

Can the **graph layer** decide the verdict deterministically *without ever turning missing data into a silent pass*? The disqualifier is fixed by §0.3.3: a candidate that collapses "not measured" into "conformant" is out. Two candidates:

- **(A) SPARQL CONSTRUCT/ASK** — pattern-match a space below threshold, materialize `?space a building:NonCompliantSpace`; companion query for the pass case.
- **(B) SHACL shapes** — `sh:NodeShape` targets habitable/accessory spaces with presence (`sh:minCount`) + range (`sh:minInclusive`) constraints; an engine returns a `sh:ValidationReport`.

### 3.2 Evaluation

| Axis | (A) SPARQL CONSTRUCT/ASK | (B) SHACL shapes |
|---|---|---|
| **Determinism** | Deterministic given a fixed query+store, but the verdict is *derived from what you remembered to assert*; absence of a `NonCompliantSpace` triple is ambiguous (pass *or* never-evaluated). | Deterministic: a validator is a total function `(data, shapes) → ValidationReport` enumerating every focus node touched and every constraint outcome. |
| **Open- vs closed-world** | SPARQL is open-world + **negation-as-failure**: `FILTER NOT EXISTS { ?s building:netHeight ?h }` treats "no height triple" identically to "height I forgot to load" → **latent silent pass** (the C-2/laundering class). | Closed-world *per shape*. A value-constraint (`sh:minInclusive`) is **vacuously true on an empty value set**, but `sh:minCount` makes *absence itself* a separately reportable result. That orthogonality is what models three-valued logic. |
| **UNDETERMINED (keystone)** | Requires three mutually-exclusive CONSTRUCTs (Compliant / NonCompliant / Undetermined) that must partition with no gap — and **nothing in SPARQL enforces the partition**. A gap = a space with no verdict triple = whatever the reader defaults to (usually "pass"). | Falls out of report **structure**: a `MinCount` result = "measurement missing" (UNDETERMINED); a `MinInclusive` result on a *present* value = "measured and below" (VIOLATION). The conformance algorithm guarantees every targeted node is visited. |
| **Auditability** | A CONSTRUCT result is "here is a triple"; the *why* must be hand-built. | The `sh:ValidationReport` is itself RDF: `sh:focusNode`, `sh:resultPath`, `sh:sourceConstraintComponent`, `sh:value`, `sh:resultMessage` — a machine-readable audit trail aligned with the project's `file:line` discipline. |
| **Tooling** | rdflib `==7.6.0` already ships SPARQL 1.1 — **zero new dependency**, runs today. | `pyshacl` is a **new** dependency and **is not installed** (verified). It is the de-facto Python SHACL engine but adds a pinned supply-chain item to vet against the GPL-3.0/Neo4j posture. |

### 3.3 Decision: SHACL is the PREFERRED *design* for the verdict — but it is scale-gated, and the runnable enforcement today is SPARQL

SHACL wins on the axis the whole project is built around (UNDETERMINED must not launder into PASS) because it gives a **structural** distinction between "absent" (`sh:minCount`) and "present-and-failing" (`sh:minInclusive`); SPARQL's negation-as-failure conflates them. It also wins on auditability and conformance totality.

**However (must-fix #1 + #5):**
1. `pyshacl` is absent, so **no `sh:validate` has been run** — the SHACL artifacts below are parse-valid Turtle only. Shipping the SHACL verdict requires *adding and license-vetting pyshacl* and actually running it in CI on instance graphs. Until then, the **runnable** check is SPARQL (§3.5, §5 — executed).
2. The verdict-into-graph move is **not justified at 2 rules / 3 fixtures** (§0.4). So §3 is the **target form**, presented complete and correct, to be adopted only when the scale trigger fires; the live verdict stays `SpaceFinding.compliant`.

The hybrid we adopt **when it ships**: SHACL for the verdict + a thin Python post-pass over the `sh:ValidationReport` to map report → tri-valued `True/False/None` (because `sh:conforms` is binary and the keystone is ternary).

### 3.4 The trap, and the correct shapes (the keystone made declarative)

A naive single shape is a **silent pass on missing data**:

```turtle
# ❌ WRONG — vacuously conforms on an unmeasured habitable space (re-opens the Duplex 21/21 / ADR-003 hole).
building:HabitableShapeBAD a sh:NodeShape ;
    sh:targetClass building:HabitableSpace ;
    sh:property [ sh:path building:netHeight ; sh:minInclusive 2.70 ] .
```

`sh:minInclusive` quantifies over the value set; over the **empty** set it is vacuously true → `sh:conforms=true` → the unmeasured space reads conformant. The fix splits **presence** (`sh:minCount`, the keystone) from **range** (`sh:minInclusive`):

```turtle
@prefix sh:       <http://www.w3.org/ns/shacl#> .
@prefix xsd:      <http://www.w3.org/2001/XMLSchema#> .
@prefix building: <https://acc.local/building#> .

building:HabitableShape a sh:NodeShape ;
    sh:targetClass building:HabitableSpace ;
    # (1) PRESENCE — keystone. Missing net height => MinCount result => UNDETERMINED.
    sh:property [ sh:path building:netHeight ; sh:minCount 1 ; sh:maxCount 1 ;
                  sh:datatype xsd:decimal ;
                  sh:message "UNDETERMINED: net height not measured (Qto/geometry absent)" ] ;
    # (1b) RANGE — bites only a PRESENT value below the bar => VIOLATION (height_ok=false).
    sh:property [ sh:path building:netHeight ; sh:minInclusive 2.70 ;
                  sh:message "VIOLATION: net height < 2.70 m (DM 1975 art.1)" ] ;
    # (2) PRESENCE of aero ratio — keystone. Missing => UNDETERMINED.
    sh:property [ sh:path building:aeroRatio ; sh:minCount 1 ; sh:maxCount 1 ;
                  sh:datatype xsd:decimal ;
                  sh:message "UNDETERMINED: aero ratio not measurable (window/floor area absent or untrustworthy)" ] ;
    # (2b) RANGE — present aero below 1/8 => VIOLATION (aero_ok=false).
    sh:property [ sh:path building:aeroRatio ; sh:minInclusive 0.125 ;
                  sh:message "VIOLATION: openable/floor area < 1/8 (DM 1975 art.5)" ] .

building:AccessoryShape a sh:NodeShape ;
    sh:targetClass building:AccessorySpace ;
    # Height ONLY — DELIBERATELY SILENT on aero (aero N/A, DM1975 art.5 inapplicable to accessories).
    sh:property [ sh:path building:netHeight ; sh:minCount 1 ; sh:maxCount 1 ;
                  sh:datatype xsd:decimal ;
                  sh:message "UNDETERMINED: net height not measured" ] ;
    sh:property [ sh:path building:netHeight ; sh:minInclusive 2.40 ;
                  sh:message "VIOLATION: net height < 2.40 m (DM 1975 art.1 reduced)" ] .
```

The accessory shape's **silence** on aero is the closed-world-per-shape boundary doing exactly the right thing: an accessory space with height OK and no aeroRatio yields zero results ⇒ compliant (aero N/A), matching `checker.py:255` `required = [self.height_ok]`. `unknown` occupancy is typed to `building:HabitableSpace` at materialization (stricter 2.70 bar + aero), reproducing `checker.py:255` / `graph.py:202`.

**§3.4 — materialization is the real trust boundary (must-fix #2, the critic's central correction).** The genuine laundering risk is the **measured** side, not the threshold side. `checker.py` runs the F-C trustworthiness test + L-2 conservative numerator (ADR-007b): an untrustworthy/absurd window yields `aero_ok=None`. The A-Box materializer **MUST run that F-C/L-2 logic and the height key-lookup BEFORE writing, and OMIT the quantity triple (no laundered 0.0/None) when trust fails** — exactly as `ex:Space_8` in §2 has no `building:derivedAeroRatio`. If the materializer instead wrote `aeroRatio 0.0`, `sh:minCount` would never fire and UNDETERMINED would collapse to a verdict — a laundering bug structurally identical to a bare threshold triple. **Required test (mirrors the codepoint-exact applicability pin):** a trust-failed window must produce **zero** `aeroRatio` triples and the verdict must resolve to `None`. This test is part of the frozen battery DoD (§5).

### 3.5 Report → tri-valued verdict (mandatory post-pass) + the runnable SPARQL form

`sh:conforms` is binary; the keystone is ternary. The post-pass classifies per focus node, **MinCount-dominant** so absence always beats a coincidental range pass:

```python
# Over the pyshacl sh:ValidationReport graph. Precedence:
#   any MinCount result on a space   => None  (UNDETERMINED — a required measurement was absent)
#   else any other result            => False (VIOLATION — a present value broke a range/datatype constraint)
#   else                             => True  (COMPLIANT — every applicable, PRESENT check passed)
SH = Namespace("http://www.w3.org/ns/shacl#")
def verdict_for(space, report):
    results = list(report.subjects(SH.focusNode, space))
    comps   = {report.value(r, SH.sourceConstraintComponent) for r in results}
    if SH.MinCountConstraintComponent in comps:
        return None
    if results:
        return False
    return True
```

This reproduces `SpaceFinding.compliant` (`checker.py:247-259`) exactly: MinCount-missing ⇒ `None`, present-and-below ⇒ `False`, all-present-in-bounds ⇒ `True`. **It must be pinned as a differential oracle against the existing Python keystone** (not against the graph's own output) — the same rigor ADR-006 uses (must-fix #4). The post-pass precedence logic was unit-verified in this environment (MinCount-dominant ⇒ None; else any ⇒ False; else True).

**The runnable enforcement today (executed, rdflib-only — this is what goes in CI now).** Because pyshacl is absent and the verdict is scale-gated, the *currently shippable* deterministic check is the verdict SPARQL, with the keystone honored by the materializer omitting untrustworthy triples (§3.4) and the baseline path walled off from the regime:

```sparql
PREFIX legal:    <https://acc.local/legal#>
PREFIX building: <https://acc.local/building#>
SELECT ?space ?thr ?derived ?limit WHERE {
  ?space a building:EvaluatedSpace ;
         building:hasOccupancy ?occ ;
         building:derivedHeight ?derived .
  ?thr   a legal:ComplianceThreshold ;
         legal:appliesToOccupancy ?occ ;
         legal:thresholdValue ?limit ;
         legal:comparisonOperator ">=" .
  FILTER(?derived < ?limit)
  FILTER NOT EXISTS { ?thr legal:underRegime ?r }   # baseline only; Salva-Casa is §1.4-gated
}
```

This returns the height-violations of *present* values; a space with an omitted measurement (Space_8) produces **no row** here and is classified UNDETERMINED by the materializer's positive `building:UndeterminedSpace` assertion (§1.2) — never by open-world default (must-fix #4). The query was executed and returned `[]` on the in-bounds sample.

### 3.6 Datatype contract (must-fix #6)

IfcOpenShell yields Python floats; a `sh:datatype` mismatch turns the datatype constraint into a spurious VIOLATION/UNDETERMINED. The materializer MUST emit **`xsd:decimal`** (not `xsd:double`) to match the shapes and the threshold values, and a test must pin that contract (mirroring the codepoint-exact applicability pin). All `^^xsd:decimal` literals in this document are consistent across §1–§5.

---

## 4. Provenance & Track-2

### 4.1 The anti-laundering invariant

> A `legal:ComplianceThreshold` value is trustworthy **iff** it carries `prov:wasDerivedFrom` a `legal:GateVerification` whose `legal:gateOutcome` is `"verified"`, and that activity `prov:used` the `legal:StatuteProse` it consumed. A threshold without that chain is laundered debt — and is **queryably detectable** as such (§4.3).

This mirrors code: the checker only ever consumes numbers the gate re-derived (answer-key excluded, unique-or-RAISE). The graph does not *replace* the gate; it **records the gate's act as permanent, queryable triples**.

### 4.2 The gate must EMIT a provenance node — today it does not (must-fix #3, the critic's central circularity correction)

The whole anti-circularity guarantee hangs on `prov:wasDerivedFrom → legal:GateVerification`. But the gates in `parser.py` (`verify_rule_against_text:346`, `verify_accessory_selection_against_text:466`, `verify_monostanza_against_text:589`) **return dicts or RAISE — they emit no RDF, no corpus hash, no codeVersion.** So a `prov:wasDerivedFrom` edge written today would be a **hand-authored token edge pointing at a node nobody minted from a real gate run** — which is *precisely the laundering the design claims to prevent*. A shape/query that checks only for the *presence* of an edge proves an edge exists, not that the number traces to a verify-never-trust execution over the prose.

**Therefore provenance enforcement is only genuine once the gate emits the node. Minimum required payload** (this is a prerequisite work item, not an assumption):

```turtle
ex:gateRun_DM1975 a legal:GateVerification ;
    prov:used          ex:statuteProse_DM1975 ;        # StatuteProse{ legal:corpusSha256, legal:corpusScope }
    legal:gateFunction "parser.verify_rule_against_text" ;
    legal:codeVersion  "git:86a3141" ;                 # git SHA — WHICH gate code ran (closes M-9)
    legal:gateOutcome  "verified" ;                    # only 'verified' licenses a threshold
    prov:endedAtTime   "2026-06-30T14:12:09Z"^^xsd:dateTime .
```

- **Content-addressing for idempotency/diffability:** the gate-run node's IRI should be the hash of `(corpusSha256 + codeVersion + gateOutcome)`, so a re-run over identical prose+code is the *same* node (idempotent), and a prose or code change mints a *different* node (diffable). This makes the provenance graph regenerable and auditable rather than minting a fresh timestamped node per invocation.
- **`StatuteProse` carries `legal:corpusSha256`** = the exact answer-key-excluded prose bytes the gate cross-checked, so the chain proves derivation from *those bytes*, not merely "from DM-1975".

Until `verify_*_against_text` return these RDF entities, the structural provenance check enforces a shape against data the pipeline cannot produce — so **the prerequisite for trusting any `prov:wasDerivedFrom` edge is wiring the gate to emit the content-addressed node above.** This blueprint states that as a hard precondition, not a nicety.

### 4.3 The runnable anti-circularity audit (executed, rdflib-only — the ONE check adopted)

Per must-fix #1 we pick **one** runnable anti-circularity check and add it to the frozen battery. Because pyshacl is absent, that check is the rdflib-only `FILTER NOT EXISTS` audit — **this set must be empty; a non-empty result is a laundered triple and a hard CI failure**:

```sparql
PREFIX legal: <https://acc.local/legal#>
PREFIX prov:  <http://www.w3.org/ns/prov#>
SELECT ?thr WHERE {
  ?thr a legal:ComplianceThreshold .
  FILTER NOT EXISTS {
    ?thr prov:wasDerivedFrom ?run .
    ?run a legal:GateVerification ; legal:gateOutcome "verified" .
  }
}
```

**Executed result:** with the §2 bridge, this returns **exactly** `legal:MinHeight_240_UNVERIFIED`; the three gate-derived nodes pass clean. This is the store-level analog of ADR-002's "no number reaches the checker unless provably bound," and it runs today with only `rdflib==7.6.0`. (The SHACL `legal:ThresholdProvenanceShape` below is the *documentary* equivalent for when pyshacl is adopted; it parses as valid Turtle but has **not** been `sh:validate`-executed.)

```turtle
# DOCUMENTARY ONLY (pyshacl absent — parse-valid Turtle, NOT sh:validate-executed):
legal:ThresholdProvenanceShape a sh:NodeShape ;
    sh:targetClass legal:ComplianceThreshold ;
    sh:property [ sh:path legal:thresholdValue ; sh:datatype xsd:decimal ; sh:minCount 1 ; sh:maxCount 1 ] ;
    sh:property [ sh:path legal:comparisonOperator ; sh:in ( ">=" "<=" ">" "<" "==" ) ;
                  sh:minCount 1 ; sh:maxCount 1 ] ;          # mirrors parser.Operator
    sh:property [ sh:path prov:wasDerivedFrom ; sh:class legal:GateVerification ; sh:minCount 1 ;
                  sh:message "Anti-circularity: a ComplianceThreshold MUST be prov:wasDerivedFrom a verified legal:GateVerification (ADR-005/006)." ] .
```

### 4.4 LLM / Track-2 confidence triples — auditable escalation, not the live verdict

Occupancy on the **live** path is deterministic and graph-backed (`occupancy_via_graph`, the M-4 tokenized classifier) — an offline checker must **not** call an untrusted model at verdict time (ADR-007). So `acc:occupancySource` is a discriminator: `"graph"` for the deterministic SPARQL path, `"llm"` for an *escalation* of a low-confidence / graph-`unknown` space. The LLM shape carries confidence **and** the pinned model digest so escalation is auditable:

```turtle
ex:model_llama31_8b a prov:SoftwareAgent , prov:Entity ;
    rdfs:label "llama3.1:8b (Q4_K_M)" ;
    acc:modelTag "llama3.1:8b" ;
    acc:modelDigest "sha256:46e0c10c039e" .                 # the digest, not a floating tag (closes H-2)

ex:Space_R301 a building:EvaluatedSpace ;
    acc:globalId "0jbV$RErb7o9P7rp7ALEd$" ;                 # GlobalId-exact (ADR-006); urn-percent-quoted at A-Box time
    acc:name "Soggiorno con bagno" ;
    building:hasOccupancy acc:Habitable ;
    acc:occupancyConfidence "0.82"^^xsd:decimal ;
    acc:occupancySource "llm" ;
    prov:wasDerivedFrom ex:model_llama31_8b .               # WHICH model digest classified it
```

A graph-`unknown` that is never escalated stays `unknown` and is evaluated at the stricter habitable bar (the fail-closed direction). **Honest gap (carried):** `llama3.1:8b` via Ollama structured output does not natively emit a calibrated occupancy confidence; the source of `acc:occupancyConfidence` (logprobs vs self-report vs a deterministic proxy) and the escalation threshold must be *defined before* the `"llm"` source is wired live (§6). The measured-side trust boundary (§3.4) is unaffected — geometry never comes from the model.

### 4.5 How this collapses H-2 / M-1 / M-9 into one invariant

- **H-2 (pin the LLM digest):** every LLM-derived node `prov:wasDerivedFrom` a model entity carrying `acc:modelDigest` — the pin lives on every classification it produced, not in an ADR comment. A retag produces a different digest node, visible in §4.4's query.
- **M-1 (`--offline` backfills DEFAULT_THRESHOLDS, source-indistinguishable):** a defaulted number has **no gate run** to point `prov:wasDerivedFrom` at, so it fails §4.3's audit — "indistinguishable from gate-verified" becomes structurally impossible.
- **M-9 (`from_rules_json` trusts compiled numbers without re-running the gate):** the audit *is* the inspection; a label like `source:"llm"` cannot fake a `prov:wasDerivedFrom → verified GateVerification` chain, and `legal:codeVersion` answers "which gate code produced this number."

### 4.6 Honesty boundary (ADR-006)

Storing provenance does **not** broaden anchoring: only the 4 Art.1 occupancy tokens and the gate-verified thresholds are anchored; the 47 cross-lingual hints stay `acc:declaredDebt` (optionally as `skos:altLabel` lexical edges) — explicitly *un-provenanced-to-statute* and queryable as such. And per ADR-005 (ii), the monostanza constants stay **out** of the graph as `legal:ComplianceThreshold` nodes until `verify_monostanza_against_text` is runtime-wired — the graph cannot launder them.

---

## 5. Migration plan (phased, controls-preserving)

### 5.0 Starting state and the immovable invariant

Three rule-bearing substrates (only one a graph): the `graph.py` occupancy ontology; `rules/applicability.json` (codepoint-pinned to frozen Python); `rules/compiled/dm_1975_salva_casa.json` (gate-verified thresholds + selection). The de-facto runtime SoT for values is Python `_dm1975_requirements`/`Thresholds`. **Immovable invariant:** the gate over the statute prose is the only thing that mints a trustworthy number/term; the graph is a **consumer** of gate output, never a substitute. Dependency direction stays `checker → graph → parser`; `graph.py` must never `import checker` (its module-top `import ifcopenshell` sys-exits without the wheel). **`SpaceFinding.compliant` is byte-untouched in every phase.**

Every phase is gated by the **full frozen battery**: 220-row + 110-row equivalence oracles 0-drift; FZK 5/1 + Institute 2/2 (GlobalId-frozen) + Duplex 0/21 both modes; `probe_controls` HELD; GATE-S 8/8 false-pass-free; GATE-N byte-neutral. A phase is not done until all are green.

### 5.1 Phase 0 — Provenance scaffolding + the runnable audit (no verdict path change)

- **Changes.** Wire `verify_rule_against_text` / `verify_accessory_selection_against_text` to **emit** the content-addressed `legal:GateVerification` + `legal:StatuteProse` nodes of §4.2 (the prerequisite — must-fix #3) for the values the gate *already* authorizes; extend `graph.build_ontology` to attach `prov:wasDerivedFrom` to the already-anchored 4 Art.1 tokens. Add the §4.3 SPARQL audit as a CI check.
- **Anti-circularity.** No *new* value enters the graph; provenance is attached to what the gate already authorized. The audit is wired and runs (returns `[]` on conformant data).
- **DoD.** §4.3 audit returns `[]`; a new test asserts anchored hints carry `prov:wasDerivedFrom` and debt hints do not (and are never `statuteAnchored`); full battery green; **no verdict moves** (graph still answers occupancy only).

### 5.2 Phase 1 — Thresholds become graph-generated, gate as SoT (env-flag, differential oracle)

- **Changes.** New `parser.gate_verified_requirements(law_text)` returns the 4 thresholds **as provenance-bearing records** (mirroring `gate_verified_selection`). `graph.build_requirement_graph` writes them as `legal:ComplianceThreshold` Entities with the `prov:wasDerivedFrom` edge; the §4.3 audit runs at build time and **refuses the build** if any threshold lacks provenance. `checker.Thresholds.resolve` gains a graph-backed path behind `ACC_THRESHOLDS_BACKEND={python|graph}` (default `python`).
- **Anti-circularity (the migration's own check).** A test asserts `graph_resolve(metric,occ) == python_resolve(metric,occ)` bit-for-bit for all records — the graph output is validated **against the gate-verified Python (the differential oracle), never against itself** (must-fix #4). Monostanza stays Python-only (ADR-005 (ii)).
- **DoD.** With `ACC_THRESHOLDS_BACKEND=graph`: report `thresholds` block byte-identical; 220/110 oracles 0-drift; GATE-N byte-neutral; §4.3 audit `[]`; differential graph↔python test green. Flip default only after a full green run; `python` is a one-env-var rollback.

### 5.3 Phase 2 — applicability.json + compiled selection become graph projections (truth-direction inverts)

- **Changes.** `graph.emit_applicability_json()` serializes occupancy nodes back to today's exact schema; the compiled `selection[]` is emitted from gate-anchored hint nodes. The **direction of truth inverts**: graph (gate-provenanced) → JSON (generated artifact), regenerated in CI. **New drift surface, explicitly policed (must-fix #5):** a generation-time check asserts the emitted JSON is set-equal incl. codepoints to the frozen tuples; the checked-in JSON is kept as a committed snapshot with a CI check that it equals the freshly generated output (preserving the codepoint anti-drift guard as a reference).
- **DoD.** Regenerated `applicability.json` byte-identical to the checked-in file (so `load_applicability` + `test_applicability_table` untouched); regenerated `selection[]` byte-identical; 220/110 green; debt edges never `statuteAnchored`.

### 5.4 Phase 3 — SHACL as runtime model-validation (additive, fail-closed) — SCALE-GATED

- **Precondition (must-fix #1 + #5):** add and license-vet `pyshacl` (Apache-2.0 — compatible; vs the rejected GPL-3.0 Neo4j), pin it, confirm its rdflib requirement is compatible with `rdflib==7.6.0` (if it forces a bump, re-run all 220/110 oracles under the new rdflib *first*, since SPARQL behavior is verdict-load-bearing). **AND** justify the verdict-into-graph move by a real multi-jurisdiction / rule-count need; otherwise this phase does not ship and `SpaceFinding.compliant` stays the live verdict.
- **Changes (if precondition met).** Add the §3.4 shapes + §3.5 post-pass as an **additive** `report["shacl"]` channel that can only move a space toward undetermined/refusal — **never** folded into `compliant`/`violations`/`spaces_undetermined`. The §3.4 materializer trust-boundary test (trust-failed window ⇒ zero aeroRatio triples ⇒ `None`) and the §3.6 datatype-contract test are added to the battery (must-fix #2, #6).
- **DoD.** SHACL channel additive; the post-pass reproduces `SpaceFinding.compliant` as a differential oracle on all 110 rows; FZK 5/1 (and `--salva-casa` = 1 — must-fix #7) / Institute 2/2 / Duplex 0/21 unchanged; GATE-S 8/8; a test pins that no fixture's `compliant`/`violations`/`undetermined` moved.

### 5.5 Phase 4 (DEFERRED, trigger-gated) — Oxigraph backend

- One-line `Graph(store="Oxigraph")` swap via `oxrdflib` (Apache-2.0, not GPL); all SPARQL is already standard 1.1. **Trigger:** a *measured* per-space latency budget on a real large IFC — which **does not exist yet** (no held-out third-party file, `DECISION_MATRIX` limitation), so the trigger is **currently unmeasurable** and the phase is honestly unschedulable. **Do not pre-optimize** (ADR-005 §1). DoD requires byte-identical 220/110 output under both backends.

### 5.6 Phase 5 (DEFERRED) — OWL/RDFS inference at scale

Only if a real (non-synthetic) fixture needs transitive subsumption. The `acc:Vestibolo` path is the capability proof; **no real fixture exercises it** (must-fix: scalability claims are unfalsifiable at this corpus). Documented as "capability proven, production deferred indefinitely" unless a real need appears.

### 5.7 Honest risks

1. **Per-space SPARQL at scale** — O(spaces × tokens × metrics) rdflib overhead. *Mitigation:* resolve the small static requirement set once into a dict at build time, not per space; Oxigraph is the escape hatch. *Trigger:* measured latency (currently unmeasurable, §5.5). Do not pre-optimize.
2. **The circularity trap (central).** *Mitigation (structural):* the §4.3 audit makes a provenance-less threshold a build/CI failure; the differential graph↔gate test (§5.2) catches drift; monostanza is forbidden from the graph; **and the gate must emit the content-addressed node (§4.2) before any `prov:wasDerivedFrom` edge is trusted** — without that, the check enforces presence of a hand-written edge, not derivation (must-fix #3).
3. **Materialization laundering (the real silent-pass surface, must-fix #2).** *Mitigation:* the materializer runs F-C/L-2 + height key-lookup before writing and OMITS untrustworthy quantity triples; pinned by a test (§3.4 / §5.4).
4. **pyshacl dependency.** *Mitigation:* pin + license-vet; re-run oracles if it forces an rdflib bump; until adopted, the runnable check is SPARQL (§4.3) — no safety claim rests on an unexecuted shape.
5. **Truth-inversion drift (Phase 2).** *Mitigation:* committed snapshot + CI equality check + codepoint pin.
6. **Honesty: not justified by inference scale.** The ~150-rule trigger has not fired; the value is provenance integrity + single source of truth, not reasoning power. Phases 3–5 are gated. Stating this is itself a mitigation against over-claiming.

---

## 6. Open questions / what this does NOT solve

1. **Gate emission is a prerequisite, not done.** Until `verify_*_against_text` emit the content-addressed `legal:GateVerification` node (corpus sha256, anchor/discriminator id, codeVersion, outcome, timestamp), `prov:wasDerivedFrom` is a hand-written edge and the provenance guarantee is **aspirational** (must-fix #3). This is Phase-0 work and the hardest precondition.
2. **The verdict-into-graph move is not justified at current scale.** This blueprint does NOT solve "should ACC move `SpaceFinding.compliant` into SHACL now" — the answer at 2 rules / 3 fixtures is *no* (§0.4, §3.3, §5.4). §3 is the target form, scale-gated; the live verdict stays Python.
3. **Salva-Casa is operator-asserted, not verified (must-fix #7).** The three AND-conditions have no IFC-derivable evidence on any fixture; the graph adds structure + a gate-provenanced derogation value, not regime verification. Reproducing FZK `--salva-casa` = 1 violation declaratively is specified (§1.4, §5.4 DoD) but the regime's *applicability* remains an operator flag until an IFC Pset can ground a conjunct.
4. **Monostanza stays out of the graph** until `verify_monostanza_against_text` is runtime-wired (ADR-005 (ii)); when it is, the surfaces 28/38/20/28 inherit the same provenance contract — likely warranting a new ADR before any monostanza triple is written.
5. **LLM occupancy confidence is undefined.** `llama3.1:8b` emits no calibrated confidence; the source of `acc:occupancyConfidence` and the escalation threshold must be defined before the `"llm"` source is wired live (§4.4). Live occupancy stays the deterministic graph path (ADR-007).
6. **Scalability is unfalsifiable at this corpus (must-fix, critic).** No held-out large real IFC exists, so the Oxigraph trigger is unmeasurable and OWL transitivity is exercised only by one synthetic room. RDF-native scaling is a solution to a problem the corpus does not yet have; it is therefore deferred, not claimed as a present benefit.
7. **pyshacl is absent and no `sh:validate` has run (must-fix #1).** Every SHACL artifact here is parse-valid Turtle only; the *runnable* anti-circularity check adopted is the rdflib-only SPARQL audit (§4.3, executed). Adopting SHACL requires adding, pinning, and license-vetting pyshacl and running it in CI on instance graphs.
8. **Cross-lingual glossary as graph edges?** Whether the 47 declared-debt hints should enter the graph at all as `skos:altLabel` + `acc:declaredDebt` (a mild laundering-risk lexical edge) or stay entirely flat until a statute/authority anchors them is unresolved (§4.6).
