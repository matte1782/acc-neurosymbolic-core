---
description: "Stage 3 (multi-software robustness) PART 1: read-only artifact-grounded baseline on 3 IFC fixtures, then author /stage32ndpart from the findings and decide if /stage33rdpart is needed. No production-code edits."
---

# Stage 3 · Part 1 — Diagnostic baseline → author Part 2 → decide Part 3 (READ-ONLY on production code)

Repo: `acc-neurosymbolic-core` (Slice A). Stage 2 is ✅ done+verified; the active target is
**Stage 3 — Multi-software robustness** (`ROADMAP.md:23`, 🟡 **1/3**): the *same* `checker.py` must
give a clean, runtime-error-free verdict on ≥3 IFC models from different tools.

Part 1 produces **facts, not code**. It is structured so subagents cannot create inconsistency
(each owns one fixture, none touches shared code) and cannot launder hallucinations into the plan
(every number is re-derived from on-disk artifacts, never trusted from agent prose). It ends by
**authoring the Part-2 command from the real findings** and **deciding whether Part 3 is needed**.

> **Working directory.** Run everything from the repo root
> `C:/Users/matte/Desktop/Desktop OLD/AI/Università AI/courses/personal_project/industrial.review/acc-neurosymbolic-core`
> — every relative path below (`sandbox/…`, `docs/…`, `.claude/…`) is relative to it. If this session
> started in a different folder, `cd` there first before doing anything else.

## BOOT (read first, no edits)
`docs/decisions.md` (ADR chain = memory; **ADR-002** newest), `CLAUDE.md`, `ROADMAP.md` → Stage 3 +
"Naming divergences" (`ROADMAP.md:103-106`), `sandbox/checker.py` (the symbolic half you PROFILE, not
change), `sandbox/README.md` fixtures table (`README.md:63-65`).

## START CONTROLS (run first — if either is off, STOP: it is an env/regression problem, not Stage 3)
- `cd sandbox && python tests/test_gate.py` → **19/19** (Stage-2 gate intact).
- `python sandbox/checker.py sandbox/data/AC20-FZK-Haus.ifc --rules sandbox/rules/compiled/dm_1975_salva_casa.json`
  → **5** violations; add `--salva-casa` → **1**.

## HARD RULES (subagent-proof + anti-hallucination)
- **No tracked-source edits**: not `checker.py`, `parser.py`, the law `.md`, or `ROADMAP.md`. A
  diagnostic is not a system change → **no ROADMAP flip and no ADR in Part 1.**
- **Allowed writes only**: `sandbox/data/*.ifc` and `sandbox/data/*_report.json` (git-ignored),
  `sandbox/STAGE3_BASELINE.md` (deliverable), and `.claude/commands/stage32ndpart.md` (authored at the end).
- **Evidence is artifact-grounded, never prose-trusted.** Treat each diagnostic SUBAGENT as UNTRUSTED
  (the same stance the Stage-2 gate takes toward the LLM). An agent's report is admissible ONLY if it
  (i) pastes the exact commands it ran + their raw stdout and (ii) writes the checker's `--json` report
  to disk. Before writing the baseline you (orchestrator) **re-derive every headline number directly
  from the saved `data/*_report.json` plus an independent `ifcopenshell` re-count** — not from the
  agent's narration. Any asserted number you cannot reproduce from an artifact is **dropped and flagged**.
- **Observation separate from interpretation**; cite `checker.py:<line>` for every claimed gap.
- "Failure" = not returning a report. A dead URL, a crash, or all-`None` quantities are **valid
  recorded observations**, never a reason to abort.

## DECOMPOSITION — 3 diagnostic agents IN PARALLEL (one per fixture)
**Required form: use the Workflow tool** — a 3-item `parallel` profiling phase (one fixture each),
then an orchestrator VERIFY phase that re-derives the numbers from the saved artifacts. Invoking this
command is itself the opt-in to run that Workflow. Each agent owns ONE fixture and writes only that
fixture's `data/<stem>.ifc` + `data/<stem>_report.json`. Run from `sandbox/`.

**Fixtures (deterministic, verified acquisition):**
1. **AC20-FZK-Haus** — *control*, already in `data/`. Expect 7 `IfcSpace` / 11 `IfcWindow` / 81
   boundaries, IFC4. MUST reproduce **5 → 1**.
2. **AC20-Institute-Var-2** — `curl -L -o data/AC20-Institute-Var-2.ifc https://www.steptools.com/docs/stpfiles/ifc/AC20-Institute-Var-2.ifc`.
   Verify `schema=="IFC4"` and `IfcSpace≈82`, `IfcWindow≈206`; mismatch ⇒ record + STOP-flag (wrong file).
3. **Duplex Apartment** (IFC2X3, Revit). Do NOT trust a guessed URL. **Resolve** the IFC2X3 Duplex
   `.ifc` inside `github.com/buildingsmart-community/Community-Sample-Test-Files` via `gh api`/repo
   listing, download the raw file, and **record the resolved URL**. Verify `schema=="IFC2X3"` and
   `IfcSpace≈21`, `IfcWindow≈24`; mismatch ⇒ record + STOP-flag.

**Each agent does, for its fixture only — and pastes the raw stdout of every command:**
- **(a) Acquire + integrity:** ensure `data/<file>.ifc` present (download per above); open with
  `ifcopenshell`; report `schema` + counts (`IfcSpace`, `IfcWindow`, `IfcRelSpaceBoundary`) vs README.
