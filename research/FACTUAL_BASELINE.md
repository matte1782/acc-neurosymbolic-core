# Factual Baseline — Automated Compliance Checking (ACC) for IFC/openBIM

> **Project:** `acc-neurosymbolic-core` · **Phase:** 0 (deterministic research baseline; no architecture committed)
> **Date:** 2026-06-17 · **Method:** fan-out web + literature research → adversarial fact-check (15 of 28 quantitative/licensing claims confirmed, 13 refuted or misattributed and corrected inline) → synthesis.
> **Tone:** strictly empirical. Verified figures are marked `(verified)`; unsubstantiated ones are shown with their correction rather than asserted as fact.

---

## 1. Executive Summary & Market Urgency

Automated Compliance Checking (ACC) for IFC/openBIM models addresses a measurable, primary-sourced cost burden in the construction sector. Three figures, each verified against primary sources, frame the economic problem this framework targets:

- The U.S. capital-facilities industry incurs **USD 15.8 billion/year** in costs from inadequate interoperability (NIST GCR 04-867, 2004; 2002 base year — verified). Two-thirds (USD 10.6B) falls on owners/operators.
- Direct construction rework averages **~5% of total project cost (range 2–20%)** per the Construction Industry Institute (verified). In the UK, the Get It Right Initiative (GIRI, 2016) measured direct error cost at **~5% of project value (~£5bn/yr)**, rising to a best estimate of **~21% (~£21bn/yr; range 10–25%)** once unrecorded process waste, indirect costs, and latent defects are included (verified).
- The McKinsey Global Institute (2017) estimates a **USD 1.6 trillion/year** construction productivity gap, ranking inadequate design processes among the top root causes (verified).

Design and engineering errors — the slice an ACC system can directly attack — drive the majority of rework. Burati et al. (1992) found design deviations accounted for ~79% of total deviation cost and ~9.5% of total project cost; Love & Lopez (2012) found design-error rework at 6.85% direct + 7.36% indirect of contract value. Poor communication and inaccurate project information together account for **48% of rework** (PlanGrid/FMI 2018: 26% miscommunication + 22% poor project data — verified). These are precisely the failure modes that machine-readable information requirements and automated rule checking address.

The urgency is regulatory as well as economic. Singapore's CORENET X became mandatory for new projects with GFA ≥ 30,000 m² from 1 October 2025, and EU-funded efforts (ACCORD, Horizon Europe grant 101056973) are productizing digital-permit compliance microservices. No incumbent ships ready-made rulesets for the Italian Testo Unico Edilizia or the Eurocodes, which is the specific gap this framework targets.

### Academic & Methodological Anchors

The ACC literature provides a deterministic, well-documented methodological stack that this framework builds upon:

