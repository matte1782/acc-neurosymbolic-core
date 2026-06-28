# Stage 4 · Part 4 — The 2nd rule (alloggio monostanza): generalize the gate + model end-to-end, decoy un-suppressed, monostanza UNDETERMINED on the 3 fixtures (highest-risk generalization proof)

Repo: `acc-neurosymbolic-core` (Slice A). Parts 1–3 are done and green: the baseline + frozen design
is `sandbox/STAGE4_BASELINE.md`; Part 2 generalized the requirement model + externalized the
applicability/selection table; Part 3 anchored the accessory selection tokens to DM-1975 Art.1 via a
verified `parser.py` primitive enforced by `test_gate.py` (27/27). Part 4 is the **proof the
abstraction admits a 2nd rule at each layer** (gate verification + model record + an honest undetermined
channel): add the **alloggio monostanza** surface rule — the
**gate** verifies its four numbers (`28 / 38 / 20 / 28`) against the statute, the **requirement model**
holds the new metric, the monostanza **decoy is un-suppressed** in the prompt while **montani 2,55 and
seismic stay rejected**, and the checker evaluates monostanza to **`undetermined` / not-applicable on all
3 fixtures** (no monolocale unit / person-count data — baseline §6) — **never a pass**. The four frozen
height/aero verdicts (`FZK 5→1`, `Institute 2→2`, `Duplex 0/21`) move by **zero**. Then ADR-005 +
ROADMAP renarrow + the Stage-4b graph split.

> **Why this is the hard part, and why the design below is the minimal-safe one.** Baseline §1
> decision 2 co-delivers monostanza precisely "to force the abstraction to be real." Three traps make
> it the highest-risk part, each pre-resolved here against the on-disk artifacts:
> 1. **The shared 28.** The four monostanza numbers are `28` (1p baseline, `mq 28`), `38` (2p baseline,
>    `mq 38`), `20` (Salva-Casa 1p, `20 m²`), `28` (Salva-Casa 2p, `28 m²`) — **28 appears twice**, and
>    `mq 28`/`mq 38` sit in one sentence. The Stage-2 gate's `source_value` is **unique-value-or-raise**
>    (`parser.py:312-333`): a naive `mq\s*(\d+)` anchor matches **both 28 and 38** → it RAISES (verified).
>    The fix is **person-count-qualified, disjoint anchors**, each resolving to a unique value (verified —
>    see Task 1); the shared `28` is fine because uniqueness is **per-anchor**, not global.
> 2. **`se per due persone` wraps a line break.** In the raw `.md` the 2p clause is split `…mq 38 se per`
>    (`:27`) / `due persone.»` (`:28`); it only becomes a contiguous phrase **after `_demark`**
>    (`parser.py:305-309`). The monostanza anchors MUST run over `_demark(crosscheck_corpus(...))`, exactly
>    as `source_value` already does — verified.
> 3. **Monostanza must not erase the frozen verdicts.** Monostanza applicability is **unit-level** (a
>    monolocale dwelling-unit + person count), **not** per-`IfcSpace` occupancy (baseline §6). If it were
>    folded into the per-space `SpaceFinding.compliant` keystone as an always-`None` required check, every
>    habitable space would flip to `undetermined` and the **FZK 5 / Institute 2 violations would vanish**.
>    So monostanza is evaluated **unit-level, in a separate report channel**, and the per-space
>    `compliant` property (`checker.py:217-228`, the Stage-3 keystone) is **UNTOUCHED**.
>
> **Design choice (recorded, defensible, minimal — the alternative is rejected):** monostanza is a
> **separate verified gate primitive** (`verify_monostanza_against_text` + its own `_MONOSTANZA_*`
> anchors/discriminators, enforced by `test_gate.py`), **not** folded into `THRESHOLD_KEYS`
> (`parser.py:222-227`). Folding it in would (a) make `parse_rule`'s `assert set(thr)==set(THRESHOLD_KEYS)`
> (`parser.py:544`) require the live LLM to emit monostanza on every run or RAISE, and (b) force the
> compiled JSON to carry 8 thresholds the checker would then have to consume — a far larger,
> verdict-risky blast radius. The separate-primitive design mirrors exactly how Part 3's selection gate
> was added (`verify_accessory_selection_against_text`, `parser.py:463`), and keeps the existing
> 4-threshold mandatory gate + the live pipeline **verdict-neutral by construction**.

