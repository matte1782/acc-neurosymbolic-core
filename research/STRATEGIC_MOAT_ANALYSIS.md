# ACC Strategic Moat Analysis

**Date:** 2026-07-02
**Status:** pre-seed technical asset; development freeze in effect (exam session)
**Grounded in:** repo state @ `5df4db5`, branch `audit/p0-m4-stabilization` (17 commits, PR #1 open), 189 tests green across 9 suites

**Evidence taxonomy (used inline throughout — the qualifier travels with the claim):**
- **[MEASURED]** — a number produced by running code this session or a pinned benchmark (file:line / ADR cited)
- **[VERIFIED-IN-REPO]** — code, test, or document that exists and was inspected at `5df4db5`
- **[BUILD]** / **[ASPIRATIONAL]** — designed but unimplemented; a plan, not an asset
- **[HYPOTHESIS]** — market/legal/competitive reasoning with no validation point yet
- **[PROJECTION]** — extrapolation beyond the measured range, with break conditions stated

**Stage statement (read this before anything else).** This is a pre-seed technical asset, not a company with a moat. Verified state: **2 statutory rules, 3 public IFC fixtures, 189 tests with no CI to guard them, 1 founder (development freeze imminent for an exam session), 0 customers, 0 LOIs, 0 pilots, and no LICENSE file** (legally: all rights reserved — the "open core" does not exist yet). What is proven is a verification architecture and an adversarial verification process at prototype scale. Everything commercial in this document is a plan and is labeled as such.

---

## 0. Executive summary

ACC is a neuro-symbolic compliance checker for Italian building habitability (DM 5/7/1975 + DPR 380/2001 Salva Casa) whose distinguishing property is that **no LLM output, extracted quantity, or rule file is ever trusted**: every threshold is deterministically re-derived from statute prose or rejected, extraction fails closed, and missing evidence yields UNDETERMINED, never a silent pass [VERIFIED-IN-REPO]. The stack is 100% local (Ollama, ifcopenshell, rdflib, pyshacl; zero cloud calls) and fast at fixture scale (~1 ms/space SHACL, warm) [MEASURED, ADR-009]. The process that built it — preregistration, external adversarial IFC corpus (GATE-S 9/9), mutation/metamorphic suites, three consecutive same-actor separate-session adversarial rounds each catching a real shipped defect — is the strongest asset, and is honestly a **time-boxed head start** (est. 6–12 engineer-months for a funded team to replicate), not a durable moat [HYPOTHESIS]. Durable defensibility would come from assets that are all currently unbuilt: provenance-bearing gate runs, an adversarial corpus factory, municipal rule packs, customer audit-trail history [ASPIRATIONAL]. Coverage today is 2 rules / 3 fixtures; the ~150-rule scale trigger has not fired; applicability semantics are mostly unverified (4/51 occupancy tokens statute-anchored). Named competitors (ACCA, Solibri/Nemetschek, Maggioli, EU ACCORD, foundation-model agents) all own something this project lacks — channel, installed base, or funding — and §4 states this unsoftened. The recommendation: fix licensing and CI immediately, run a short Track A hygiene pass, then put the main R&D weight on Track B's gate generalization, whose span-quote protocol is the stated make-or-break.

---

## 1. The Core Technical Moat

The moat claim is not the idea ("check building codes with an LLM") and not the stack (every component is open source). It is a **verification architecture in which no LLM output, no extracted quantity, and no rule file is ever trusted** — plus the adversarial process that built it. This section states the mechanism precisely, grounded in code at `5df4db5` (189 tests green across 9 suites; frozen controls byte-identical: FZK 5 violations / 1 salva-casa, Institute 2/2, Duplex 0 violations / 21 undetermined) [VERIFIED-IN-REPO]. Scope disclosure, stated here and not only in an appendix: everything below is demonstrated at **2 rules on 3 fixtures**; the moat claim is about architecture and process at prototype scale, not coverage breadth.

### 1.1 Containing the hallucination cliff (mechanism, not marketing)

Pure-LLM compliance tools fail on a cliff: the model emits a *plausible* threshold ("minimum height 2.55 m" — a real number in the statute, but the mountain-municipality carve-out, not the habitable baseline), the comparison happens inside text generation, and the output is a fluent verdict with no audit trail and no way to distinguish a correct pass from a confabulated one. ACC's statute corpus contains such traps by design (the "comuni montani 2,55" line, seismic-zone heights, daylight percentages), and the architecture makes that failure class structurally unreachable in four layers. Note on the contrast: it is argued **by construction** (the statute's own decoy values plus the gate defects found in-house), not from a measured benchmark of competitor tools [HYPOTHESIS on the competitor side].

**Layer 1 — the LLM does structural translation only, never arithmetic and never verdicts** [VERIFIED-IN-REPO]. The local model (Ollama `llama3.1:8b`, temperature 0 / seed 0 / top_k 1, JSON-schema-constrained) decomposes statute prose into a RASE structure (Requirement / Applicability / Selection / Exception) with verbatim source spans (`sandbox/parser.py:71-126`, `SYSTEM_PROMPT`). Its output is explicitly labeled UNTRUSTED in the module contract (`parser.py:6-12`).

**Layer 2 — VERIFY-NEVER-TRUST: every number is re-derived deterministically from the statute before it can exist downstream** [VERIFIED-IN-REPO]. `verify_rule_against_text` (`parser.py:346-400`) re-extracts each threshold from the statute text using metric-anchored regexes pinned to each threshold's lead-in phrase (`_SOURCE_ANCHORS`, `parser.py:282-287`), with three defenses that each closed a real attack:

- **Answer-key exclusion** (`crosscheck_corpus`, `parser.py:262-270`): everything from the "Target rule" heading onward is stripped, so the gate can never be satisfied by the model echoing the decomposition under verification (anti-circularity).
- **Unique-value-or-reject** (`source_value`, `parser.py:315-336`): the anchor must resolve to exactly one distinct value; an injected look-alike span makes the source ambiguous and the gate **raises** rather than letting the first match win. This closed a real anchor-shadowing false-pass found by a 180-case adversarial audit (ADR-002).
- **Discriminator binding** (`parser.py:294-305, 372-393`): a clause binds a threshold only if its value equals the re-derived source value (tolerance 1e-9 after Italian-comma/fraction normalization), carries operator `>=` and the correct unit, and cites a verbatim span containing that metric's discriminator tokens — the two equal-valued 2.40 m thresholds (accessory vs Salva Casa) have **disjoint** discriminator sets, so a value-identical swap is caught.

Any missing, partial, swapped, decoy, or ambiguous value raises `ValidationGateError`; no default is ever backfilled on the LLM path (`parse_rule`, `parser.py:737-755` — the silent regex fallback was deliberately removed, ADR-002).

**Layer 3 — the extraction side is fail-closed on garbage** [VERIFIED-IN-REPO]. `_qty` (`checker.py:295-314`) rejects any non-finite or non-positive quantity (a negative-dimension window fabricating positive area is exactly the CRITICAL C-1 the audit found and closed); `length_scale_to_m` (`checker.py:752+`) raises `NotCertifiableError` on an unresolvable LENGTHUNIT instead of silently reading millimetres as metres (the 1000× false-pass class, C-2/C2-F); a zero-`IfcSpace` model exits not-certifiable rather than vacuously passing (H-1); and the aero numerator is always the conservative `min(attr, Qto)` lower bound (`checker.py:530-538`, ADR-007c).