- **RASE methodology (Hjelseth & Nisbet, 2011):** decomposes each normative clause into Requirement / Applicability / Selection / Exception operators, producing a logical tree compilable into computable rules. It captures rule *structure* only and requires a separate execution engine plus a dictionary mapping regulation terms to IFC terms. Recent work (IEEE 2024) automates RASE tagging with LLMs + human-in-the-loop active learning.
- **Semantic NLP-to-rules (Zhang & El-Gohary, 2016/2017):** the canonical SNACC pipeline — ML text classification → syntactic-semantic information extraction over a domain ontology → transformation into logic clauses → deductive reasoning over BIM data. This is the "probabilistic text parsing feeding a deterministic reasoner" paradigm.
- **buildingSMART IDS and mvdXML:** IDS is the current computer-interpretable XML standard for deterministic information-requirement checking (Applicability + Requirement facets, echoing RASE's A and R); it handles existence/value/range checks but is not a general logic reasoner. mvdXML is the older MVD-based validation encoding, now largely superseded by IDS.
- **Semantic-web / linked-data checking:** ifcOWL and Linked Building Data (LBD) map IFC to RDF/OWL; SHACL, SPARQL/SPIN, and SWRL then perform deterministic constraint validation and Horn-rule inference. Notable systems include the French SBIM-Reasoner and recent NLP-to-SHACL fire-safety work.
- **Logic & constraint solving:** Answer Set Programming (clingo) formalizes prescriptive/performance codes; Clingo2DSR (2024) couples ASP to an external geometry database for mixed qualitative/quantitative spatial reasoning. SMT (Z3) provides decision procedures over arithmetic theories and ships a Datalog engine. These supply the sound, explainable deterministic verdict layer.
- **LLM + symbolic ("zero-hallucination") ACC (2022–2026):** LLMs perform extraction/classification while RAG grounding, knowledge-graph constraints, and a symbolic verification layer make the final deterministic verdict. Representative: Madireddy et al. (2025, arXiv:2506.20551). "Zero hallucination" is an engineering target, not a proven guarantee — treat efficacy claims as early-stage and not yet independently validated at scale.
- **EU ACCORD project:** contributes the AEC3PO ontology and the CODE-ACCORD corpus (862 annotated sentences, 4,297 entities, 4,329 relations from England + Finland regulations; Scientific Data 2025), feeding NLP-driven rule generation across UK/FI/EE/DE/ES demonstrators.

## 2. Proprietary Competitor Matrix

| Player | Vendor | Target Audience | Deployment/Pricing | Key Limitations |
|---|---|---|---|---|
| Solibri Office / Advanced / Premium / CheckPoint | Solibri Inc. (Nemetschek Group) | BIM managers, QA/QC, engineering firms, some AHJs; checks IFC + Revit | On-prem desktop + cloud CheckPoint (2025). Subscription: ~EUR 1,962/yr single seat (legacy Office, annual billing) up to ~EUR 3,150/yr/seat team; perpetual licenses discontinued Jan 1, 2025 | Recurring ~EUR 2k–3k/yr/seat; rule editing gated to higher tiers; proprietary closed ruleset format (.cset), no portability; no shipped Eurocode/Testo Unico rulesets — manual parameterization required; largely geometric/property checks |
| Model Checker for Revit + Configurator | Autodesk, Inc. | Revit users/BIM managers verifying model standards; not primarily an AHJ tool | On-prem Revit plugin; free with paid Revit subscription | Revit-only (not vendor-neutral IFC); Autodesk ecosystem lock-in; Autodesk-specific checkset format; oriented to data-quality not legal code; no localized regulation packs |
| UpCodes (incl. Copilot) | UpCodes, Inc. | Architects, engineers, contractors, code consultants doing code research | Cloud SaaS freemium; paid ~USD 25–50/mo/user (Copilot from ~USD 25/mo) | US-only codes (IBC/IRC/ICC); no Eurocode/Testo Unico; text/Q&A research, NOT geometric model checking; LLM can hallucinate citations; per-seat recurring cost |
| Verifi3D | Xinaps B.V. | Designers, BIM coordinators, engineering firms; native Revit + IFC | Cloud SaaS, ~EUR 400/mo/seat; ACC/BIM 360 integration | High per-seat cost for small firms; geometry/clash/egress/parameter focus; no shipped statutory packs; cloud/vendor lock-in; small single-vendor continuity risk |
| BIM.permit | VSK.software GmbH (Germany) | Designers, BIM managers, EU/DACH permit offices | Cloud/web + API; pricing not public | Rule formalization is a user/authority task (heavy upfront effort); opaque pricing; regionally focused; depends on availability of formalized rulesets (no default Testo Unico); IDS-bound, semantic/legal rules need custom encoding |
| ACCORD project outputs | ACCORD consortium (EU Horizon Europe 101056973) | Public authorities, software vendors, AEC; piloted EE/FI/DE/ES/UK | Cloud microservices/API; largely non-commercial, EU-funded | Framework/guidelines/reference microservices, not turnkey product; per-jurisdiction formalization still substantial; funding-period support limits; uneven coverage; no ready Eurocode/Testo Unico rulesets; productization status partly unverified |
| BricsCAD BIM | Bricsys NV (Hexagon AB) | Architects/designers using BricsCAD; engineers needing in-model checks | On-prem desktop; perpetual + subscription; compliance-feature pricing not public | Built-in convenience checking (accessibility/exits/ventilation), narrower than Solibri; vendor rule format; no localized statutory packs; ecosystem lock-in; not an AHJ tool |
| Allplan / Bimplus | ALLPLAN GmbH (Nemetschek Group) | Architects, structural/civil engineers, project teams | Allplan on-prem desktop; Bimplus cloud CDE; subscription, pricing not uniformly public | Primarily authoring + CDE, not a dedicated general code checker; code checking mainly structural-analysis context; no turnkey national permit rulesets; ecosystem lock-in (checking delegated to Solibri); pricing not fully transparent |
| cove.tool | cove.tool, Inc. (Atlanta) | Architects, performance/sustainability consultants | Cloud SaaS, from ~USD 500/mo | Energy-code/performance scope only (US/CA/UK/AU), not structural/fire/accessibility/permit; no Eurocode/Testo Unico; performance-model derived, not statutory review; recurring cost; lock-in |
| ClearEdge3D Verity | ClearEdge3D | Construction QA/QC teams, surveyors, contractors | On-prem desktop via Revit/Navisworks; pricing not public | NOT a code/regulatory checker — verifies as-built vs design geometry; requires Autodesk + reality-capture data; no regulation encoding; opaque pricing |
| Archistar AI PreCheck | Archistar (Australia) | Local governments/AHJs (primary), developers/architects/certifiers | Cloud SaaS; pricing not public (enterprise/government) | Jurisdiction-by-jurisdiction onboarding (~30+ cities AU/US/CA); zoning/planning emphasis; opaque pricing; AI/CV output needs human validation; no Eurocode/Testo Unico support |
| CodeComply (CodeComply.ai) | CodeComply.ai | AEC professionals + municipal plan reviewers/officials | Cloud SaaS; pricing not public | US-only codes (ICC/NFPA/ADA/FHA); no Eurocode/Testo Unico; AI flagging needs human verification; opaque pricing; early-stage, coverage depth unverified |
| CivCheck (Guided AI Plan Review) | CivCheck (founded 2023; acquired by Clariti, Oct 2025) | City plan reviewers/AHJs and permit applicants | Cloud SaaS; enterprise/government contracts (e.g. Denver USD 4.6M AI permit-review contract); list price not published | US-municipality focus; no Eurocode/Testo Unico; per-jurisdiction config; opaque, large-procurement model (not SMB-accessible); AI needs human oversight; post-acquisition roadmap risk |
| Snaptrude | Snaptrude Technologies Pvt. Ltd. | Architects/designers in early concept design | Cloud SaaS; pricing not public (~USD 35.8M total funding) | Code awareness is GENERATIVE, not a verifiable compliance report; AI output not authoritative; design tool, not statutory review; localized coverage unspecified; pricing not public |
| Public/municipal e-permitting (CORENET X, Norway/ByggSøk, Estonia POC) | Government bodies (Singapore BCA, Norway DiBK, Estonia MKM) + integrators | AHJs and permit-submitting industry in those jurisdictions | Cloud government platforms; not commercial COTS; free/fee submission. CORENET X mandatory for GFA ≥ 30,000 m² from 1 Oct 2025 | Jurisdiction-locked (no Eurocode/Testo Unico transferability); not sold to firms; heavy national rule-formalization maintained by authority; several remain pilots/POCs; platform-specific submission overhead |

## 3. Audited Open-Source Tech Stack (Self-Hostable Primitives)

### IFC/BIM Layer

| Tool | Role | License | Self-Hosting | Limitation |
|---|---|---|---|---|
| IfcOpenShell ([repo](https://github.com/IfcOpenShell/IfcOpenShell)) | De-facto FOSS IFC engine: parse/query/author/edit/validate IFC; IfcConvert CLI | LGPL-3.0-or-later (core); some CLI/utility components GPL-3.0-or-later [^1] | pip/conda, cross-platform; OCCT native dep ships in wheels; CPU/memory-bound on large models | LGPL source-availability obligations for modified library code; no horizontal scaling; pre-1.0 (0.8.x) breaking changes; no managed cloud |
| ifctester / IfcTester ([repo](https://github.com/IfcOpenShell/IfcOpenShell)) | IDS validator; authors/reads IDS, validates IFC; Console/HTML/ODS/BCF reports | LGPL-3.0-or-later (inherits IfcOpenShell) | Pure-Python, lightweight CLI/library/web | Bounded by IDS facet coverage (no arbitrary geometric/logic rules); reported BCF report bugs (issue #4680); tied to IfcOpenShell versioning |
| buildingSMART IDS ([repo](https://github.com/buildingSMART/IDS)) | Contract layer: computer-interpretable info-requirement standard | CC-BY-ND-4.0 (verified from repo) | Specification (XSD + docs), zero infrastructure | No-derivatives: cannot fork/redistribute a modified IDS variant; constrained to declarable facets; young standard (v1.0 Final 2024-06-03), maturing interop |
| Bonsai (formerly BlenderBIM) ([repo](https://github.com/IfcOpenShell/IfcOpenShell)) | Native IFC authoring/review front-end | GPL-3.0-or-later [^2] | Blender add-on, commodity desktop; not headless | GPL copyleft (more restrictive than core LGPL); pre-1.0 alpha; Blender dependency; heavy on large federated models |
| web-ifc (ThatOpen) ([repo](https://github.com/ThatOpen/engine_web-ifc)) | Browser/Node IFC parser-writer (C++→WASM) | MPL-2.0 | JS/WASM, in-browser or Node, commodity hardware | Geometry coverage trails OCCT on edge cases; browser memory limits; MPL file-level copyleft |
| ThatOpen Components ([repo](https://github.com/ThatOpen/engine_components)) | Viewer/UI layer on Three.js (rendering, measurements, fragments) | MIT | Front-end JS/TS, browser+Node, no backend | Visualization toolkit, not an authoritative data engine; large models need Fragments tiling; Three.js migration churn |
| xBIM Toolkit (XbimEssentials) ([repo](https://github.com/xBimTeam/XbimEssentials)) | IFC data layer for .NET backends | CDDL-1.0 (verified from repo) | .NET 6/8 cross-platform; geometry engine more Windows-centric | CDDL weak-copyleft, GPL-incompatible; cross-platform geometry weaker; lower cadence; IFC4.3 lags; split across repos |
| FreeCAD BIM Workbench ([repo](https://github.com/FreeCAD/FreeCAD)) | Open parametric BIM authoring + IFC round-trip | LGPL-2.1 (core; verified from repo) | Desktop, commodity hardware; reuses IfcOpenShell/OCCT | IFC4.3 round-trip can lose data; interactive desktop, not headless server; not for federated coordination; maturing UX |
| buildingSMART IFC schema (ISO 16739-1) ([repo](https://github.com/buildingSMART/IFC4.3.x-development)) | The ISO-standardized data model at the bottom of the stack | CC-BY-ND-4.0 (verified from repo) | Specification/schema, zero runtime | No-derivatives (implement, don't fork); large/complex schema, uneven IFC4.3 tool coverage; slow standards lifecycle; verbose STEP encoding |

### Knowledge/Graph & Reasoners

| Tool | Role | License | Self-Hosting | Limitation |
|---|---|---|---|---|
| Neo4j Community ([repo](https://github.com/neo4j/neo4j)) | Labeled-property-graph DB (Cypher) for the KG | GPL-3.0-only (Community); Enterprise commercial | JVM single server; Community lacks clustering/RBAC/hot backup | GPL copyleft on distributed products; property graph, not RDF/OWL (needs n10s); single-instance only |
| Apache Jena + Fuseki ([repo](https://github.com/apache/jena)) | RDF triple store + SPARQL 1.1 endpoint + reasoner hooks | Apache-2.0 | JVM; Fuseki jar/Docker; no tier limits | JVM-centric (Python via HTTP); built-in reasoner limited (RDFS/forward-chaining), full OWL DL needs external reasoner; TDB2 tuning at scale |
| RDFLib ([repo](https://github.com/RDFLib/rdflib)) | In-process Python RDF graph library | BSD-3-Clause | Pure-Python, pip, no server | In-memory store doesn't scale; SPARQL slower than native stores; no built-in OWL reasoning |
| Oxigraph ([repo](https://github.com/oxigraph/oxigraph)) | Lightweight fast RDF DB, SPARQL 1.1; RDFLib persistent backend | Apache-2.0 OR MIT (dual) | Single Rust binary/CLI/embeddable/Python/WASM; RocksDB | Smaller ecosystem than Jena; no built-in OWL/RDFS reasoner; pre-1.0 (0.5.x) API/storage churn |
| Ontotext GraphDB Free ([site](https://graphdb.ontotext.com/)) | RDF triple store with SPARQL + OWL2-RL/QL reasoning | Proprietary freeware — NOT open source; production use prohibited | JVM self-host but from v11 requires manual free license key; 1 core / 2 concurrent queries | Closed-source; free license forbids production/SaaS/resale; capped at 1 core; vendor lock-in |
| Memgraph ([repo](https://github.com/memgraph/memgraph)) | In-memory property-graph DB (Cypher, Bolt) | BSL 1.1 — source-available, NOT OSI open source | Docker/binary; RAM-bound | BSL restricts competing managed service until change date; in-memory RAM bottleneck; no native SPARQL/DL |
| HermiT ([repo](https://github.com/owlcs/hermit-reasoner)) | Sound/complete OWL 2 DL reasoner | LGPL-3.0-or-later (some sources note dual LGPL/GPL) | JVM library via OWL API | Effectively unmaintained (stuck at 1.3.8); OWL 2 DL expensive; LGPL linking obligations |
| Openllet ([repo](https://github.com/Galigator/openllet)) | OWL 2 DL reasoner (Pellet fork); SWRL + SPARQL-DL | AGPL-3.0 (also commercial) | Java library, Java 11+ | AGPL network copyleft — SaaS source-disclosure trigger; stale (last release 2019); poor ABox scaling |
| ELK ([repo](https://github.com/liveontologies/elk-reasoner)) | Fast parallelized OWL 2 EL reasoner | Apache-2.0 | JVM library/CLI/Protégé plugin | EL profile only (no disjunction/negation/universals); limited beyond classification; infrequent releases |
| pySHACL ([repo](https://github.com/RDFLib/pySHACL)) | SHACL validation engine over RDF | Apache-2.0 | Pure-Python on RDFLib, pip | RDFLib in-memory perf bound; validation only (not full OWL inference); partial advanced-SHACL coverage |

### Symbolic Solvers

| Tool | Role | License | Self-Hosting | Limitation |
|---|---|---|---|---|
| Z3 ([repo](https://github.com/Z3Prover/z3)) | SMT/theorem solver; constraint/satisfiability/model finding | MIT | Single binary + bindings, pip (z3-solver), in-process | Undecidable fragments time out / "unknown"; not a KB (needs encoding layer); encoding-sensitive scaling |
| clingo / Potassco ([repo](https://github.com/potassco/clingo)) | ASP grounder + solver for non-monotonic/rule-based KR | MIT | conda/pip, in-process | Steep modeling curve; grounding bottleneck on large domains; finite-domain, not general theory solver |

### Neuro-Symbolic Frameworks

| Tool | Role | License | Self-Hosting | Limitation |
|---|---|---|---|---|
| SymbolicAI ([repo](https://github.com/ExtensityAI/symbolicai)) | Neuro-symbolic glue: Symbol primitives + design-by-contract over LLMs | BSD-3-Clause | pip; self-hostable with local LLM backend | Reliability bound by LLM; "semantic" ops inherit nondeterminism/hallucination; not a formal reasoner; fast-evolving API |
| DeepProbLog ([repo](https://github.com/ML-KULeuven/deepproblog)) | Deep learning + probabilistic logic programming (neural predicates in ProbLog) | Apache-2.0 | Python, GPU optional; needs ProbLog/Prolog | Research-grade; probabilistic inference scales poorly with grounding; steep learning curve |
| Scallop ([repo](https://github.com/scallop-lang/scallop)) | Differentiable Datalog via provenance semirings | MIT | Rust core + pip (scallopy), GPU optional | Research project, evolving API; Datalog expressivity limits; provenance cost on large fact sets |
| IBM LNN ([repo](https://github.com/IBM/LNN)) | Logical Neural Networks: differentiable weighted real-valued logic | Apache-2.0 | Python/PyTorch, GPU optional | No formal releases; requires weighted-logic expertise; maturity/scalability behind production frameworks |

### Local LLM Runtime

| Tool | Role | License | Self-Hosting | Limitation |
|---|---|---|---|---|
| Ollama ([repo](https://github.com/ollama/ollama)) | Local LLM serving with registry + OpenAI-compatible API | MIT (engine) | Single binary, CPU works/GPU recommended; runs on laptop for small models | Per-model licenses vary; lower throughput than vLLM (single-user oriented); large models need RAM/VRAM |
| llama.cpp ([repo](https://github.com/ggml-org/llama.cpp)) | High-efficiency GGUF/quantized inference engine; llama-server | MIT (engine) | CPU-only and consumer GPU (CUDA/Metal/Vulkan/ROCm); edge-capable | Model weights separately licensed; lower-level/less turnkey; single-node focus |
| vLLM ([repo](https://github.com/vllm-project/vllm)) | High-throughput production serving (PagedAttention, continuous batching) | Apache-2.0 (engine) | Effectively requires server/datacenter GPU; significant VRAM | Model weights separately licensed; heavy hardware (not commodity/CPU); more operational complexity |
| Base-model weights (Llama 3 vs Mistral) ([Llama](https://www.llama.com/llama3/license/) / [Mistral](https://mistral.ai/)) | The neural knowledge/generation component | Llama 3: Meta Community License (open-weight, NOT OSI). Mistral 7B / Mixtral: Apache-2.0 | Weights downloadable/self-hostable on the runtimes above | Llama 3 license: free commercial use only below 700M MAU, bans training competitors, AUP/attribution — NOT open source. Some newer Mistral models ship under non-commercial Research License — verify per checkpoint |

[^1]: License correction — SPDX `LGPL-3.0` is deprecated in favor of `LGPL-3.0-or-later`; IfcOpenShell's core is LGPL-3.0-or-later (bundled CLI/utility components carry GPL-3.0-or-later).
[^2]: License correction — although Bonsai lives in the IfcOpenShell repository (whose core library is LGPL-3.0-or-later), Bonsai itself links Blender's Python API and is distributed under GPL-3.0-or-later, not LGPL.

## 4. Quantitative ROI & Economic Proof Points

### ROI Formula

```
ROI% = [ (HoursSaved × LoadedRate) + ReworkAvoided + ScheduleAccelerationValue − AnnualSubscriptionCost ] / AnnualSubscriptionCost × 100

Per-seat annualized form:
  AnnualGrossBenefit = Projects_per_seat_per_year × [ (H × R) + W + S ]
  AnnualNet          = AnnualGrossBenefit − C
  ROI%               = AnnualNet / C × 100
  Payback_months     = C / (AnnualGrossBenefit / 12)
```

### Worked Example (explicit variables)

| Variable | Value | Status |
|---|---|---|
| H = code-review hours saved/project = 24 hr × 0.70 reduction | 16.8 hr | ASSUMPTION (manual hrs built from CivCheck per-pass times; reduction% assumed) |
| R = loaded structural-engineer rate | $175/hr | SOURCED (intermediate band $150–210; market $100–220) — note: $175 is the top of the *entry* band; true intermediate midpoint is $180/hr |
| W = rework avoided = $2,000,000 × 1.5% × 10% | $3,000 | rework % SOURCED; project size + ACC-prevented share ASSUMPTION |
| S = schedule-acceleration value/project | $2,500 | UNVERIFIED — see proof points |
| C = annual subscription cost/seat ($68/mo) | $816/yr | SOURCED (UpCodes Professional list price) |
| Projects_per_seat_per_year | 12 | ASSUMPTION |

**Computation:** per-project gross benefit = (16.8 × $175) + $3,000 + $2,500 = $2,940 + $3,000 + $2,500 = **$8,440**. Annualized: 12 × $8,440 = $101,280 gross; net = $101,280 − $816 = $100,464. **ROI% ≈ 12,300%**; payback ≈ 816 / (101,280/12) ≈ 0.097 months (~3 days, effectively the first project).

This headline ROI is arithmetically correct but assumption-dominated and should not be the lead figure. The defensible **conservative floor**: a single project's labor saving (16.8 × $175 = **$2,940**) exceeds the full annual seat cost ($816) by ~3.6×, so payback is the first project regardless of rework/schedule assumptions. Rework and schedule value are upside, not base case.

### Proof-Point Metrics (with verification status)

- Direct construction rework ~5% of total project cost, range 2–20% — CII **(verified)**.
- CII rework by project type 2.4% (standard industrial) → 12.4% (civil/heavy) — **(unverified — refuted: the 2.4%/12.4% per-type split is not supported by any primary source. CII RS10-1 (1989) reports a single ~12.4% / "exceeds 12 percent" overall average for industrial projects with no project-type segmentation; the 2.4% figure appears fabricated.)**
- GIRI UK direct error cost ~5% of project value (~£5bn/yr), 17 organisations — **(verified)**.
- GIRI total error including indirect ~21% (~£21bn/yr), range 10–25% (breakdown 5% direct + 6% process waste + 7% indirect + 3% latent) — **(verified)**.
- NIST inadequate-interoperability cost USD 15.8 billion/yr (U.S. capital facilities, 2002 base year) — **(verified)** (inflate ~1.6–1.7× for a 2026 TAM).
- McKinsey construction productivity gap USD 1.6 trillion/yr — **(verified)**.
- Permit timelines: commercial 3–6 months (upper-typical, not median), 9–12+ months large/complex, 8–10 years major U.S. infrastructure — **(verified)** (correct citation is the U.S. House Oversight hearing of Sept 6, 2018, not 2023–2026).
- Permit delay monthly carrying cost ~1–3% of total project cost/month — **(unverified — refuted: not supported by cited sources and internally implausible (annualizes to ~12–36%). Carrying cost is better expressed as absolute dollars or ~0.5–1.5% of project value/month, dominated by financing + taxes + insurance.)**
- Hawaii DBEDT state-project permit delay: avg 439 days (2022), 489 days (2023); >$30M total over 2022–2023 — **(verified)** (scoped to state-government projects).
- Share of rework from design/engineering errors ~70%; design-error rework ~6–10% of project cost — **(unverified — misattributed: the cited Trimble blog supports neither figure. Corrected: design errors ≈ 70–79% of rework cost (Burati et al. 1992: 79%; 9.5% of project cost) and design-error rework ≈ 6–10% of project cost (Love & Lopez 2012: 6.85% direct + 7.36% indirect).)**
- Rework drivers: 26% miscommunication + 22% poor project data (= 48%) — PlanGrid/FMI 2018 **(verified)** (the separate 14% bad-data figure is from Autodesk/FMI 2021, not the 2018 report; use 22% for the 2018 baseline).
- U.S. annual rework spend ~5% × ~$1.3T ≈ $65bn+/yr — **(unverified — refuted: the 5% rate is CII, not Autodesk/FMI; the $65B extrapolation appears in no cited source and uses an inconsistent $1.3T base (U.S. spend was ~$1.8T+ by 2022). The defensible, correctly-attributed figure is PlanGrid/FMI 2018: >$31 billion/yr U.S. rework from poor communication + poor data.)**
- Structural engineer billing rate $100–$220/hr (principals to $350) — HomeGuide/Monograph **(verified)**.
- Structural engineer loaded rate by experience: entry $110–175, intermediate $150–210, senior $190–280, principal $250–350 — Monograph **(verified)** (source last updated 2026, not 2025; intermediate midpoint is $180/hr).
- AEC firm billing-rate inflation: 95% raised rates, median +11% (2022–2025) — **(unverified — misattributed: figures originate from Zweig Group's 2025 Fee + Billing Report, not Monograph/HomeGuide; HomeGuide does not contain them. The "3–5%/yr ongoing" element is Monograph editorial guidance, not survey data.)**
- Structural engineering fee 1–5% of construction cost (renovations to 7%); structural portion ~0.68–1.68% — Monograph **(verified)**.
- Peer/code-review service fee 0.25–0.50% of construction cost (= $5,000–$10,000 on $2M) — Monograph **(verified)** (single-publisher rule-of-thumb; source dated 2026).
- Typical code-review labor cost ~$2,940–$10,000/project — **(unverified — refuted: both anchors are unsupported and the 0.25–0.50% peer-review figure is contradicted by literature placing peer review/inspection nearer ~15% of project cost (~$300k on $2M); the 16.8-hr-saved figure has no located source; mixing a one-off hours-saved delta with a percent-of-cost basis is methodologically incoherent.)**
- Manual plan-review time 1–1.5 hr/pass; green reviewers did 4–5 reviews in 20–30 min with AI — CivCheck testimonial **(verified)** (implied per-review reduction ~88–93%, i.e. at/above the high end of "70–90%").
- Permit approval time 30–60 days → 3–5 days with AI plan review — **(unverified — refuted: the cited UF Warrington article contains no such figure; it reports a per-review-STEP reduction (~3 weeks → ~30 min, Altamonte Springs/AutoReview.AI), not end-to-end approval days. The 30–60→3–5 day figure traces only to AI search summaries and uncrawlable vendor pages.)**
- Cost savings per project from faster approvals $2,500–$5,000 (base S = $2,500) — **(unverified — refuted: no locatable source links "UF Warrington, via Nomic, 2025" to this range; attribution appears fabricated. Do not treat $2,500 as a sourced base case.)**
- Permit-delay carrying cost ~$1,100/week per single-family project — **(verified)** (originates with BIAW Washington research; Legacy Group/SICBA are corroborating reporters).
- Permit-delay carrying cost ~$31,375 avg per project (WA, 6+ month avg) — **(unverified — misattributed: the dollar figure is accurate but originates from BIAW's "Cost of Permitting Delays" report dated November 2022 (2018 survey inputs), not Legacy Group and not 2025.)**
- Carrying cost for larger projects $50,000–$200,000/month — **(unverified — misattributed: the dollar range is verbatim-accurate but is sourced from mod-eng.com / Michael Groselle (2026), not the cited Permit Division blog, which contains no such figure; it is single-vendor, Texas-specific. The accompanying "1–3% of project cost/month" benchmark is unsupported.)**
- Construction rework total 5–9% of contract value (range 3–12%) — **(unverified — misattributed: the numbers are sound but originate from CII/Navigant (~5% reported vs ~9% actual), not CMAA; CMAA only hosts a 2004 re-citing handout. Re-attribute to CII/Navigant, compiled by PlanRadar 2025.)**
- Design-error rework 1–2% of project cost (down from ~9% pre-digitization) — **(unverified — refuted: the 9% and 1–2% come from different studies with different denominators/sectors (Burati 1992: 9.5% of total project cost, industrial; Hwang 2009: ~1.5% of construction-phase cost, buildings); no primary study attributes any decline to digitization. State as ~1.5–9.5% depending on sector/methodology and drop the causal framing.)**
- Rework from bad info/communication 48% (26% + 22%) — PlanGrid/FMI 2018 **(verified)**.
- BIM software market ~$9.1–12.8B (2025), ~$10.3B (2026), $24.6–51.4B by 2034–2035 — **(unverified — cross-firm variance; medium confidence, not adversarially verified against primary filings).**
- AEC software market ~$9.2–12.8B (2025) — **(unverified — medium confidence, wide cross-source variance).**
- RegTech market ~$14.69B (2025) → $115.5B by 2035 — **(unverified — medium confidence; cross-industry, not AEC-specific).**
- Dedicated ACC/construction-compliance market size — **(unverified — no reliable standalone public figure exists; must be triangulated as a fraction of BIM/AEC/RegTech TAM).**
- ACC SaaS list price $45/mo (Essentials) – $68/mo (Professional) per seat — UpCodes **(verified)**.
- CodeComply.ai raised $2M — Refresh Miami **(verified — investor-appetite signal).**

## 5. Factual Data Bottlenecks

Where deterministic, freely available data is hard or impossible to obtain:

- **Opaque competitor pricing.** Roughly half the proprietary players (BIM.permit, Archistar AI PreCheck, CodeComply.ai, CivCheck list pricing, ClearEdge3D Verity, BricsCAD BIM compliance feature, Allplan/Bimplus) publish no list price, operating book-a-demo or enterprise/government procurement models. Where figures exist (Solibri, Verifi3D, UpCodes, cove.tool), they vary by source, plan, region, and billing cadence and shift over time.
- **Machine-readable Italian/EU regulation availability.** No incumbent ships ready rulesets for the Testo Unico Edilizia (DPR 380/2001), Italian DM norms, or the Eurocodes. These remain primarily as legal prose (PDF/HTML) rather than computer-interpretable formats (IDS/SHACL/logic), so formalization is a substantial, largely manual upfront task per jurisdiction — confirmed across Solibri, Autodesk, Verifi3D, BIM.permit, ACCORD, and the public e-permitting platforms.
- **Proprietary, non-portable rule formats.** Incumbents encode rules in closed vendor formats (Solibri .cset/parametric templates, Autodesk checksets, in-application BricsCAD rules) that are not exchangeable across tools, frustrating independent audit and creating lock-in. The open alternatives (IDS, mvdXML, SHACL) are deliberately scope-limited (declarable facets / data-requirement conformance), not general normative reasoners.
- **Scarcity of public rework-cost primary data.** The strongest anchors (CII, GIRI, NIST, McKinsey, Burati 1992, Love & Lopez 2012, PlanGrid/FMI 2018) are real but aging (much CII/NIST material is 2001–2005 / 2002-base-year), context-sensitive (GIRI itself warns the "average is almost meaningless" for a specific project), and frequently laundered through vendor blogs and AI search summaries with broken or fabricated attribution. Several widely circulated figures (the 2.4%/12.4% per-type split, the 1–3%/month carrying cost, the 30–60→3–5 day permit reduction, the "UF Warrington via Nomic" $2,500–$5,000 savings, the Autodesk/FMI $65B extrapolation) could not be substantiated and were refuted during verification.
- **IFC model test-set availability.** No standard, openly licensed, regulation-annotated IFC benchmark corpus exists for Italian/EU code checking. The closest public resource is the ACCORD CODE-ACCORD corpus (862 annotated sentences from England + Finland regulations) — valuable for NLP rule generation but English/Finnish-language, not Italian, and text-only rather than paired IFC geometry.
- **No clean ACC market sizing.** There is no traceable standalone "AEC RegTech" or "construction-compliance software" market figure; it must be derived as a fraction of the BIM (~$9–13B 2025) / AEC software (~$9–13B 2025) / RegTech (~$15B 2025) TAMs, all of which themselves show wide cross-firm variance and are flagged medium-to-low confidence.

---

*Provenance: generated 2026-06-17 from web and literature research with adversarial verification; verified figures are marked, and refuted or misattributed claims are corrected or flagged inline rather than presented as fact.*