- **(b) Baseline run (UNCHANGED checker):** `python checker.py data/<file>.ifc --json data/<stem>_report.json`,
  then again with `--salva-casa`. Capture `crashed` (full traceback if so), `schema`, `spaces_evaluated`,
  `violations` (both modes).
- **(c) Profile divergences** (from the report + introspection): #spaces with `height==None`,
  `floor_area==None`, `aero_ratio==None`; #spaces with a resolved window (`window_area_m2>0`);
  classification counts (habitable/accessory/unknown); the actual Qto/pset names on `IfcSpace`; which
  height keys exist (`Height`/`ClearHeight`/`FinishCeilingHeight`/`AltezzaNetta`/other); whether
  `space.BoundedBy` yields any `IfcWindow`; the unit scale to metres.
- **(d) Map each gap to the mechanism it stresses, citing line:** height-key lookup (`checker.py:117-118`),
  `windows_serving` boundary-only + TODO fallback (`checker.py:147-158`), `space_floor_area` keys
  (`checker.py:121-126`), Qto-name candidates (`checker.py:100-101`).

**Each agent returns STRUCTURED JSON:**
```
{ fixture, schema, downloaded_ok, resolved_url, counts:{ifcspace,ifcwindow,boundaries}, counts_match_readme,
  crashed, traceback, violations_baseline, violations_salva_casa,
  none_height, none_area, none_aero, windows_resolved, classification:{habitable,accessory,unknown},
  qto_names:[...], height_keys:[...], boundary_resolves_windows,
  gaps:[ {symptom, checker_line, minimal_fix_idea} ],
  commands_run:[...], raw_stdout_excerpt, notes }
```

## VERIFY (orchestrator; untrusted-agent stance)
Open each `data/<stem>_report.json` yourself and recompute violations / none_* / windows_resolved /
classification; independently re-count `IfcSpace`/`IfcWindow`/boundaries with `ifcopenshell`. On any
divergence from an agent's report, **trust the artifact** and note the agent error. The FZK control
must still be **5 → 1** from the artifact.

## SYNTHESIS — write `sandbox/STAGE3_BASELINE.md` (all numbers artifact-derived)
- one **evidence table per fixture** (counts vs expected, crashed?, violations, none-height/area,
  windows-resolved, classification);
- a **prioritized GAP LIST**: each = `{symptom, fixtures affected, checker.py:line, minimal fix}` —
  describe only, do **not** implement;
- a **min-bar vs real-bar** recommendation (runs crash-free on 3 tools  vs  yields a *meaningful*
  verdict — needs multi-key height + a window/geometry fallback for Duplex).

## REFINE (completeness critic — before authoring Part 2)
Re-read the baseline adversarially and resolve, in the doc:
- Any **under-characterized** fixture (e.g. Duplex window resolution or height keys not actually
  tested)? If a gap is ambiguous, run ONE more targeted read-only probe — do not carry ambiguity into
  Part 2.
- Are gaps **independent** (safe one-by-one) or **coupled**? State the dependency/fix order.
- State the **production-safety invariant** Part 2/3 MUST honor: *the checker must never silently mark
  an unmeasurable space COMPLIANT* — missing height/area/window ⇒ the space stays flagged with a note,
  never a pass (symbolic analog of the Stage-2 no-launderer rule).

## AUTHOR PART 2 — write `.claude/commands/stage32ndpart.md` from the REFINED findings
Context-complete, not blind. For EACH hardening task include: target function + `checker.py:line`,
the fixture(s) that exercise it, the **expected verdict delta** (before→after), the exact regression
command, and the invariant that **all 3 fixtures + the FZK 5→1 control + test_gate.py 19/19 must still
pass after the edit**. Tasks are **sequential, single-concern**, ordered lowest-risk → highest-risk,
each followed by re-running all 3 fixtures.

## DECIDE PART 3 (go/no-go, evidence-based — record the trigger in the baseline)
- **No Part 3** if the gaps are few and mechanical (multi-key height lookup, extra classify hints,
  Qto-name additions) — they fit safely in Part 2.
- **Spin Part 3** (`/stage33rdpart`, to be authored later from Part 2's results) if a gap is high-risk
  or coupled — specifically the **geometry fallback** (deriving height/area/window area from the 3D
  shape when Qto/boundaries are absent: the Duplex case). It touches multiple functions, risks wrong
  numbers, and needs its own verification harness, so keep it OUT of Part 2.
State the decision and its trigger explicitly so it is reproducible.

## DONE-WHEN (Part 1)
1. `sandbox/STAGE3_BASELINE.md`: 3 fixtures characterized with **artifact-derived** numbers, a
   file:line gap list, dependency/fix order, min-vs-real recommendation, the production-safety
   invariant, and the Part-3 go/no-go + trigger.
2. `.claude/commands/stage32ndpart.md` authored from the findings (per-task: function, line, fixture,
   expected delta, regression command).
3. Controls intact: `test_gate.py` 19/19; FZK **5 → 1**.
4. `git status` shows ONLY the new baseline doc + the new Part-2 command (+ git-ignored `data/`); no
   tracked source changed. Append a `.idos/events.jsonl` line ONLY if a real STOP/DEFECT was found.
Then **STOP** and hand back the gap list, the authored Part-2 command, and the Part-3 decision for
review. Do **not** edit `checker.py` — that is `/stage32ndpart`.