**Layer 4 — the ternary keystone: no *known* path by which absent evidence reads as compliance** — an engineering claim verified at 2 rules / 3 fixtures / 9 adversarial files, **not** an absolute, and it coexists with two declared residuals: (R1) a *present-but-wrong* unit label (mm declared METRE) is caught by no current guard, and (R2) a single-source inflated-but-plausible window cannot be cross-checked by `min(attr, Qto)`. Within that boundary [VERIFIED-IN-REPO]: `SpaceFinding.compliant` (`checker.py:266-278`) returns `None` if *any applicable* check is unevaluated — never `all()` over what happens to be present. The per-space A-Box materializer **omits** unmeasurable values (`materialize_space_abox`, `checker.py:481-507`), and the shapes' `sh:minCount` converts that absence into UNDETERMINED via the MinCount-dominant ternary mapping (`orchestrator.py:149-181`). The loader is fail-closed against tampering: `load_shacl_shapes` (`orchestrator.py:65-97`) raises on shapes missing `sh:targetClass` for any regime class (vacuous conformance = silent pass), missing `sh:minInclusive`, or missing `sh:minCount >= 1` — the last guard added after an adversarial bypass hunt proved a minCount-stripped TTL loaded silently and read a missing height as PASS (ADR-008a). Visible consequence on real data: the Revit Duplex fixture, which carries no net-height quantity, reports **0 violations / 21 undetermined and exits non-zero** — an honest refusal where a naive tool would print "0 violations."

One determinism caveat, stated inline because it belongs in the same sentence as the claim: **the runtime verdict path is fully deterministic and the LLM is not on it — but the occupancy/applicability classifier (`graph.py`, tokenized head-stem matching) IS on the verdict path via `sh:targetClass` applicability, and it is verdict-equivalent only by construction on the 3 fixtures (4/51 tokens statute-anchored, 47 declared debt).** Determinism is reproducibility, not correctness; the applicability half of the verdict has not had the adversarial hardening the threshold half has.

Every verdict decomposes into (i) a threshold provably bound to a verbatim statute span, (ii) a measurement that passed positivity/unit/trust guards or was honestly omitted, and (iii) a SHACL `ValidationReport` parsed by one deterministic SPARQL query (`orchestrator.py:127-146`), with `sh:resultMessage` regenerated from the live threshold value so even a message can never carry a stale number (ADR-008) [VERIFIED-IN-REPO].

### 1.2 Local-first / data sovereignty