> **Working directory.** Run everything from the repo root
> `C:/Users/matte/Desktop/Desktop OLD/AI/Università AI/courses/personal_project/industrial.review/acc-neurosymbolic-core`.
> If the session started elsewhere, `cd` there first. Paths below are relative to it; checker/parser/
> test commands run from `sandbox/`.

## BOOT (read first)
`sandbox/STAGE4_BASELINE.md` — esp. **§1** (rescope + decision 2 "force the abstraction to be real"),
**§2** anchor table (B/B′ monostanza `28/38` + Salva-Casa `20/28`; **C** montani 2,55 decoy-to-keep;
**C′** seismic name-only — 0 numeric hits), **§3** (the requirement model already admits a 5th metric
via the accessor; the monostanza metric is "added to the model in Part 4"), **§5** (the gate machinery +
the corpus exclusion: kept **1–57**, dropped **58→EOF**; the decoy block `parser.py:97-101`), **§6**
(**monostanza is UNIT-level, UNDETERMINED on all 3 fixtures** — no occupant count, no monolocale flag;
Duplex carries a dwelling-unit zone NAME only — see Task 2's exact handling), **§8** (production-safety: missing data ⇒ undetermined, **never a pass**; `SpaceFinding`/
`compliant` stay untouched); `docs/decisions.md` (ADR-001…004; **Part 4 appends ADR-005**); `ROADMAP.md`
(Stage 4 `:117-127` + Iteration Log — **Part 4 renarrows it**); `CLAUDE.md`.
Code you edit/read: `sandbox/parser.py` (the gate — `SYSTEM_PROMPT` decoy block `:97-101`, `DEFAULT_THRESHOLDS`
`:126-131`, `build_rule` `:162-196`, `compile_thresholds` `:199-213`, `THRESHOLD_KEYS` `:222-227`,
`_SOURCE_ANCHORS` `:279-284`, `_METRIC_DISCRIMINATORS` `:291-302`, `_norm_value` `:236-246`, `_demark`
`:305-309`, `source_value` unique-or-raise `:312-333`, `_unit_ok` `:336-340`, `verify_rule_against_text`
`:343-397`, the Part-3 `verify_accessory_selection_against_text` `:463-489`, `parse_rule` `:530-547`);
`sandbox/checker.py` (`Requirement` `:87-100`, `_dm1975_requirements` `:103-118`, `Thresholds.resolve`
`:137-151`, `to_legacy_dict` `:170-179`, `from_rules_json` `:181-199`, `SpaceFinding.compliant` keystone
`:217-228` **read-only/untouched**, `check_space` `:397-444`, `run` report dict `:462-472`);
`sandbox/rules/dm_1975_salva_casa.md` (the statute — monostanza baseline `:26-28`, Salva-Casa surfaces
`:37`, montani decoy `:15-17`, Art.1 `:8-10`); `sandbox/rules/compiled/dm_1975_salva_casa.json` (the
4-threshold block `:54-59` + **empty `selection: []` `:8`** Part 4 populates); `sandbox/tests/test_gate.py`
(27 cases), `sandbox/tests/test_requirement_model.py` (16 cases — **only the two `resolve("min_surface_monostanza_1p",
"monolocale")` calls at `:88` and `:101` flip when Part 4 adds the metric; re-point exactly those, leave
`:98`/`:99` untouched**).

## START CONTROLS (run first from `sandbox/` — if any is off, STOP: env/regression, not Stage 4)
- `python tests/test_gate.py` → **27/27**; `python tests/test_height_keys.py` → **9/9**;
  `python tests/test_geometry_fallback.py` → **12/12**; `python tests/test_requirement_model.py` →
  **16/16**; `python tests/test_applicability_table.py` → **18/18, 0 skipped**.
- `python checker.py data/AC20-FZK-Haus.ifc --json data/AC20-FZK-Haus_report.json` → **5**;
  `--salva-casa` → **1**.
- `python checker.py data/AC20-Institute-Var-2.ifc --json data/AC20-Institute-Var-2_report.json` →
  **2** (spaces **402/403**); `--salva-casa` → **2**.
- `python checker.py data/Duplex_A_20110907.ifc --json data/Duplex_A_20110907_report.json` →
  **0 / 21 undetermined** (both modes; exit ≠ 0 EXPECTED).
- `python probe_controls.py` → **FROZEN CONTROLS HELD**.
- If a `data/*.ifc` is missing (git-ignored), re-acquire per `stage32ndpart.md:22-27`.

