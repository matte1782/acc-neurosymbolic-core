# FAQ — the honest-limits page

**Is this legal advice / can I attach the output to a pratica edilizia?**
No. The engine produces deterministic measurements compared against statute-derived bars; it
does not replace professional judgment, and nothing here is legal advice. The HTML report
says this on its face. A provenance-certified report format is future, separate work.

**Why does my model come back "non determinabile" everywhere?**
Almost always: the export carries no space quantities (net height / NetFloorArea). Revit's
default IFC export is the classic case — our own Duplex fixture reads honestly 21/21
undetermined. Geometry-derived substitutes were probed and declined on evidence: they recover
*gross*, not *net*, values, which would fabricate passes (ADR-004). Fix: export with base
quantities (a Qto/BaseQuantities-bearing setup) — the engine then measures normally.

**Why not just guess from geometry like other tools?**
Because a fabricated pass is the worst possible defect for a tool whose output someone signs.
"Non determinabile" is a feature: it tells you exactly which spaces your model cannot prove.

**Can it check my region's rules?**
The mechanism is proven (a mock regional pack with different bars runs end-to-end), but real
regional/municipal packs don't exist yet — building one requires the statute-verification
gate, an adversarial test corpus, and (for new measurement types) an extractor. That is
exactly the work we want to do with design partners.

**Is my model uploaded anywhere?**
No. Everything — parsing, rules, verdicts, even the optional local LLM used at rule-authoring
time — runs on your machine. The API seam is self-hosted. Local-first is a design position.

**How fast is it?**
Indicative, this-machine numbers: a 7-space house evaluates in ~0.2–0.4 s; ~1 ms per space
for the SHACL validation, warm. We publish no benchmark claims until a proper harness exists.

**What's the license situation?**
Engine: Apache-2.0 (`LICENSE`); dependency inventory in `NOTICE` and `THIRD_PARTY_LICENSES`
(ifcopenshell is LGPL-3.0 — consumed as an ordinary, user-replaceable pip dependency). Posture
notes pending counsel review are marked as such; nothing here is a legal opinion.

**Who is behind this / how mature is it?**
A pre-1.0 research-grade engine with an unusually heavy verification harness (the entire
decision history, including every defect found by adversarial review, is public in
[`docs/decisions.md`](decisions.md)). Treat it as an instrument to evaluate, not a product to
rely on — and if you evaluate it, we want to hear what broke: that is the point.