The entire stack runs on-premise with **zero cloud calls** [VERIFIED-IN-REPO]: Ollama on localhost for the neuro lane (not on the default verdict path), ifcopenshell 0.8.5 for extraction, rdflib 7.6.0 for the occupancy graph and A-Box, pyshacl 0.31.0 for validation. The pipeline is 100% offline and reproducible (temperature 0 + fixed seed; ADR-002's ≥3×-identical criterion), and locality costs nothing at fixture scale — on FZK (7 spaces, warm): 0.386 s IFC extraction, 0.011 s A-Box construction, 0.008 s SHACL validation, ~1 ms per space [MEASURED, ADR-009].

*Market reasoning, labeled as such* [HYPOTHESIS]: BIM models are commercially sensitive artifacts — a full IFC encodes layouts, security infrastructure, and client identity — and large owners and public administrations are structurally reluctant to upload them to third-party clouds. An air-gappable checker sidesteps the data-processing-agreement and cross-border questions, a posture aligned with EU procurement expectations. **Honest durability caveat:** "local LLM, zero cloud" is a *deployment feature*, not durable differentiation — as on-prem/VPC frontier-model deployment normalizes, this USP erodes (see §4, threat T6). What this repo has NOT done for that market: there is **no LICENSE file**, and the ifcopenshell LGPL-3.0 linking obligation is open — both must be resolved before any commercial claim (§2.3).

### 1.3 The process moat (adversarial verification pipeline)

The third asset is not a file; it is the demonstrated pipeline that produced the files. All components in-repo [VERIFIED-IN-REPO]:

- **Preregistration before judging.** Frozen prereg documents (`research/PREREG_C1_window_geometry.md`, `PREREG_C2_unit_scale.md`, `PREREG_C1b_aero_window_trust.md`) committed *before* evaluation, with the shipped fix entered as one candidate among several (`research/DECISION_MATRIX.md`) — explicit confirmation-bias resistance, because the project's own frozen-control oracle is circular for defects the fixtures cannot trigger.
- **An external adversarial oracle corpus** (`research/corpus/`): 9 surgically mutated IFC fixtures with spec-pinned expected verdicts, independent of the code under test. Current status: GATE-S 9/9 (every planted defect refused) and GATE-N (frozen controls byte-identical, conforming units still process).
- **Mutation and metamorphic suites that demonstrate test power against the current mutant set (n=11 mutation cases, 7 metamorphic relations)** — e.g., reverting to the attr-preferring aero numerator false-passes and is killed. This demonstrates power against *those specific mutants*, not test power in general; "prove" would be exactly the overclaim this repo bans.
- **Three consecutive adversarial verification rounds, each catching a real defect in freshly-shipped code.** "Independent" defined precisely, because a technical investor will ask: these were **same-actor (founder + LLM-assistant pipeline), separate-session, fresh-context** rounds — *not* external red teams. Within that definition: (1) ADR-007a — the C-2 unit fix was DISQUALIFIED because its presence-only check passed an `IfcContextDependentUnit` that still yielded the silent 1000× misread; (2) ADR-007c — an inflated-window bypass (bounding-box area inflated to just under the floor area) defeated the trust test and fabricated an aero pass (FZK 5→4, reproduced before fixing); (3) ADR-008a — the `sh:minCount` loader gap plus an exact-at-bar `xsd:double`-vs-`xsd:decimal` regression flipping a room at exactly 2.40 m to VIOLATION. Every one reproduced first, fixed fail-closed, pinned as a regression test, auditable in the append-only ADR log (`docs/decisions.md`).
- **Committed gate [ASPIRATIONAL, stated as an obligation]:** one genuinely *external*, third-party adversarial round plus a held-out third-party IFC corpus before any externally-relied-upon verdict claim. Neither exists today.

The self-honesty is hard to fake: the 49-agent code audit (`research/CODE_AUDIT_REPORT.md`) that found the CRITICALs is committed to the repo, refuted candidates and all.

### 1.4 What is easy vs hard to copy (honest table)

The honest frame is not "hard to copy" — it is a **time-boxed head start**. The anchor engineering exists for n=2 rules; the frozen oracle is 3 *public* fixtures; and the verification methodology, once published (and open-coring publishes it), is replicable by a competent 2–3 person funded team in an estimated **6–12 engineer-months** [HYPOTHESIS — order-of-magnitude estimate, stated so it can be challenged]. The durable-moat story rests on assets that are all currently **[ASPIRATIONAL]**: provenance-bearing gate runs (Phase-0 nodes not yet emitted), the adversarial corpus factory as a systematized product, municipal rule packs with per-rule attack corpora, and customer audit-trail history.

| Copyable in weeks | Head start (months, at current state) | Durable — if built [ASPIRATIONAL] |
|---|---|---|
| The idea: LLM + SHACL for building codes. | The **gate discipline**: per-threshold statute anchors that each survived a break-and-repair cycle (anchor-shadowing, decoy injection, value-swap on equal 2.40s) — per-statute forensic engineering, but demonstrated at n=2 rules only. | A **corpus factory** producing attack fixtures per rule at scale, with gate-run provenance no copier can forge. |
| The stack: Ollama, ifcopenshell, rdflib, pyshacl — all open source. | The **honest-undetermined semantics threaded through every layer** (compliant property, A-Box omission, `sh:minCount`, classified exit codes) — most rebuilds will silently map "missing" to "pass" and not know it, until they hit the same defects we already fixed. | **Customer-side lock-in**: multi-user audit trails, verdict history over model revisions, stored corpora — none exists. |
| Reading DM 5/7/1975 and typing 2.70 / 2.40 / 1/8 into a config. | The **verified statute anchoring + frozen differential oracle**: 220-row equivalence checks, byte-frozen controls across three authoring tools, adversarial IFC corpus with spec-pinned verdicts. Oracle fixtures are public files; the *verdict pins* are the work. | **Gate-verified rule-pack inventory** covering real municipal codes with per-change re-verification — recurring by regulatory churn. |
| A demo that passes clean fixtures. | The **process**: preregistration, external oracles, mutation/metamorphic power demonstrations, 3-for-3 same-actor adversarial rounds catching real shipped defects. Expensive and culturally alien to a "ship the demo" competitor — but a process, not a secret. | A **track record third parties can audit**: external red-team rounds, held-out corpora, CI history. |

**The hardening asymmetry, stated plainly:** thresholds are adversarially hardened (n=2); applicability — *which spaces a rule governs* — is 47/51 unanchored declared debt, and applicability is arguably the harder and more legally-exposed half of compliance. The moat narrative above rests on the hardened half; the unhardened half is Track B gate type 6 (§3.2.4) and must not be quietly excluded from any external pitch.

---

## 2. The Open-Core Monetization Matrix

**Present-tense reality first:** the repo has **no LICENSE file**, so as of today there is **zero open core** — all rights reserved, no adoption, no contributions, no public scrutiny. Every "OSS layer" statement below is therefore **future-tense / [ASPIRATIONAL]** until `LICENSE` and `NOTICE` land. Coverage disclosure: the system ships 2 statute rules over 3 fixtures (DM 5/7/1975 heights + aero 1/8; DPR 380/2001 art. 24 c.5-bis/5-ter; monostanza 28/38/20/28 gate-verified test-side only, runtime honest-undetermined). Everything in the "proprietary" column is aspirational product surface — none exists as sellable inventory.

### 2.1 The split principle [HYPOTHESIS]

Open the layer whose value grows with *public scrutiny and adoption* (engine, method, national baseline); keep the layer whose value grows with *private verification effort or organizational lock-in* (local content, corpora, audit trails, reports). The engine as pure code is replicable by a funded competitor in months (§1.4); its value is maximized by becoming the reference way Italian AEC does automated code checking — free, inspectable, citable. What would not be replicable in months is a corpus of gate-verified, adversarially-tested rule packs plus the audit/provenance machinery that lets a professional stake an asseverazione on the output. Regulatory churn converts content into subscription. **Honest counterweight (from §4):** the `.ttl` encoding of a public statute is thin IP (facts and law are not copyrightable; EU sui-generis database protection is weak for small curated packs [HYPOTHESIS — pending counsel]); the protectable asset is the adversarial corpus + gate-run provenance, and Phase-0 provenance nodes are **not yet emitted** — the one durable artifact is unbuilt.

### 2.2 The matrix (all "side" assignments are the plan, not the present)

| # | Asset | Side (planned) | Status today (verified) | Rationale |
|---|---|---|---|---|
| O1 | **Orchestrator framework** (`sandbox/orchestrator.py`: pyshacl engine, thr-parameterized shapes, fail-closed loader guards, deterministic SPARQL report parsing, MinCount-dominant ternary) | OSS | Shipped [VERIFIED-IN-REPO]; adversarially exercised (Stage-5 minCount guard + exact-at-bar decimal defect caught and fixed, ADR-008a) | The ternary fail-closed verdict model is the credibility argument of the whole product; it must be publicly auditable to be believed by professionals whose signature is on the line. |
| O2 | **A-Box generator pattern** (`sandbox/checker.py`: IfcOpenShell extraction, P0 fail-closed guards, per-space materializer, xsd:decimal contract, C-1b conservative bound) | OSS | Shipped [VERIFIED-IN-REPO]; survived three adversarial rounds + GATE-S 9/9 | The IFC→RDF bridge is the integration surface; an open extractor gets community hardening against exporter quirks (the Duplex 21-undetermined class) faster than any closed team. |
| O3 | **National-statute baseline shapes** (`sandbox/ontology/dm1975_salvacasa.ttl`) | OSS | Shipped (2 rules; monostanza test-side only — no fixture carries a monolocale) [VERIFIED-IN-REPO] | The national baseline is the free tier and the least defensible content (one public 1975 decree); giving it away sets the encoding conventions proprietary packs extend. |
| O4 | **Verification-harness methodology** (frozen byte-identical controls, mutation + metamorphic suites, prereg discipline in `research/PREREG_*.md`) | OSS | Shipped; 189 tests, controls FZK 5/1, Institute 2/2, Duplex 0/21-und. [VERIFIED-IN-REPO] | Methodology spreads by being copied; an open "how to prove a compliance checker isn't lying" harness makes the project the reference standard. **Cost acknowledged:** publishing the method hands it to competitors — this is deliberate funnel spend, defensible only if the durable assets (P1–P4) actually get built. |
| P1 | **Municipal/regional rule packs** (e.g. Milano Regolamento Edilizio, Lombardia overlays) as gate-verified `.ttl` + per-rule attack corpora | Proprietary | **Does not exist** [ASPIRATIONAL]. Engine is thr-parameterized; Stage-4 applicability externalization was built to make packs data, not code | Local-knowledge, recurring re-verification work (~8,000 Italian comuni — public order-of-magnitude figure, not a market size). IP caveat: the `.ttl` itself is thin; the *verification evidence* is the defensible part. |
| P2 | **Multi-user change management + audit trails** (who checked what, which pack version, verdict diffs across revisions) | Proprietary | Does not exist; Phase-0 provenance designed in `research/ONTOLOGY_UPGRADE_BLUEPRINT.md` but **not emitted** [ASPIRATIONAL] | Enterprise workflow layer — near-zero OSS adoption value, high switching cost once adopted. This is where switching costs would come from; today they are nil. |
| P3 | **Regulatory PDF reports with provenance** (statute clause, measured value, threshold derivation, pack version) | Proprietary | Does not exist; depends on P2 [ASPIRATIONAL] | The artifact a professional attaches to a pratica edilizia; value is a reproducible verdict chain. |
| P4 | **Adversarial corpus factory** (systematized exploit-IFC production per rule) | Proprietary | Process real and demonstrated (3 rounds, GATE-S 9/9); factory-as-product [ASPIRATIONAL] | The quality moat behind P1: a rule file can be copied the day it leaks; the corpus proving it fail-closed under attack cannot. |
| P5 | **SLAs, certification support, norm-change monitoring** | Proprietary | Does not exist [ASPIRATIONAL] | Service margin on P1–P4; recurring by regulatory churn — a thesis with **zero validation points** today (no evidence comuni budget for this, and EU/PNRR digital-permit programs may deliver it free; §4, T4). |

**Boundary rule for future assets:** value grows with public scrutiny → OSS; value grows with private verification effort or lock-in → proprietary.

### 2.3 Licensing reality (must be fixed before anything else in this document matters)

**Current state: NO LICENSE file** — all rights reserved; nobody may legally use, copy, or contribute. The open-core strategy is void until this lands, and it must land **before** any external contribution arrives (retroactive relicensing requires contributor consent; DCO/CLA from day one). The repo also has no NOTICE or THIRD_PARTY_LICENSES file. This is the cheapest item in this entire document and it gates every other section — recommending Apache-2.0 from a repo with no LICENSE file is a standing credibility hit; it is Post-freeze Action #1 (§5).

Dependency posture (verified versions) [VERIFIED-IN-REPO]:

| Dependency | License | Obligation |
|---|---|---|
| ifcopenshell 0.8.5 | **LGPL-3.0** | Real; see working interpretation below |
| rdflib 7.6.0 | BSD-3-Clause | Attribution |
| pyshacl 0.31.0 | Apache-2.0 | Attribution + NOTICE |
| Ollama | Separate local process over HTTP | Not a linked library dependency |

**The LGPL-3.0 point — working interpretation, pending counsel; not legal advice and not settled fact.** The common practitioner reading is that importing `ifcopenshell` from Python is analogous to dynamic linking, so our own code may be licensed as we choose; this analogy is **contested**, which is precisely why counsel must sign off before any commercial distribution. Under that working interpretation, obligations bite on **distribution** of a combined product (e.g. an on-prem installer for a comune): (a) ship the LGPL license text and attribution, (b) keep ifcopenshell **user-replaceable** — install as a normal pip dependency, never fuse into a single-file frozen binary (the PyInstaller one-file foot-gun), (c) do not forbid reverse engineering for debugging the library. A SaaS deployment distributes nothing, so the working interpretation is that LGPL obligations are minimal there — again pending counsel, not asserted as settled. Net: LGPL-3.0 looks like packaging discipline rather than a business blocker, **but that conclusion needs a lawyer's signature before it appears in any commercial document.**

**License choice for the open core — recommendation: Apache-2.0** [HYPOTHESIS, decision-grade]:

- **Apache-2.0 (recommended).** Maximal adoption by studi tecnici and by commercial BIM vendors who might embed the checker (every embed sells rule packs); explicit patent grant; low PA-procurement friction; compatible with the LGPL dependency and pyshacl. Risk: a cloud vendor hosts the engine free. Acceptable because the engine without gate-verified packs checks two rules of one 1975 decree — a free-rider hosts our funnel. Consistent with the repo's prior license discipline (Neo4j rejected for GPL-3.0; Oxigraph chosen — `research/ONTOLOGY_UPGRADE_BLUEPRINT.md`).
- **AGPL-3.0 (considered, rejected).** Blocks SaaS free-riding and enables dual-license upsell, but PA and enterprise legal teams routinely ban AGPL, strangling exactly the adoption the OSS layer exists to create; dual-licensing needs copyright consolidation; and it protects the least defensible asset (code). Revisit only if engine-hosting free-riders demonstrably materialize.
- **Rule packs beyond the DM-1975 baseline:** ship under a commercial content license (EULA). **Protectability caveat, stated honestly:** the copyrightable delta of a `.ttl` encoding of a public statute is thin (facts and law are not copyrightable; sui-generis database right weak for small packs) — the EULA is a contract-law fence, **not** "clean" IP, and its enforceability is a counsel question. The practically defensible bundle is pack + attack corpus + gate-run provenance, not the pack alone.
- **Non-negotiables:** `LICENSE`, `NOTICE` (Apache-2.0 + BSD-3 attributions + LGPL-3.0 notice), `THIRD_PARTY_LICENSES` inventory, DCO for contributors. None exists today.

### 2.4 Pricing-model sketch and buyers [HYPOTHESIS — all figures unvalidated; no TAM invented]

| Buyer | Fit model | Rationale |
|---|---|---|
| **Studi tecnici** (geometri, architects; high-volume CILA/SCIA/agibilità/Salva Casa filers) | Per-seat subscription + territory-scoped rule-pack add-ons | Small firms think in per-seat software; workload is many small models in few municipalities. **Channel risk: this is exactly ACCA's installed base (§4, T1).** |
| **Developers / general contractors** (episodic, larger projects) | Per-model-checked credits | Marginal cost per check is effectively zero (measured ~0.4 s warm full FZK check, ~1 ms/space SHACL [MEASURED]), so pricing is pure value capture against project de-risking. |
| **Comuni / PA (uffici tecnici)** | Site license bundling P2 audit trails + P3 reports + P5 SLA | PA buys accountability, not seats. **Channel risk: Maggioli-class incumbents own this procurement relationship (§4, T5); EU ACCORD outputs may commoditize it (§4, T4).** |
| **Certification bodies / CTU-CTP** | Premium tier: packs + adversarial-evidence dossiers (P4) + certification support | They pay for proof the checker was tested to fail closed — the artifact competitors can't fake. Highest willingness-to-pay, smallest volume. |
| **Rule-pack marketplace (long-term)** [ASPIRATIONAL] | Revenue share; packs admitted only through the P4 gate | Scales content past one team; the proprietary gate keeps quality and margin in-house. |

Anchor logic instead of invented numbers: per-seat vs a mid-tier AEC software seat (order of hundreds of €/seat/year — *estimate, unvalidated*); per-model vs a fraction of the professional fee it de-risks; pack subscriptions vs manual code-reading hours replaced. First real pricing data must come from design partners, not this document. **Distribution is the unpriced weakness: no channel into any of these four segments exists today, while every named competitor owns one (§4).**

**Monetization sequencing gates, in order:** (1) LICENSE/NOTICE landed; (2) the ~150-rule generalization trigger actually fired (it has **not**); (3) Phase-0 provenance emitted (P2/P3 prerequisite); (4) one real municipal pack built end-to-end through the adversarial gate as the P1 template; (5) CI + a held-out third-party IFC corpus + one external adversarial round before any externally-relied-upon verdict ships.

---

## 3. Dual-Vector Scaling Backlog

### 3.1 Track A: Data Stress Test

Everything in §3.1.1–§3.1.4 was **[MEASURED]** this session on repo code (branch `audit/p0-m4-stabilization` @ `5df4db5`, from `sandbox/`) on the development machine (Windows 11, Python 3.13.14, ifcopenshell 0.8.5, rdflib 7.6.0, pyshacl 0.31.0, psutil 7.2.1; warm OS file cache). **Measurement-hygiene stamp, applied to every number in this section: single laptop, n=2–3 runs, no CI, and the harness currently lives in the session scratchpad, not the repo — these numbers are not regression-guarded and cannot yet be re-run by a diligence engineer. Phase A-0 exists to close exactly this gap and is a precondition for using these figures externally.** §3.1.5 is **[PROJECTION]** and labeled as such.

#### 3.1.1 Parse cost: `ifcopenshell.open` wall time (3 runs each)

| Fixture | Size | Run 1 | Run 2 | Run 3 | ms/MB |
|---|---|---|---|---|---|
| FZK (`data/AC20-FZK-Haus.ifc`) | 2,526,544 B | 0.160 s | 0.155 s | 0.159 s | ~61 |
| Institute (`data/AC20-Institute-Var-2.ifc`) | 10,786,515 B | 0.706 s | 0.779 s | 0.770 s | ~64–72 |
| Duplex (`data/Duplex_A_20110907.ifc`) | 2,380,763 B | 0.163 s | 0.155 s | 0.156 s | ~65 |

Parse time is **consistent with linear over the measured 2.4–10.8 MB span** (~61–72 ms/MB, warm cache) — three points over a 4.5× span is consistency-with-linear, **not** measured linearity beyond it. Institute is 147,712 IFC entities in 10.8 MB (~73 B/entity on disk).

#### 3.1.2 Full pipeline on the largest fixture: `ComplianceOrchestrator.run` (Institute, 82 spaces)

Via the built-in `PhaseTimer` (`sandbox/orchestrator.py:184`), two consecutive runs; output reproduced the frozen Institute control (2 violations, 0 undetermined, 82 spaces):

| Phase | Run 1 | Run 2 | Per space (warm) |
|---|---|---|---|
| `ifc_extraction_s` | 5.095 s | 4.720 s | ~58 ms |
| `graph_construction_s` | 0.116 s | 0.108 s | ~1.3 ms |
| `shacl_validation_s` | 0.077 s | 0.072 s | **0.88–0.94 ms** |
| total wall | 5.551 s | 5.026 s | — |

This is **consistent with the FZK ~1 ms/space SHACL baseline at 11.7× the space count — at the current rule count (2 rules / 57 shape triples). Per-space SHACL cost growth with rule count is unmeasured; the ~150-rule regime is an open unknown carried on this measurement line itself, not just in a limits appendix.** The run also exposes what FZK (7 spaces) was too small to show: `ifc_extraction_s` is 4.7–5.1 s while raw `ifcopenshell.open` is ~0.7 s — **~4 s of "extraction" is not parsing.** Micro-profiling attributes the residual exactly:

| Extraction sub-phase (Institute, 82 spaces) | Total | Per space |
|---|---|---|
| `classify` — per-space SPARQL over the Stage-4b ontology (`checker.py:450` → `graph.occupancy_via_graph`) | **3.862 s** | **~47 ms** |
| `serving_windows` — BoundedBy traversal (`checker.py:461`) | 0.014 s | 0.17 ms |
| `space_height` + `space_floor_area` (Qto lookups) | 0.089 s | ~1.1 ms |
| `_window_area_bounds` over 206 window relations (C-1b dual lookup, incl. 2nd BoundedBy pass) | 0.123 s | — |

Sum ≈ 4.09 s — fully accounted for. **70–77% of Institute wall time is the occupancy classifier running one rdflib SPARQL query per space.** The blueprint predicted this as risk #1 (`research/ONTOLOGY_UPGRADE_BLUEPRINT.md:519`); it is now the first *measured* hot spot, and its fix is memoization, not architecture.

#### 3.1.3 Memory: opening Institute

psutil RSS in two independent fresh processes (baseline after `import ifcopenshell`, ~78.8 MB): **+83.87 MB and +82.3 MB** RSS for the 10.79 MB file (opens 0.705 s / 0.694 s) → **RSS multiplier ≈ 7.6–7.8× file size** (~560 B/entity in memory). Measured at exactly one file size; RSS deltas are coarse (allocator/OS granularity), though the two runs agree within 2%.

#### 3.1.4 Graph sizes: not a big-data RDF system today

| Graph | Triples |
|---|---|
| Per-space A-Box (`materialize_space_abox`: type + height + aero) | **3** (2 height-only; 1 all-unmeasurable — the `sh:minCount` → UNDETERMINED case) |
| Shapes graph (`ontology/dm1975_salvacasa.ttl`, thr-parameterized, cached) | 57 |
| Stage-4b occupancy ontology (`graph.build_ontology()`) | 260 |
| Per-run IfcSpace store, Institute (`materialize_ifcspaces`, 82 spaces) | 410 (5.0/space) |

The largest RDF object the runtime holds is 410 triples. rdflib-the-*store* is nowhere near a limit; rdflib-the-*SPARQL-engine*, invoked 82 times by `classify`, is the measured cost.

#### 3.1.5 Extrapolation to a 2 GB commercial IFC — **[PROJECTION], with break conditions**

Basis: parse rate consistent-with-linear over a 4.5× span only; RSS multiplier measured at one size point; per-space constants measured at 2 rules. **Break conditions that would invalidate these figures: a different entity mix (geometry-heavy commercial models), the RAM ceiling (paging makes parse time superlinear), and the space-count assumption (2,000–50,000 IfcSpaces for a commercial tower is assumed, not derivable from file size).** All 2 GB numbers below are projections 190× beyond the measured span.

- **(i) `ifcopenshell.open` memory, then time (the wall).** 7.6–7.8× × 2 GB ≈ **~15.5 GB RSS (stated range 12–20 GB)** [PROJECTION] — naive open infeasible on 16 GB, marginal on 32 GB; and 61–72 ms/MB × 2048 MB ≈ **125–150 s** single-threaded [PROJECTION], valid only if RAM suffices. Mitigations [ASPIRATIONAL — no ≥100 MB fixture exists in-repo]: the pipeline needs only `IfcSpace`, `IfcWindow`, `IfcRelSpaceBoundary`, property/quantity sets, and unit entities — entity-filtered pre-extraction (IfcPatch-style subset), IfcOpenShell streaming/iterator facilities, per-storey partitioning with multiprocessing.
- **(ii) Per-space `classify` SPARQL — a measured premise correction.** The expected second bottleneck was BoundedBy traversal; measurement says otherwise: BoundedBy resolves via ifcopenshell's inverse index at 0.17 ms/space, while `classify` costs ~47 ms/space. Unmemoized at 2k–50k spaces: **1.5–40 minutes** [PROJECTION] — the dominant CPU term by an order of magnitude. Fix is trivial and blueprint-sanctioned (memoize per distinct `(Name, LongName)`, or resolve the requirement set once at build time). Caveat: BoundedBy measured at fixture-scale boundary counts only; dense commercial space boundaries could resurface it — demoted to a watch list, not dismissed.
- **(iii) rdflib storage is NOT the bottleneck** until the blueprint's Phase-4 full-model *persistent* graph — precisely where the documented Oxigraph swap lands (`ONTOLOGY_UPGRADE_BLUEPRINT.md` §5.5: one-line `Graph(store="Oxigraph")` via oxrdflib, Apache-2.0, Neo4j rejected GPL-3.0, DoD = byte-identical output under both backends). SHACL at ~0.9 ms/space × 2 rules: 2–45 s at commercial scale [PROJECTION, current-rule-count constant only]; batch validation (one pyshacl call, per-space focus nodes) is the known lever.

#### 3.1.6 Phased optimization path (each phase gated on: 3 frozen controls byte-identical + 189 tests green)

| Phase | Action | Measurable exit criterion |
|---|---|---|
| **A-0 Baseline freeze** | Commit the §3.1 measurement harness + JSON baseline into the repo (today it lives in a scratchpad — a disclosed gap) | Harness re-runs from `sandbox/` and reproduces §3.1.1–3.1.4 within noise |
| **A-1 Classify memoization** | Cache `occupancy_via_graph` per distinct `(Name, LongName)`; verdict-equivalence is by-construction (pure function of its inputs) but is still asserted on all 3 fixtures | Institute `ifc_extraction_s` ≤ 1.2 s (from 4.7–5.1 s); controls byte-identical |
| **A-2 Batch SHACL** (trigger-gated — do not pre-optimize, ADR-005 §1) | One pyshacl call per model using per-space focus nodes (`urn:acc:space:<gid>`) instead of 82 calls on `urn:acc:eval:space` | Institute `shacl_validation_s` ≤ 0.03 s AND per-space verdict equality vs the current path on all 3 fixtures |
| **A-3 Large-model ingestion** (blocked: no ≥100 MB fixture) | Entity-filtered extraction / streaming open; per-storey multiprocessing | On a synthetic ≥500 MB model: peak RSS ≤ 2× the filtered-subset size; verdicts identical to naive open at every size where both paths run |
| **A-4 Oxigraph backend** (blueprint §5.5, trigger-gated) | `Graph(store="Oxigraph")` swap when the full-model persistent graph ships | Byte-identical output under both backends (blueprint DoD); load throughput recorded |

One conflation guard: the classifier whose cost dominates (and which A-1 memoizes) is verdict-equivalent-by-construction on the 3 fixtures only (4/51 tokens statute-anchored) — its **performance** fix must not be confused with **semantic** validation it has not had.

### 3.2 Track B: the Automated Legal Engineer

**Claim, stated precisely and at the right tense: zero human *coding* per rule-pack is the design target of a pipeline that does not exist yet** — all seven stages below carry their build status at the claim, no PDF has ever entered the system, and **the span-quote gate generalization (Stage 3) is the track's stated make-or-break research risk**, promoted here into the headline rather than a limits footnote. Zero human *review* is explicitly NOT claimed — that boundary is designed-in (§3.2.3), because the repo's own measured anchoring boundary (4/51 selection tokens statute-anchored) proves the gate does not yet cover the semantics a lawyer would be liable for.

Track B is not a fresh bet: it industrializes a loop that exists and has survived adversarial attack in this repo. `parser.py` treats a local LLM (Ollama `llama3.1:8b`, temperature 0, 100% offline) as **untrusted** and admits its output only through deterministic re-derivation from statute prose. Design rule: **GATE-FIRST** — every stage is specified by the deterministic check that admits its output, not by the model that produces it. A stage without a machine-checkable admission contract does not ship.

#### 3.2.1 What the repo already proves [VERIFIED-IN-REPO — enforced by `tests/test_gate.py`, 37 of the 189 tests]

| Proven primitive | Where | What it proves |
|---|---|---|
| **Metric-anchored deterministic re-derivation.** Thresholds re-derived from the corpus with the answer key excluded (`crosscheck_corpus`); a clause binds only on value-equality + operator + unit + a metric discriminator in its verbatim span; anything missing/partial/swapped **raises**, no default substituted. | `sandbox/parser.py:346-400`, `:315-336` | Numbers can be admitted from an untrusted extractor without trusting it. |
| **Unique-value-or-reject / decoy rejection.** `re.findall`, not `search`: two distinct values under one anchor → ambiguous → raise, never tie-break. The 1p-monostanza anchor was re-engineered after an adversarial audit showed a single-lead-in anchor could be decoy-shadowed (`parser.py:529-538` documents the rejected design). | `parser.py:315-336`, `:573-586` | Ambiguity is a rejection class. |
| **Enumeration (selection) gate.** Art.1 accessory list re-derived from prose, tokenized, stemmed, matched by stem equality (not prefix); unanchored tokens raise (NO-INVENT); cross-lingual synonyms returned as *declared, unanchored debt*. | `parser.py:466-501`, `:432-463` | The gate pattern extends beyond numbers to vocabularies — with an honest debt channel. |
| **Second-rule replication.** The monostanza surface gate (28/38/20/28 m²) reproduced the pattern with person-count-qualified disjoint anchors. | `parser.py:589-651` | The architecture replicated once (n=2, hand-anchored). |

Downstream, the target format and admission contract exist: `sandbox/ontology/dm1975_salvacasa.ttl` is the shape template (stable `*_PS` URIs, `sh:minCount 1` + `sh:maxCount 1` + `sh:minInclusive`, value-carrying `sh:message`, `rdfs:seeAlso` provenance anchor), and `orchestrator.py:67-91` enforces the ADR-008a fail-closed loader guards, each added because its absence was a *proven* silent-pass (`docs/decisions.md`).

#### 3.2.2 The pipeline, gate-first (seven stages, status at the claim)

1. **PDF → article-segmented text [BUILD].** Layout-aware extraction of Gazzetta Ufficiale / Normattiva PDFs into a canonical UTF-8 corpus segmented at article/comma level, each segment carrying `(law_id, article, comma, char_offsets, sha256)`. Uniqueness-or-reject then applies per article segment (tighter decoy rejection, fewer false-ambiguity raises). **Admission contract:** two independent extractors (candidates `pdfplumber`/`pdfminer.six`, both MIT — **PyMuPDF is AGPL-3.0 and must be license-vetted the way Neo4j was rejected for GPL-3.0**; apply this vet to *every* new Track B dependency) must agree modulo whitespace, else the document is quarantined for human triage; invariants: monotone article numbering, no empty segment, every numeral accounted for in exactly one segment. **Honest scope cut:** scanned/OCR-only PDFs are out of the automated lane in v1. Today's input is a curated markdown (`rules/dm_1975_salva_casa.md`) — Stage 1 is entirely new surface.
2. **LLM RASE extraction [EXISTS, extend].** Local temp-0 model, pydantic `Rule` JSON-Schema-constrained (`parser.py:43-69`), RASE clauses with `operator`/`value`/`unit` and verbatim spans (`SYSTEM_PROMPT` rules 1-3, `parser.py:71-104`). Zero cloud. Admission: schema validation + Stage 3; the LLM remains untrusted by construction.
3. **THE GATE, generalized [EXISTS at n=2 hand-anchored rules; the core R&D — the make-or-break].** Today's anchors (`_SOURCE_ANCHORS`, `_MONOSTANZA_ANCHORS`) are per-metric regexes individually hand-audited — O(engineer-hours per rule), does not scale to ~150 rules. Track B replaces them with a **span-quote verification protocol** needing no per-rule regex authoring: (i) span fidelity — the clause's `text` must be an exact substring of the de-marked segment; (ii) deterministic re-parse — number/unit/direction re-extracted from the span by a fixed rule-agnostic grammar for Italian legal numerics (`m 2,70`, `mq 28`, `1/8 della superficie`, `non inferiore a` → `>=`, `riducibile a` → derogation marker) and required to equal the clause's fields (the repo's value/operator/unit checks, `parser.py:377-386`, sourced from the span itself); (iii) uniqueness in scope — span occurs exactly once in its segment, derived value unique per (metric, segment) (`parser.py:331-336` with the segment as corpus); (iv) answer-key exclusion & anti-echo (as `crosscheck_corpus` today); (v) reject-on-ambiguity everywhere — rejection is a routing outcome to human triage, not a failure. **Meta-gate:** every pack's gate run is auto-mutation-tested — delete the cited span → gate MUST raise; inject a look-alike decoy → gate MUST raise as ambiguous — mechanizing the manual audits done for the monostanza anchors.
4. **TTL emitter [BUILD, template exists].** Compile gate-verified clauses by templating `dm1975_salvacasa.ttl`: stable content-addressed `*_PS` URIs; `sh:minCount 1` + `sh:maxCount 1`; bounds as **`xsd:decimal` via `Decimal(str(v))`** (the ADR-008a exact-at-bar lesson: float 2.40 sits strictly below decimal 2.40 and flips PASS→VIOLATION); `sh:message` **regenerated with the emitted value** (the stale-"2.70"-message defect, ADR-008); `rdfs:seeAlso` → a `legal:NormativeProvision` node; and the **blueprint Phase-0 provenance node**: `prov:wasDerivedFrom` a content-addressed gate-run record (segment sha256, span offsets, gate version) — **[ASPIRATIONAL: Phase-0 provenance is not yet emitted anywhere; Track B is where it becomes mandatory]**. **IFC-bindability sub-gate:** the emitted `sh:path` must resolve against a registry of extractor-supported measurements (today: `acc:heightM`, `acc:aeroRatio`); a rule with no extractor feature compiles to a **structurally-UNDETERMINED shape** (minCount fires on every space, honestly, like Duplex's 21) — never silently dropped, never fabricated.
5. **SHACL meta-validation [EXISTS as loader guards; promote to emit-time CI check].** The `orchestrator.py` guards become the emitter's acceptance test on every generated pack: parse-valid Turtle; every NodeShape has `sh:targetClass` and every declared target class is covered (untargeted = vacuous conformance, the proven ADR-008 silent-pass); every PropertyShape has its bound **and** `sh:minCount >= 1` (the ADR-008a fail-open under TTL tamper); all literals `xsd:decimal`; only constraint components the MinCount-dominant ternary maps (`_shacl_verdict`'s raise becomes an emit-time rejection).
6. **Auto-generated adversarial corpus + differential tests per pack [BUILD, pattern exists].** Per threshold, the synthetic A-Box quartet: below-bar → VIOLATION; **exact-at-bar → PASS** (the ADR-008a regression class, forever pinned); above-bar → PASS; absent → UNDETERMINED. Pack-level: minCount-stripped TTL refused by the loader; decoy-injected corpus makes the gate raise; and the new pack changes **no verdict** on the frozen controls (FZK 5/1, Institute 2/2, Duplex 0/21 — byte-identical or no merge). Battery cost is cheap: measured 0.008 s SHACL for 7 FZK spaces (~1 ms/space warm) [MEASURED].
7. **CI gate [BUILD — and an honest current gap: the repo has NO CI today].** A rule-pack PR merges only when Stages 1–6 artifacts are green (segmentation invariants, gate report with zero unresolved rejections, meta-validation, generated battery, frozen-control byte-identity, license scan on new dependencies) and the human sign-off record is attached. CI is what makes "zero human coding" auditable rather than anecdotal.