## HARD RULES
- **Edit `sandbox/parser.py`, `sandbox/checker.py`, `sandbox/tests/test_gate.py`,
  `sandbox/tests/test_requirement_model.py`, `sandbox/rules/compiled/dm_1975_salva_casa.json`,
  `docs/decisions.md`, and `ROADMAP.md`.** Do **NOT** touch the law `.md` (the statute is the ground
  truth — never edit it to make a number bind), `applicability.json`, or `tests/equiv_oracle.json` (the
  committed pre-Part-2 golden; Part 4 moves no per-space verdict, so the 220-row equivalence stays the
  verdict-neutrality proof — re-capturing it would overwrite the "before", forbidden).
- **`SpaceFinding`/`compliant` (`checker.py:203-228`) is UNTOUCHED** (Stage-3 Part-3 keystone). Monostanza
  is **unit-level**, surfaced in a **separate** report channel, and **never** folded into the per-space
  `compliant`, the `violations` count, the `spaces_undetermined` count, or the frozen GlobalId sets.
- **Verify against the STATUTE, never the answer key, never a default.** The monostanza gate MUST run
  over `_demark(crosscheck_corpus(law_text))` (answer-key `:58→EOF` excluded, line break collapsed) and
  mirror `source_value`'s **unique-value-or-raise** (`parser.py:328-332`): an absent/deleted number RAISES
  (no backfill); a duplicate/ambiguous anchor RAISES; a fabricated/decoy surface RAISES.
- **Decoys stay rejected.** Un-suppressing monostanza in `SYSTEM_PROMPT` (`parser.py:101`) is a **prompt
  edit only** (the live LLM path; not exercised by any control). **montani 2,55** (`:98-99`) and
  **seismic / daylight-%** (`:100`) remain decoys; the gate must still REJECT montani 2,55 as a habitable
  height AND reject any montani/seismic value offered as a monostanza surface (regression-tested).
- **The existing 4-threshold gate is UNCHANGED.** Do NOT add monostanza to `THRESHOLD_KEYS`
  (`:222-227`), do NOT alter `verify_rule_against_text` (`:343-397`) or the `parse_rule` assert (`:544`).
  Monostanza is a **separate** primitive. The four frozen numbers (`2.70/2.40/2.40/0.125`) resolve
  byte-identically; the report `thresholds` block stays byte-identical.
- **Fix the code, not the harness.** Never weaken a check or a control to make a number pass.
- **One task at a time, in order (lowest→highest risk).** After EACH code task run the full REGRESSION
  BLOCK. **If any frozen control moves, revert that task and stop.** Observation separate from
  interpretation; cite `file:line` in notes for each change.

## REGRESSION BLOCK (run after EVERY code task — from `sandbox/`)
```
python tests/test_gate.py                                                                 # 27 -> N (grows, all green)
python tests/test_height_keys.py                                                          # 9/9
python tests/test_geometry_fallback.py                                                    # 12/12
python tests/test_requirement_model.py                                                    # 16 -> M (grows, all green)
python tests/test_applicability_table.py                                                  # 18/18, 0 skipped (220-row equivalence, 0-drift)
python checker.py data/AC20-FZK-Haus.ifc            --json data/AC20-FZK-Haus_report.json            # viol 5
python checker.py data/AC20-FZK-Haus.ifc --salva-casa --json data/AC20-FZK-Haus_report_sc.json       # viol 1
python checker.py data/AC20-Institute-Var-2.ifc     --json data/AC20-Institute-Var-2_report.json     # viol 2
python checker.py data/AC20-Institute-Var-2.ifc --salva-casa --json data/AC20-Institute-Var-2_report_sc.json # viol 2
python checker.py data/Duplex_A_20110907.ifc        --json data/Duplex_A_20110907_report.json        # 0 / 21 undet
python checker.py data/Duplex_A_20110907.ifc --salva-casa --json data/Duplex_A_20110907_report_sc.json # 0 / 21 undet
python probe_controls.py                                                                   # FROZEN CONTROLS HELD
```
**Global invariant (every task):** `test_gate` and `test_requirement_model` only **grow** (all green);
every other number is **byte-identical** to START CONTROLS — violations `FZK 5→1`, `Institute 2→2`
(GlobalIds `0jbV$RErb7o9P7rp7ALEd$`=402, `3txvJd9V1BPhyU$48F$mnF`=403), `Duplex 0 / 21 undetermined`
both modes; `spaces_undetermined` = `{FZK:0, Institute:0, Duplex:21}`; `test_applicability_table`
220-row equivalence 0-drift; report `thresholds` block byte-identical. **Part 4 adds a 2nd rule's
verification + an honest undetermined channel, not a single per-space verdict.** Any movement = revert.

---

