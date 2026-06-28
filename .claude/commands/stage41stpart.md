---
description: "Stage 4 (rescoped: verified applicability + rule generalization; graph DEFERRED) PART 1: read-only artifact-grounded baseline that confirms the statute anchors, freezes the declarative-applicability-table + generalized-requirement-model schema, records the rescope/deferred-graph decision, then authors /stage42ndpart. No production-code edits."
---

# Stage 4 · Part 1 — Baseline + design freeze → author Part 2 (READ-ONLY on production code)

Repo: `acc-neurosymbolic-core` (Slice A). Stages 1–3 are done; Stage 3 closed 🟢 (ADR-004,
geometry probed + declined). The active target is **Stage 4 — RESCOPED**. The original ROADMAP
Stage 4 ("Graph anchoring (scalability)", `ROADMAP.md:117-127`) was stress-tested by a 7-lens
adversarial workflow and found to be a premature abstraction (a vocab-only graph meets the
done-when in *letter not spirit*: `classify()` still runs in Python before any query; the
equivalence proof is circular; the `thresholdKey`/`getattr` indirection is cosmetic and breaks on
rule #2). **The user re-scoped Stage 4** (decisions recorded below) to attack the *real* gaps —
the verification gap and the unproven generalization — with no graph yet.

**Rescoped Stage 4 goal:** *the rule model + the verify-never-trust gate generalize beyond one
rule, and applicability/selection is externalized into a declarative, gate-verified model — not
hardcoded in Python.* The graph is split out as a future **Stage 4b** with its store pre-decided.

**User decisions (this is the frozen scope — do not re-litigate):**
1. **Table first, defer the graph** — externalize applicability/selection out of Python into a
   declarative, gate-verifiable data file; build the graph only when inference/scale needs it.
2. **Co-deliver the alloggio monostanza surface rule** as a real 2nd rule (≥28 m² 1p / ≥38 m² 2p;
   →20/28 under Salva Casa) — to force the abstraction to be real.
3. **Extend the verify-never-trust gate to applicability/selection**, to the extent the statute
   anchors it (Italian terms ↔ Art.1; the German/KIT hints have NO Italian-statute anchor and stay
   a declared, test-pinned cross-lingual glossary = named debt — do NOT overclaim).
4. **Graph store, when later built (Stage 4b): rdflib (`==7.6.0` pinned, standard Store API +
   SPARQL 1.1 so Oxigraph is a one-line backend swap); Oxigraph as the documented upgrade; Neo4j
   rejected (GPL-3.0 on a commercial asset).**

Part 1 produces **facts + a frozen design, not code**. It is structured so subagents cannot launder
hallucinations (every statute/code claim is re-derived from the on-disk file, never trusted from
prose). It ends by **authoring the Part-2 command from the confirmed findings**.

> **Working directory.** Run everything from the repo root
> `C:/Users/matte/Desktop/Desktop OLD/AI/Università AI/courses/personal_project/industrial.review/acc-neurosymbolic-core`
> — every relative path below (`sandbox/…`, `docs/…`, `.claude/…`) is relative to it. If this session
> started elsewhere, `cd` there first.

## BOOT (read first, no edits)
`docs/decisions.md` (ADR chain = memory; **ADR-004** newest), `CLAUDE.md`, the approved plan
`C:/Users/matte/.claude/plans/toasty-humming-pine.md` (the rescope + design), `ROADMAP.md` → Stage 4
(`:117-127`) + Iteration Log, `sandbox/checker.py` (the `Thresholds`/`classify`/`check_space`
surface you PROFILE, not change), `sandbox/parser.py` (the gate + `SYSTEM_PROMPT` decoy set +
`THRESHOLD_KEYS` you PROFILE, not change), `sandbox/rules/dm_1975_salva_casa.md` (the statute — the
anchors live here), `sandbox/rules/compiled/dm_1975_salva_casa.json` (the compiled rule, empty
`applicability`/`selection`).

## START CONTROLS (run first from `sandbox/` — if any is off, STOP: env/regression, not Stage 4)
- `python tests/test_gate.py` → **19/19**; `python tests/test_height_keys.py` → **9/9**;
  `python tests/test_geometry_fallback.py` → **12/12**.
- `python checker.py data/AC20-FZK-Haus.ifc --json data/AC20-FZK-Haus_report.json` → **5**;
  `--salva-casa` → **1**.
- `python checker.py data/AC20-Institute-Var-2.ifc --json ...` → **2** (spaces **402/403**);
  `--salva-casa` → **2**.
- `python checker.py data/Duplex_A_20110907.ifc --json ...` → **0 violations / 21 undetermined**
  (both modes; exit ≠ 0 EXPECTED). If a `data/*.ifc` is missing, re-acquire per the Part-2/Part-3
  fixture notes (Duplex from the `media.githubusercontent.com` LFS endpoint).
- **Capture the frozen control GlobalId sets** (not just counts): FZK's 5 / its 1, Institute's
  `402`/`403`, both modes — these are the Stage-4 acceptance anchors, identical to Stage 3.

## HARD RULES (subagent-proof + anti-hallucination)
- **No tracked-source edits**: not `checker.py`, `parser.py`, the law `.md`, the compiled rule JSON,
  or `ROADMAP.md`. A baseline is not a system change → **no ROADMAP flip and no ADR in Part 1.**
- **Allowed writes only**: `sandbox/STAGE4_BASELINE.md` (deliverable), `sandbox/probe_*.py` scratch +
  `data/*_report.json` (git-ignored diagnostics), and `.claude/commands/stage42ndpart.md` (authored
  at the end).
- **Evidence is artifact-grounded, never prose-trusted.** Treat each probe SUBAGENT as UNTRUSTED (the
  Stage-2 gate's stance toward the LLM). An agent's claim is admissible only if it pastes the exact
  command + raw stdout (e.g. the verbatim statute line, the `grep` hit, the `dir()`/source excerpt).
  Before writing the baseline you (orchestrator) **re-derive every anchor and every code fact from the
  file on disk** — any claim you cannot reproduce is **dropped and flagged**.
- **Observation separate from interpretation**; cite `parser.py:<line>` / `checker.py:<line>` /
  `dm_1975_salva_casa.md:<line>` for every claim.
- "Failure" = not returning a finding. A missing anchor, an ambiguous applicability dimension, a
  fixture lacking monolocale data are **valid recorded observations**, never a reason to abort.

## DECOMPOSITION — read-only probe IN PARALLEL (use the Workflow tool)
**Required form: use the Workflow tool** — a `parallel` probe phase, then an orchestrator VERIFY
phase that re-derives every anchor/fact from the files. Invoking this command is the opt-in to run
it. Probes are READ-ONLY (may write `sandbox/probe_*.py` scratch + the baseline note; never
`checker.py`/`parser.py`). Three probe tracks:

**Track A — Statute anchors (the verification foundation).** From `sandbox/rules/dm_1975_salva_casa.md`,
paste verbatim and cite line:
- (a) **Selection anchor:** Art.1 enumerates the accessory rooms — *"corridoi, i disimpegni in
  genere, i bagni, i gabinetti ed i ripostigli"* (`:9-10`; RASE selection `:61`). Confirm the exact
  Italian tokens — these are the ONLY accessory terms gate-verifiable against the statute.
- (b) **Monostanza numbers:** `≥28 m²` / `≥38 m²` (`:26-28`) and Salva-Casa derogation `≥20 m²` /
  `≥28 m²` (`:37`); the comma-5-ter cumulative-AND regime (`:39-46`). These are the 2nd rule's
  anchors + discriminators.
- (c) **Decoy set still to reject:** montani `2,55` (`:15-17`) and any seismic-zone height — confirm
  they are decoys, NOT requirements.
- Cross-check the answer-key block (`:58-66`) is the part the gate's corpus-exclusion DROPS (so
  applicability/selection verification must anchor to the *prose* `:8-46`, not the decomposition).

**Track B — Gate surface (what extending the gate touches; READ-ONLY on `parser.py`).** Cite lines:
- The `SYSTEM_PROMPT` clause that names **monostanza surface as a DECOY** (the thing Part 4
  un-suppresses) and the montani/seismic decoy clauses (the things that must STAY rejected).
- `THRESHOLD_KEYS`, `_METRIC_DISCRIMINATORS`, the per-key regex anchors, `verify_rule_against_text`
  (note it already walks `rule.selection`/`rule.applicability` but never checks them), and
  `assert source=='llm'`.
- The exact normalization (Italian comma, `1/8→0.125`) and the unique-value-or-reject logic.

**Track C — Generalization surface (what generalizing the model touches; READ-ONLY on `checker.py`).**
Cite lines:
- `Thresholds` (the 4 fixed fields `:66-69`), `from_rules_json` whitelist (`:72-79`),
  `compile_thresholds` in `parser.py`. Confirm: a 2nd-rule key has no field → `getattr` would raise.
- `classify()` hint tuples (`:45-59`, incl. the codepoint-sensitive `küche`/`kuche`),
  `check_space()` height-bar selection (`:195-197`) + aero applicability (`:219-226`) + the
  salva-casa swap. Build the **distinct `{Name, LongName}` corpus from the 3 live IFC fixtures** (the
  Part-2 equivalence test's oracle) — and note whether ANY fixture carries monolocale / person-count
  data (expected: NONE → monostanza will be honestly UNDETERMINED, verdict-neutral).

**Each track returns STRUCTURED JSON** with `{track, claims:[{fact, file_line, raw_excerpt}],
open_questions, notes}`.

## VERIFY (orchestrator; untrusted-agent stance)
Re-open each cited file yourself and confirm every pasted anchor/excerpt is byte-accurate. Re-run the
START CONTROLS from the artifacts (FZK 5→1, Institute 402/403, Duplex 0/21). Drop and flag any claim
you cannot reproduce. Confirm the monostanza-decoy clause and the montani/seismic decoys exist
verbatim (Part 4 must un-suppress the former while keeping the latter rejected).

## SYNTHESIS — write `sandbox/STAGE4_BASELINE.md` (all claims file:line-cited)
- The **rescope record**: why the graph was deferred (the adversarial findings, one paragraph), the 4
  user decisions, and the explicit split (Stage 4 = generalization+verified-applicability; Stage 4b =
  graph, store pre-decided).
- The **anchor table**: selection (Art.1 tokens), monostanza numbers (28/38/20/28), decoys-to-keep
  (montani/seismic) — each with verbatim excerpt + line.
- The **generalization surface**: exactly what changes to make `Thresholds`/`THRESHOLD_KEYS`
  backward-compatible-but-extensible (the 4 frozen numbers MUST resolve byte-identically).
- The **frozen declarative-table schema**: the occupancy/selection/regime record shape, with
  `unknown` = strict complement, accessory-first precedence, fail-closed NOT-FOUND→None, and the
  Italian-anchored vs cross-lingual-glossary (debt) split.
- The **monostanza applicability dimension** (unit-level: is-monolocale + person count) and the
  recorded fact that it is UNDETERMINED on all 3 fixtures (verdict-neutral, honest).
- The **production-safety invariant** (unchanged): never silently mark an unmeasurable space
  compliant; missing data ⇒ `undetermined`, never a pass.

## REFINE (completeness critic — before authoring Part 2)
Re-read adversarially and resolve in the doc: is any anchor ambiguous (run ONE more read-only probe,
don't carry ambiguity forward)? Are the four parts' changes independent or coupled (state the order:
P2 generalize-model+externalize-table is verdict-neutral/lowest-risk; P3 gate-to-A/S is
verification-only; P4 monostanza+gate-to-its-numbers is the highest-risk generalization proof)? Is
the cross-lingual-glossary debt clearly bounded (which hints can/can't anchor to Art.1)?

## AUTHOR PART 2 — write `.claude/commands/stage42ndpart.md` from the REFINED findings
Context-complete, not blind. Part 2 = **generalize the requirement model + externalize the
applicability table, VERDICT-NEUTRAL** (no graph). For each task include: target function +
`checker.py:line`, the change (single concern), the **expected verdict delta (none — controls
frozen)**, the binding acceptance test (per-`GlobalId` table-driven-vs-current-Python equality of
`(occupancy, height_required, aero_applies, compliant)` across all 3 fixtures BOTH modes, run BEFORE
trusting it; hint-set byte-equality incl. codepoints), and the REGRESSION BLOCK (`test_gate` 19/19,
`test_height_keys` 9/9, `test_geometry_fallback` 12/12, FZK 5→1, Institute 402/403, Duplex 0/21 — all
byte-identical). Tasks sequential, single-concern, lowest→highest risk, full regression after each,
revert-on-control-move. State that Parts 3 (gate→A/S) and 4 (monostanza) are authored later from
Part 2/3 results — do NOT pre-write them blind.

## DONE-WHEN (Part 1)
1. `sandbox/STAGE4_BASELINE.md`: rescope record + the 4 decisions; the anchor table (Art.1 selection,
   monostanza 28/38/20/28, montani/seismic decoys-to-keep) all file:line-cited and byte-verified; the
   generalization surface; the frozen declarative-table schema + monostanza applicability dimension +
   the cross-lingual-glossary debt boundary; the production-safety invariant.
2. `.claude/commands/stage42ndpart.md` authored from the findings (per-task: function, line, change,
   verdict-neutral acceptance test, regression block).
3. Controls intact: `test_gate.py` 19/19, `test_height_keys.py` 9/9, `test_geometry_fallback.py`
   12/12; FZK 5→1; Institute 2→2 (402/403); Duplex 0/21. Frozen GlobalId sets recorded.
4. `git status` shows ONLY the new baseline doc + the new Part-2 command (+ git-ignored
   `data/*_report.json` and `probe_*.py`); no tracked source changed. Append a `.idos/events.jsonl`
   line ONLY if a real STOP/GATE/DEFECT was found.
Then **STOP** and hand back the anchor table, the frozen schema, and the authored Part-2 command for
review. Do **not** edit `checker.py`/`parser.py` — that is `/stage42ndpart` onward.