#### 3.2.3 The zero-human-CODING vs human-SIGN-OFF boundary

**Design target (of the unbuilt pipeline): zero human coding per rule-pack** — nobody writes a regex anchor, a `.ttl`, or a test file for a new statute; the pipeline emits TTL, provenance, and tests; the only Python is the pipeline itself. This is stated as a target, not an achievement: the per-rule artifacts have mechanizable templates proven in-repo, but the mechanization is [BUILD] and Stage 3's generalization is unproven.

**Not claimed, ever: zero human review.** The gate proves *numeric fidelity to the text*, not *legal correctness of scope*. The repo's own measurement draws the boundary: even in its best-audited corner, only 4/51 selection tokens are statute-anchored — selection semantics are mostly engineering judgment. Auto-emitted `sh:targetClass` decisions inherit that boundary at scale.

**Sign-off design — a lightweight diff-review, not re-engineering.** The reviewer never reads generated Turtle. One table per pack, one row per gate-verified clause: verbatim statute span (article/comma citation, PDF page) · derived number/operator/unit · targeted spaces in plain language · regime (baseline/derogation, and what it derogates) · the four generated test verdicts. The reviewer signs exactly the residual the gate cannot check: *does this rule apply to what the machine says, and does the derogation compose as wired?* The sign-off (who/when/pack-hash) enters the pack's provenance node. Effort estimate "minutes per pack" is [HYPOTHESIS].