## TASK 1 — Gate: verify the monostanza numbers against the statute + un-suppress the decoy  *(parser.py + test_gate.py; verdict-neutral by construction)*
- **Target:** `parser.py` (alongside the Part-3 selection gate `:463-489`); `SYSTEM_PROMPT` decoy block
  `:97-101`; `tests/test_gate.py`.
- **Gap:** the gate verifies the 4 height/aero numbers and (Part 3) the accessory selection, but **not**
  the monostanza surfaces. They live in the statute prose (`:26-28`, `:37`) and even in the compiled
  exception `text` (`compiled/dm_1975_salva_casa.json:50`) but are **unverified** and prompt-**suppressed**
  as a decoy (`parser.py:101`).
- **Change (single concern — add ONE gate primitive + its anchor data, mirror the numeric gate):**
  - `_MONOSTANZA_KEYS` = `("min_surface_monostanza_1p", "min_surface_monostanza_2p",
    "min_surface_monostanza_sc_1p", "min_surface_monostanza_sc_2p")`.
  - `_MONOSTANZA_ANCHORS` — the **person-count-qualified, disjoint** anchors (each verified to resolve to a
    UNIQUE value over `_demark(crosscheck_corpus(LAW))`; a naive `mq\s*(\d+)` is ambiguous→raise and is the
    failure mode this guards):
    ```
    min_surface_monostanza_1p:    r"per una persona[^0-9]*?mq\s*(\d+)\b(?!\s+se per due)"  # -> 28
    min_surface_monostanza_2p:    r"mq\s*(\d+)\s+se per due persone"        # -> 38
    min_surface_monostanza_sc_1p: r"(\d+)\s*m²\s*\(\s*1 person\s*\)"        # -> 20  (m² = U+00B2 literal)
    min_surface_monostanza_sc_2p: r"(\d+)\s*m²\s*\(\s*2 persons\s*\)"       # -> 28
    ```
    **All four MUST be fail-closed (deleting the source value yields `[]`→RAISE, never a slide to a
    neighbour).** `_2p`/`_sc_1p`/`_sc_2p` are right-anchored (the `se per due persone` / `(1 person)` /
    `(2 persons)` trailer pins the number). `_1p` is the trap: the naive `per una persona.*?mq\s*(\d+)`
    is **NOT** fail-closed — deleting `mq 28` lets the gap **slide forward and capture 38** (verified),
    exactly the laundering the gate forbids. The form above blocks the slide with `\b(?!\s+se per due)`
    (verified: intact→`['28']`, `mq 28` deleted→`[]`). Use **`re.I` only** — `re.S` is **inert** here (the
    de-marked corpus has 0 newlines; the `se per due persone` break is already collapsed by `_demark`).
    All run over `_demark(crosscheck_corpus(...))` — NOT the raw `.md` (baseline-trap-2). The `m²` literal
    round-trips in a UTF-8 raw string like Part 3's `»`; verify the file reads back U+00B2.
  - `_MONOSTANZA_DISCRIMINATORS` — bilingual tokens each clause MUST carry. The only ambiguity is the
    shared value `28` (1p baseline vs Salva-Casa 2p); those two keys are kept **disjoint** by Italian-vs-
    English tokens — `_1p`→(`una persona`,`mq`) vs `_sc_2p`→(`2 persons`,`m²`,`surface`) — while the
    `28`/`38` pair is separated by value-equality first. (`_2p`→(`due persone`,`mq`); `_sc_1p`→(`1 person`,
    `m²`,`surface`).) Do **NOT** put `monostanza` in `_1p`'s set — it appears in BOTH the baseline (`:26-27`)
    and the Salva-Casa (`:37`) spans, so it carries no disambiguating power and only risks an order-dependent
    false-REJECT (never a false-pass — value-equality + the used-set guarantee that direction). Breadth is
    safe: a token binds only when the clause value already equals the source value.
  - `verify_monostanza_against_text(rule_or_clauses, law_text) -> dict` — for each `_MONOSTANZA_KEYS` key,
    re-derive the source value via its anchor with **unique-value-or-raise** (reuse the `source_value`
    discipline: `re.findall` over the de-marked, answer-key-excluded corpus; ≥2 distinct → RAISE; none →
    RAISE), then bind a DISTINCT clause whose `_norm_value` equals it, with operator `>=`, a surface unit
    (`m²`/`mq`/`m2`) checked by a **NEW helper local to this primitive** — do **NOT** mutate the shared
    `_unit_ok` (`:336-340`), which the frozen numeric gate consumes (`:379`); ratio/metre units are
    rejected, and a metric discriminator. Any missing/partial/decoy/swapped/ambiguous ⇒ RAISE. Returns the 4 verified
    surfaces `{key: value}`. It does **NOT** touch `THRESHOLD_KEYS`, `verify_rule_against_text`, or
    `parse_rule` — it is a standalone primitive, exactly like `verify_accessory_selection_against_text`.
  - **Un-suppress the decoy (prompt edit):** in `SYSTEM_PROMPT` remove the monostanza-surface decoy. **Exact
    boundary** — the phrase straddles two concatenated string literals: `:100` ends `…daylight-factor
    percentages, and the ` and `:101` is `'alloggio monostanza' minimum SURFACES in m2/mq.\n`. Delete the
    `, and the ` connector at the end of `:100` **and** the whole `:101` decoy phrase, re-terminating so the
    decoy list reads `…seismic-zone heights, daylight-factor percentages.\n` (no orphan `and the`, no doubled
    period). Then add monostanza as an enumerated extraction target (a 5th item in the rule-4 list `:86-94`,
    citing its own verbatim spans, surfaces in m²/mq, person-count-tagged). **Keep** "comuni montani …
    reduced height (a DECOY …)" (`:97-99`) and "seismic-zone heights, daylight-factor percentages" (`:100`)
    as decoys. This edits the **live LLM instructions only** — no control exercises `SYSTEM_PROMPT`, so it is
    verdict-inert; its correctness is proven by the gate-level regression below.