**Failure classes that remain human, explicitly:** (1) applicability/selection semantics beyond numbers (the 4/51 boundary generalized — numerically perfect, legally wrong scoping); (2) cross-article references ("di cui all'articolo…", "fermo restando…") — the gate verifies a reference *resolves*, not that its legal effect was encoded; (3) derogation regimes — DPR 380/2001 art. 24 c.5-ter is a cumulative AND that today is operator-asserted via `--salva-casa`, not machine-derived; (4) qualitative requirements ("adeguata ventilazione") — not threshold-representable; emitted as declared out-of-scope, never as a shape; (5) temporal/regional applicability (entry-into-force, transitional regimes, regional overrides).

#### 3.2.4 New gate types required beyond numeric thresholds (priority order)

1. **Span-fidelity gate** — exact-substring verification of every cited span (mechanizes prompt rule 3; today requested of the LLM, enforced only heuristically).
2. **Operator/direction gate** — closed lexicon of Italian comparative phrasing (`non inferiore a` → `>=`, `non superiore a` → `<=`, `almeno`, `fissata in`, `riducibile a`), raise on anything outside it; today `>=` is effectively hardcoded for minima (`parser.py:380`).
3. **Derogation-binding gate** — a derogation must name the bar it derogates, machine-checked against an already-verified baseline (the 2.40-derogates-2.70 relation, currently prompt-engineered in `SYSTEM_PROMPT` rule 4d).
4. **Cross-reference resolution gate** — every "articolo X, comma Y" must resolve in the corpus index; dangling/ambiguous → raise, route to triage (resolution, not interpretation).
5. **Logical-structure gate** — verify emitted AND/OR trees against connective surface forms (c.5-ter); non-machine-evaluable leaves compile to operator-asserted or UNDETERMINED — the honest generalization of `--salva-casa`.
6. **Applicability-class gate** — extend the enumeration gate to every target-class decision: auto-target only if selection tokens anchor to prose (stem-equality, unique-set-or-raise); everything else is declared debt requiring sign-off. **This is the machine that shrinks 4/51 instead of hiding it.**
7. **Unit-lexicon gate** — the deliberately disjoint surface/length unit checks (`_unit_ok`, `_monostanza_unit_ok`, `parser.py:564-570`) generalized into a typed unit registry; unknown unit → raise.
8. **Anchor-power meta-gate** — automated delete-span / inject-decoy mutations per clause (`parser.py:529-538`'s manual audit, mechanized). A gate whose power is untested is scored as no gate.

**Track B status line:** §3.2.1 is measured and in-repo. Everything [BUILD] is design grounded in proven templates but unimplemented: no PDF has entered the pipeline; the gate is proven on 2 rules over hand-written anchors against curated markdown; the span-quote generalization is the principal research risk; there is no CI, no held-out third-party IFC, no Phase-0 provenance emission, and no LICENSE. The claim stood behind is narrower and stronger than the slogan: *an LLM legal engineer whose every number is deterministically re-derived from the statute or rejected, whose every emitted shape is refused unless it fails closed, and whose human reviewer signs only what no machine can yet check* — as a design target.

### 3.3 Recommended sequencing + resource weights

**Order: hygiene gate first (blocking, ~1 week), then Track B carries the main R&D weight (~70%), with Track A held to its cheap measured wins (~30%) until a real large fixture exists.**

1. **Blocking hygiene gate (before either track counts as progress):** LICENSE/NOTICE/THIRD_PARTY_LICENSES + DCO; minimal CI running the 189 tests + frozen-control byte-identity; Track A Phase A-0 (harness into the repo). Rationale: these are days of work, they are stated prerequisites for every external use of this document, and their absence is the red team's most-cited credibility hit.
2. **Track A gets ~30%: do A-0 and A-1 now, then stop until triggered.** A-1 (classify memoization) removes 70–77% of measured wall time for roughly a day of work with a byte-identical exit criterion — the best measured ROI in the backlog. A-2 is explicitly trigger-gated (ADR-005 §1: no pre-optimization), and A-3 is **blocked** on a ≥100 MB fixture that does not exist — pouring effort into 2 GB ingestion now would be optimizing for a customer we do not have, against projections we have labeled as such.
3. **Track B gets ~70%: it attacks the binding constraint.** The project's biggest weakness is not speed — it is **coverage** (2 rules) and the hand-anchoring cost per rule, which is exactly what blocks the ~150-rule trigger, the P1 rule-pack thesis, and any differentiation against a Solibri ruleset author (§4, T2). The first Track B milestone is a **de-risking spike on the make-or-break**: run the span-quote protocol (Stage 3 i–v + meta-gate) against the *existing* curated DM-1975 corpus and require it to reproduce the hand-anchored gate's accept/reject behavior on all existing clauses plus the known decoys before any PDF work (Stage 1) begins. If the spike fails, Track B's design is revised before more is built on it — gate-first applies to the roadmap too.
4. **Cross-cutting, scheduled not deferred:** one external adversarial round + held-out third-party IFC acquisition (the §1.3 committed gate) — these serve both tracks and are the only way the "process moat" claim survives diligence.

---

## 4. Competitive landscape & moat weaknesses (from the red team, unsoftened)

No competitor below is currently addressed by any in-repo asset. This section exists because a moat section with no named competitor is not a moat section. All entries [HYPOTHESIS — desk assessment, no formal teardown done yet; teardowns are Post-freeze Actions #8–9].

### 4.1 Named threats

- **T1 — ACCA software (Bagheria, IT: usBIM, PriMus, Edificius).** The single most direct threat and absent from every earlier draft: the dominant Italian AEC vendor, already regulation-aware, already owning the geometri/ingegneri/studi-tecnici channel our per-seat tier targets. If ACCA ships habitability checking inside usBIM, that segment evaporates. *Honest differentiation:* ACC's fail-closed ternary verification and gate-verified statute anchoring vs a feature checkbox — defensible only if we can *demonstrate* their checker false-passes where ours refuses, which requires the external corpus we do not yet have.
- **T2 — Solibri / Nemetschek Model Checker.** Incumbent rule-based IFC checking, global installed base, ruleset ecosystem. Adding an Italian DM-1975/Salva-Casa ruleset is a **content problem for them, not an architecture problem** — a Solibri ruleset author could replicate our 2 rules in weeks. *Honest differentiation:* Solibri rulesets are not statute-anchored or adversarially verified, and their closed ecosystem cannot show provenance from verdict to statute span; our answer must be verification evidence, not rule count, because we lose on rule count.
- **T3 — buildingSMART IDS + bSDD (standards risk).** If Italian PA or EU digital-building-permit programs standardize on IDS as the machine-readable requirements format, a bespoke SHACL/Turtle ontology becomes a non-standard island. **Stated interop position:** SHACL remains the internal verification representation (IDS cannot express the MinCount-dominant ternary or the provenance chain), and ACC commits to an **IDS export/import bridge** as a roadmap item [ASPIRATIONAL] — comply with the standard at the boundary, keep the verification semantics inside. If IDS wins fully, the gate pipeline (Track B) retargets to emitting IDS, and the moat claim shifts entirely to verification process — this is a real strategic contingency, not a footnote.
- **T4 — EU ACCORD (Horizon Europe) + EUnet4DBP digital-building-permit network.** Publicly funded, open-deliverable efforts to commoditize exactly the statute-to-machine-readable-rules pipeline Track B calls proprietary; their outputs could zero out the rule-pack revenue thesis for the PA segment, and PNRR-funded programs may deliver rule updates to comuni **free**. *Honest differentiation:* consortium deliverables historically lag on production hardening and liability-grade verification; ACC's play is to be the verified implementation of whatever they standardize — a bet, not a fact.
- **T5 — Maggioli / Wolters Kluwer Italy and comune-software incumbents.** They own the procurement relationships with the ~8,000 comuni the site-license tier targets; a compliance module from Maggioli reaches every target buyer before a single-founder startup gets one pilot meeting. **Channel, not technology, decides the PA segment.** *Honest differentiation:* none on channel — the realistic path is partnering/OEM into such an incumbent rather than competing with it.
- **T6 — Foundation-model vendors shipping compliance agents (and enterprises running frontier models on-prem/VPC).** The verify-never-trust gate is a publishable pattern; a frontier model with IFC tooling plus the same deterministic re-derivation gate could outrun ACC on rule coverage. And the "local Ollama, zero cloud" USP erodes as on-prem frontier deployment normalizes — it is a deployment feature, not durable differentiation (§1.2). *Honest differentiation:* the gate + adversarial corpus + provenance discipline transfers to any model backend, including frontier ones — the moat must live in the verification layer, not the model choice.
- **T7 — Authoring-tool natives (Autodesk Revit, Graphisoft Archicad) adding design-time code checking.** Check-while-modeling structurally beats check-after-IFC-export, and IFC-export lossiness is not hypothetical — the Duplex 21-undetermined result **is** evidence the export seam is fragile ground. *Honest differentiation:* ACC's honest-undetermined handling of lossy exports is a strength at the seam, but the seam itself may shrink; the permit/asseverazione moment (which requires the neutral exchange format) is the defensible wedge.
- **T8 — UpCodes-style legal-database players moving down into geometric checking.** They already solve regulatory-churn tracking at scale — the exact recurring-revenue engine §2 claims. *Honest differentiation:* they lack IFC/geometric verification; ACC lacks their statute-tracking infrastructure; whoever crosses the gap first wins the bundle, and they are funded and shipping.

### 4.2 Moat weaknesses (unsoftened)

1. **Rule-pack content is not defensible IP.** Statutes are public; the `.ttl` encoding has thin copyright; a shipped pack (open baseline OR sold) is trivially copyable. The protectable asset would be the adversarial corpus + gate-run provenance data — and Phase-0 provenance nodes are NOT yet emitted. **The one durable artifact is unbuilt.**
2. **The "process is the asset" thesis is self-undermining under open-core.** Methodology published for scrutiny is methodology handed to competitors. No data flywheel, no network effect, no customer feedback loop backs it yet. It is a head start of an estimated 6–12 engineer-months (§1.4), and that is how it should be pitched.
3. **Bus factor = 1.** Single founder, development freeze in effect for an exam session, no CI to hold the line while frozen. For a thesis whose moat is verification velocity and discipline, founder unavailability is a direct moat outage. Disclosed here because omitting it was itself a red-team finding.
4. **No LICENSE file → the open-core flywheel is at absolute zero.** No adoption, no contributions, no scrutiny — every "value grows with public scrutiny" claim is conditional on a roughly one-hour task that has not been done, which also leaves the ifcopenshell LGPL-3.0 obligation blocking any commercial claim.
5. **Zero customers, zero LOIs, zero pilots, zero municipal relationships.** Every item in the proprietary/monetization column is aspirational. Summary sentence, stated plainly: **this is a pre-seed technical asset with a strong verification story, not a company with a moat.**
6. **Switching costs are nil pre-integration.** No workflow embedding, no audit-trail history, no stored corpora at any customer; the lock-in assets (P2/P3) are all in the unbuilt column.
7. **The hardening asymmetry.** Thresholds are adversarially hardened (n=2); applicability — 47/51 occupancy tokens unanchored — is declared debt, and applicability is the harder and more legally-exposed half of compliance. The moat narrative rests on the hardened half.
8. **All performance evidence tops out at 10.8 MB / 82 spaces on one developer laptop with no CI.** The commercial-scale story (2 GB, Oxigraph, streaming) is 100% blueprint + projection. A competitor with real project files has an evidence base this repo lacks — no held-out third-party IFC exists.
9. **Distribution is the unpriced weakness.** Four buyer segments are mapped (§2.4); zero channels into any of them exist, while ACCA, Maggioli, and Nemetschek each already own one.
10. **The regulatory-churn recurring-revenue thesis has zero validation points.** No evidence Italian comuni budget for rule-update subscriptions, and PNRR/EU digital-permit programs may deliver updates free (T4).

---

## 5. Post-freeze action list (first 10 working days back)

Each item has an owner (founder — bus factor 1), a done-criterion, and maps to a gap named above. Days are working days, sequenced by dependency.

| Day | Action | Done when | Closes |
|---|---|---|---|
| 1 | **Land licensing:** `LICENSE` (Apache-2.0 per §2.3), `NOTICE` (Apache-2.0 + BSD-3 attributions + LGPL-3.0 ifcopenshell notice), `THIRD_PARTY_LICENSES`, DCO note in CONTRIBUTING | Files committed on a branch off `main`; LGPL interpretation + rule-pack EULA protectability flagged in a counsel-questions list | §2.3; weakness #4 |
| 2 | **Minimal CI** (GitHub Actions): 189 tests + frozen-control byte-identity (FZK 5/1, Institute 2/2, Duplex 0/21) on every push | A red/green badge on PR #1; a deliberately broken control fails the build | Weaknesses #3, #8; Track B Stage 7 precursor |
| 3 | **Track A Phase A-0:** move the measurement harness from the session scratchpad into `sandbox/` with a JSON baseline | Harness re-runs and reproduces §3.1.1–3.1.4 within noise, in CI as a non-blocking job | §3.1 hygiene stamp |
| 4 | **Track A Phase A-1:** memoize `occupancy_via_graph` per distinct `(Name, LongName)` | Institute `ifc_extraction_s` ≤ 1.2 s; 3 controls byte-identical; 189 green | §3.1.2 measured hot spot |
| 5 | **Merge PR #1** (branch `audit/p0-m4-stabilization`) with days 1–4 folded in, closing the stabilization audit | PR merged to `main` with CI green | Repo hygiene |
| 6–7 | **Track B make-or-break spike:** span-quote gate (Stage 3 i–v + delete-span/inject-decoy meta-gate) run against the existing curated DM-1975 corpus, no PDF work | Reproduces the hand-anchored gate's accept/reject behavior on all existing clauses + known decoys, or a written revision of Track B's design | §3.2.2 Stage 3; §3.3 item 3 |
| 8 | **Held-out corpus + external round setup:** source ≥1 third-party IFC never used in development (kept out of the repo); draft the scope/brief for one genuinely external adversarial round | Fixture acquired and quarantined; external-round brief written with budgetary estimate | §1.3 committed gate; weakness #8 |
| 9 | **Competitor teardown, part 1:** ACCA usBIM and Solibri Italian-ruleset capabilities vs the §4.1 desk assessment; record an IDS export feasibility note (T3 position) | One-page teardown per competitor committed to `research/`, with the false-pass-demonstration test plan for T1 | §4.1 T1–T3 |
| 10 | **Phase-0 provenance spike + first outreach:** emit `prov:wasDerivedFrom` gate-run nodes for the two existing rules (blueprint Phase-0); send 3 design-partner emails (studi tecnici) for a pilot conversation | Provenance nodes in the A-Box behind a flag, round-tripping through the orchestrator with controls byte-identical; 3 emails sent | Weakness #1 (the unbuilt durable artifact); weakness #9 |

Standing rule carried out of this document: **every claim that leaves this repo carries its taxonomy tag, and the qualifier travels with the claim.** A strategy document that overclaims is a defect; this one has been red-teamed accordingly, and the red team's findings are folded in above rather than appended.