- **Expected verdict delta:** **NONE.** `checker.py` untouched; `THRESHOLD_KEYS`/the numeric gate
  untouched; the live pipeline still resolves exactly the 4 thresholds (monostanza clauses, if the LLM now
  emits them, are extra clauses the 4-key loop ignores). The full REGRESSION BLOCK stays byte-identical.
- **Acceptance (add to `tests/test_gate.py`; run BEFORE trusting):**
  1. **Accept (anchored):** `verify_monostanza_against_text(<oracle monostanza clauses>, LAW)` returns
     `{_1p:28, _2p:38, _sc_1p:20, _sc_2p:28}`. Build the oracle clauses citing the real spans (`mq 28`,
     `mq 38`, `20 m² (1 person)`, `28 m² (2 persons)`), unit `m²`/`mq`, op `>=`.
  2. **Unique-or-raise proof:** assert `source_value`-style derivation of `_1p` over the corpus is the
     UNIQUE `28` and that a naive `mq\s*(\d+)` anchor would yield `{28,38}` (ambiguous) — i.e. the
     qualified anchor is load-bearing. (A direct re.findall assertion, like Part 3's enumeration test.)
  3. **Reject — fabricated surface:** a monostanza clause with a value absent from the statute (`30`)
     RAISES.
  4. **Reject — decoy-as-surface:** montani `2,55` or seismic offered as a monostanza surface RAISES
     (value not in `{28,38,20,28}` and/or wrong unit) — proves the decoys stay out of the 2nd rule.
  5. **Reject — deleted source, BOTH person counts (non-vacuous — pins the `_1p` slide fix):**
     (a) on a LAW copy with `mq 28`→`mq XX`, assert the gate RAISES on `_1p` **and** the derived source is
     not `38` (proves `_1p` is fail-closed, not sliding); (b) on a copy with the `mq 38 … due persone` span
     deleted, assert RAISES on `_2p`. A single generic "deleted source RAISES" passes **vacuously** via the
     already-safe `_2p` path — both halves are required. Also: the `38` value cited under a `_1p`
     discriminator RAISES (swap).
  6. **montani 2,55 STILL rejected as a habitable height** (regression): re-assert the existing
     `test_montani_decoy_value_rejected` / `test_decoy_span_rejected_even_with_right_number` semantics are
     untouched — the numeric gate is unchanged.
- **Invariant:** global invariant holds; the new primitive never returns a default; the 4 frozen numbers
  byte-identical; `THRESHOLD_KEYS` and `verify_rule_against_text` unchanged.

## TASK 2 — Model: add the monostanza metric + evaluate it UNIT-level, UNDETERMINED  *(checker.py + test_requirement_model.py; verdict-neutral)*
- **Target:** `checker.py` `_dm1975_requirements` (`:103-118`) / `Requirement` (`:87-100`); a new
  unit-level evaluation surfaced in `run`'s report (`:462-472`); `tests/test_requirement_model.py`.
- **Gap:** the model holds only the 3 DM-1975 records; `resolve("min_surface_monostanza_1p","monolocale")`
  currently RAISES (the §3 "5th-metric" fail-closed, pinned by `test_requirement_model.py:87-88`).
- **Change (single concern):**
  - Add the **four monostanza `Requirement` records** to `_dm1975_requirements()` — metric
    `min_surface_monostanza_1p`/`_2p`, applicability `monolocale`, op `>=`, unit `m²`, value `28`/`38`, with
    `salva_casa_value` `20`/`28` (the Salva-Casa derogation as the `salva_casa_value` of the 1p/2p records,
    mirroring how the habitable height carries its Salva-Casa value `:112-113`). Now `resolve(...)` returns
    them; the legacy 4-accessor view + `to_legacy_dict` (`:170-179`) is UNCHANGED (it names only the 4
    height/aero metrics) ⇒ the report `thresholds` block is byte-identical.
  - Add a **unit-level** `monostanza_status(model)` (or a few lines in `run`): scan every `IfcSpace` pset /
    zone for **(a) a monolocale / single-room flag AND (b) an INTEGER occupant count**. Monostanza status
    is **`"undetermined"` UNLESS BOTH (a) and (b) are present** — a bare zone-NAME string is neither and
    keeps it undetermined. **Exact fixture facts (baseline §6, re-verified — do NOT assert "no hits on all
    3"):** FZK & Institute carry **no** occupancy data; **Duplex carries
    `PSet_Revit_Other.OccupancyZoneName` (values `'Unit A'`/`'Unit B'`/`'Roof'`)** — a multi-room
    *dwelling-unit name*, NOT a monolocale flag and NOT a count, so the Duplex hit is expected and must
    still yield **`undetermined`**
    (insufficient for monostanza). The unit-level result is **`{"applicable": null, "status":
    "undetermined", "reason": "no monolocale flag + occupant count (Duplex has a dwelling-unit NAME only)"}`**
    (fail-closed: a monolocale present *without* a count is also `undetermined`-blocking). Surface it as a
    **new top-level report field** `report["monostanza"]` in `run` (`:462-472`) — do **NOT** add it to
    `findings`, `violations`, or `spaces_undetermined`, and do **NOT** change `main`'s exit logic on its
    account.
  - **The per-space `SpaceFinding.compliant` keystone (`:217-228`) is byte-untouched.** check_space
    (`:397-444`) does NOT consult monostanza. This is what keeps FZK 5 / Institute 2 / Duplex 21
    byte-identical (baseline-trap-3).
  - **Re-point ONLY the two assertions that flip** in `test_requirement_model.py` (verified): the metric in
    `unknown_metric_raises` (`:87-88`) and `extras_not_resolvable_as_default` (`:100-101`) — both call
    `resolve("min_surface_monostanza_1p","monolocale")` expecting a RAISE, which no longer holds — to a
    **still-absent** metric (e.g. `min_surface_monostanza_3p` or `min_volume_min_m3`). **Leave
    `extras_preserved` (`:98`) and `extras_do_not_shift_legacy` (`:99`) UNCHANGED** — they test the
    extras-dict passthrough and the legacy block (metric-name-agnostic; they do NOT flip); touching them
    would delete real coverage.
- **Add tests** (`test_requirement_model.py`): `resolve("min_surface_monostanza_1p","monolocale")` == 28
  and `salva_casa=True` == 20; `_2p` == 38 / 28; the 4 legacy accessors + `to_legacy_dict` still
  byte-identical (monostanza did not perturb them); a still-absent metric still RAISES. (Optionally a tiny
  checker-level assertion that `report["monostanza"]["status"]=="undetermined"` on a fixture, guarded/
  skipped if the IFC is absent — mirror `test_applicability_table`'s skip pattern.)
- **Expected verdict delta:** **NONE.** Per-space projection (the 220-row oracle), violations,
  `spaces_undetermined`, GlobalId sets, and the report `thresholds` block all byte-identical; only a new
  top-level `monostanza` field is added.
- **Invariant (HARD):** if ANY per-space verdict, count, GlobalId set, or the 220-row equivalence moves,
  the monostanza channel leaked into the per-space path — **revert this task**.

## TASK 3 — Compile: wire the Part-3 selection gate into the compile path + populate the compiled `selection: []`  *(parser.py + the compiled JSON; verdict-neutral — the checker reads only `thresholds`)*
- **Target:** `parser.py` compile path (`build_rule` `:162-196` / `compile_thresholds` `:199-213` /
  `parse_rule` `:530-547`); `rules/compiled/dm_1975_salva_casa.json` `selection: []` (`:8`).
- **Gap (baseline §5):** the compiled rule's `selection: []` is empty, and the Part-3 selection gate is
  enforced only by `test_gate.py`, not invoked when a rule is compiled. The hand-off's wiring item.
- **Change (single concern, deterministic — NO Ollama dependency):**
  - **Add the gate-on-compile capability (code):** a small step that calls
    `verify_accessory_selection_against_text` over the **art1 tokens** (read from `rules/applicability.json`,
    the dependency-free way `test_gate.py` does — NOT `import checker`) and, on success, returns the
    verified accessory selection clauses (subject/text citing the Art.1 enumeration + anchored term); a
    fabricated token makes it RAISE (fail-closed). Expose it so `build_rule`/the offline path CAN emit a
    gate-verified `selection`. **Prove it with a NEW `test_gate.py` test** (real art1 tokens → non-empty
    verified selection; fabricated token → RAISE) — NOT by regenerating the committed file.
  - **Populate the on-disk compiled `selection: []` by HAND-EDIT only — do NOT regenerate it.** The
    committed artifact is **LLM-shaped** (`source: "llm"`, `rule.id: "A"`, `rule.source: "Italian
    habitability rule"`, `selection: []`); the offline/`build_rule` path emits a **structurally disjoint**
    rule (`id: "IT-DM-1975-HAB"`, a different `source`, and its own `vani abitabili` selection clause), and
    `build_rule(thr)` has **no `law_text` parameter** the gate needs — so it **cannot** reproduce this file
    as a selection-only diff. Therefore **hand-insert** the gate-verified accessory selection clauses into
    `selection: []`, leaving `id`/`source`/`thresholds` (`:54-59`) **byte-identical** (the `git diff` shows
    ONLY `selection` filled). Never **downgrade `source` from `"llm"`** or perturb `thresholds`.
- **Why verdict-neutral:** `checker.py`'s `from_rules_json` (`:181-199`) reads **only** the `thresholds`
  block; it never reads `selection`. And the START-CONTROL checker runs use **DM-1975 defaults** (no
  `--rules`), so the compiled JSON is not even on the verdict path. Populating `selection` changes
  provenance/completeness, **not** a verdict.
- **Invariant:** the compiled `thresholds` block + `source` byte-identical (`git diff` shows only
  `selection` added); the full REGRESSION BLOCK byte-identical.
- **If Task 3 proves entangled** (e.g. the only faithful regenerator is the live LLM and Ollama is
  unavailable): hand-populate `selection` from the verified gate output and record the limitation — do
  **NOT** downgrade `source` from `"llm"` or perturb `thresholds`. If still unsafe, **STOP and report**;
  Task 3 may be split to a Part-4b rather than risk the artifact (the core generalization proof is Tasks
  1–2 + 4).

## TASK 4 — ADR-005 + ROADMAP renarrow + Stage-4b split  *(docs only; no code, no verdict)*
- **`docs/decisions.md`:** append **ADR-005** (never edit a past ADR — CLAUDE.md): Stage 4 Parts 2–4
  delivered = generalized record-backed model + externalized gate-verified applicability/selection +
  the monostanza 2nd rule (gate-verified numbers `28/38/20/28`, decoy un-suppressed with montani/seismic
  still rejected, **undetermined/unit-level on all 3 fixtures**, verdict-neutral) — **without a graph**;
  the graph is **Stage 4b** (rdflib `==7.6.0` → Oxigraph swap; Neo4j rejected GPL-3.0, baseline §1
  decision 4), triggered when room-type hierarchies / multi-jurisdiction conflict / ~150 rules need it.
  Cite the verified controls. Status `ACCEPTED`, HEAD per CLAUDE.md.
- **`ROADMAP.md`:** the two-touch protocol (`:6-9`) — (1) renarrow the **Stage 4** block (`:117-127`) from
  "Graph anchoring" to "**generalize the model + gate-verified applicability/selection + 2nd rule
  (monostanza), no graph**", and add a **Stage 4b — Graph anchoring** entry (the deferred graph,
  store pre-decided); update the at-a-glance row (`:24`); (2) add **one** Iteration-Log line (`:133`,
  newest at top). Keep monostanza's honest status (undetermined; ✅-on-monostanza needs a monolocale
  fixture, mirroring the Stage-3 net-geometry caveat).
- **Invariant:** docs only; no code touched in this task; the REGRESSION BLOCK is still green (re-run once
  to confirm nothing drifted).

---

## DECIDE / HAND-OFF
- Part 4 proves the Stage-4 abstraction **admits a genuine 2nd rule at every layer**: monostanza is
  **gate-verified against the statute** (four numbers, unique-or-raise, decoys rejected), **held in the
  generalized requirement model**, and **honestly evaluated** (unit-level `undetermined` on all 3
  fixtures — never a fabricated pass), with the per-space verdicts and the four frozen numbers moving by
  **zero**. The accessory **selection** is now **gate-verified at compile time** (Task 3), not just
  test-time.
- **Honesty boundary (carry forward, do not over-claim):** (i) monostanza is `undetermined` because **no
  fixture carries a monolocale unit + person count** (baseline §6; Duplex's `OccupancyZoneName='Unit A/B'`
  is a dwelling-unit *name*, not a count) — its positive evaluation is **deferred to a monolocale fixture**,
  exactly as Stage-3's ✅-on-the-no-quantity-class was deferred to a net-geometry fixture (ADR-004).
  (ii) The monostanza **gate** is **test-enforced, not runtime-wired** (`verify_monostanza_against_text` is
  not called by `parse_rule`, by design — like Part 3's selection gate); and it verifies *clauses vs
  statute*, while the checker's hardcoded monostanza records in `_dm1975_requirements` are **not** gate-
  checked — a mis-transcribed value there would not be caught until a monolocale fixture exercises it. State
  this plainly; do not imply gate→model→verdict flow that does not exist. (iii) The cross-lingual accessory
  glossary remains **declared, unanchored debt** (Part 3 / baseline §7). The graph is **deferred to Stage
  4b** (never built here; its done-when is met only when an `IfcSpace`/room actually enters a graph store —
  baseline §1).
- **Stage 4b (`/stage4b...`) — authored later, NOT here:** the graph (rdflib `==7.6.0`, SPARQL 1.1,
  Oxigraph upgrade path) when room-type hierarchies / multi-jurisdiction conflict / ~150 rules need it; the
  room must enter the graph in that stage or the done-when is met in letter only.

## DONE-WHEN (Part 4)
1. `parser.py` Task 1: `verify_monostanza_against_text` + `_MONOSTANZA_*` anchors/discriminators (qualified,
   unique-or-raise over the de-marked answer-key-excluded corpus), the monostanza decoy un-suppressed while
   **montani 2,55 + seismic stay rejected**; `THRESHOLD_KEYS` / `verify_rule_against_text` / the `parse_rule`
   assert UNCHANGED. `checker.py` Task 2: 4 monostanza `Requirement` records + a **unit-level**
   `report["monostanza"]="undetermined"` channel; `SpaceFinding`/`compliant` byte-untouched; the stale
   `min_surface_monostanza_1p` absent-metric exemplars re-pointed. `parser.py`+compiled JSON Task 3:
   selection gate wired into the (Ollama-free) compile path + compiled `selection: []` populated,
   `thresholds`/`source` byte-identical. `docs/decisions.md`+`ROADMAP.md` Task 4: ADR-005 + the two-touch
   renarrow + Stage-4b. `applicability.json`, the law `.md`, and `tests/equiv_oracle.json` UNTOUCHED.
2. REGRESSION BLOCK green after every code task: `test_gate` **27→N**, `test_height_keys` 9/9,
   `test_geometry_fallback` 12/12, `test_requirement_model` **16→M**, `test_applicability_table` 18/18
   (220-row equivalence 0-drift), `probe_controls.py` = HELD; violations `FZK 5→1`, `Institute 2→2`
   (402/403), `Duplex 0/21` both modes; report `thresholds` block byte-identical — **all byte-identical**.
3. The monostanza gate is **non-vacuous**: it ACCEPTS the 4 statute surfaces (`28/38/20/28`, incl. the
   line-break-wrapped 2p span and the shared-28 disambiguation) and REJECTS a fabricated surface, a
   decoy-as-surface (montani/seismic), a swapped person-count, and a deleted source; the naive ambiguous
   anchor is shown to raise.
4. Monostanza is **`undetermined` on all 3 fixtures** (never `compliant=True`); the per-space verdicts and
   the four frozen numbers are byte-identical; the compiled `selection` is populated + gate-verified while
   `thresholds`/`source` are byte-identical.
5. **ADR-005 written + ROADMAP renarrowed** (Stage 4 = no-graph generalization + 2nd rule; Stage 4b =
   graph). `.idos/events.jsonl`: append a line **only** on a real STOP/GATE/DEFECT.
Then **STOP** and hand back the diff + the regression output, and confirm Stage 4b (the graph) is the
remaining scope (do not start it).
