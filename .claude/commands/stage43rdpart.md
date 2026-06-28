# Stage 4 · Part 3 — Anchor the accessory selection to the statute (extend the verify-never-trust gate; VERDICT-NEUTRAL, parser+test only)

Repo: `acc-neurosymbolic-core` (Slice A). Parts 1–2 are done and green: the baseline + frozen
design is `sandbox/STAGE4_BASELINE.md`; Part 2 externalized the applicability/selection logic into
`sandbox/rules/applicability.json` and generalized the requirement model, with **zero verdict
movement** (220-row equivalence + frozen controls). This command **implements** the one piece Part 2
deliberately left as a *named gap*: the table's `art1`-provenance accessory tokens are currently
pinned only to a **Python constant** (`checker.py:342-346` pins the table's `art1` group set-equal to
`_ART1_ACCESSORY_TOKENS`, `checker.py:77`) — i.e. table ↔ Python self-consistency, **not** a statute
anchor. Part 3 extends the Stage-2 verify-never-trust gate to **selection/applicability** so those
tokens are provably bound to **DM-1975 Art.1** (`rules/dm_1975_salva_casa.md:8-10`), the cross-lingual
glossary is **declared + test-pinned as named debt** (never claimed statute-verified), and the gate
**grows but stays green**. **No new rule. No monostanza/numbers. No graph. No verdict change. No
checker.py edit.**

> **Why this, why now, why minimal.** Baseline §1 names the exact trap: transcribing the current
> Python's own outputs into a "verification" proves self-consistency, not correctness — "the exact
> 'echo the decomposition' move the gate forbids one layer up." Today the `art1` label in
> `applicability.json` is an **unverified assertion**: the Part-2 load guard only checks the table
> equals a Python tuple. The *real* unsolved problem baseline §5 names is the **verification gap** —
> `verify_rule_against_text` pools selection/applicability clauses (`parser.py:353-354`) but only ever
> loops `for key in THRESHOLD_KEYS` (`parser.py:359`); **no branch inspects what a selection clause
> asserts**, and the compiled rule shows the consequence: `applicability: []`, `selection: []`
> (`rules/compiled/dm_1975_salva_casa.json:7-8`). Part 3 closes *that* gap for the accessory tokens
> and nothing more. The numbers (monostanza `28/38/20/28`), the decoy un-suppression, and any
> production compile-time wiring are **Part 4 — do NOT attempt or pre-write them here.**

> **Working directory.** Run everything from the repo root
> `C:/Users/matte/Desktop/Desktop OLD/AI/Università AI/courses/personal_project/industrial.review/acc-neurosymbolic-core`.
> If the session started elsewhere, `cd` there first. Paths below are relative to it; checker/parser/
> test commands run from `sandbox/`.

## BOOT (read first)
`sandbox/STAGE4_BASELINE.md` — esp. **§1** (rescope + the circularity warning Part 3 must not commit),
**§2** anchor table (the Art.1 accessory tokens + the answer-key `:61` that must be dropped + the
montani/seismic decoys-to-keep), **§5** (the gate surface + verification gap + the corpus-exclusion
re-derivation: kept lines **1–57**, dropped **58→EOF**), **§7** (the cross-lingual debt boundary —
do not over-claim); `docs/decisions.md` (ADR-004 newest; **no ADR is written in Part 3**); `CLAUDE.md`;
`sandbox/parser.py` (the gate you extend — `verify_rule_against_text` `:343-397`, `crosscheck_corpus`
`:259-267`, `_SOURCE_ANCHORS` `:279-284`, `source_value` unique-or-raise `:312-333`,
`_METRIC_DISCRIMINATORS` `:291-302`, `_demark`/`_norm_text` `:305-309`/`:249-256`,
`ValidationGateError` `:232-233`); `sandbox/tests/test_gate.py` (the control you grow — 19 cases,
auto-collected by `_main()` `:233-244`, `_expect_reject` helper `:216-222`,
`test_answer_key_is_excluded_from_corpus` `:111-115` is the pattern to mirror);
`sandbox/rules/dm_1975_salva_casa.md` (the statute — Art.1 `:8-10`, answer-key Selection `:61`);
`sandbox/rules/applicability.json` (the `art1` vs `cross-lingual-glossary` hint groups + their
`statute_anchor`/`provenance`); `sandbox/checker.py` **read-only here** (`_ART1_ACCESSORY_TOKENS`
`:77`, `_ACCESSORY_HINTS` `:63`, the Part-2 art1 load-guard `:342-346`).

## START CONTROLS (run first from `sandbox/` — if any is off, STOP: env/regression, not Stage 4)
- `python tests/test_gate.py` → **19/19**; `python tests/test_height_keys.py` → **9/9**;
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
- **Edit `sandbox/parser.py` and `sandbox/tests/test_gate.py` ONLY.** Do **NOT** touch `checker.py`,
  `applicability.json`, the law `.md`, the compiled rule JSON, or `ROADMAP.md`. (Because `checker.py`
  and the table are untouched, **verdict-neutrality is structural** — there is no verdict path to
  move; you still re-run the full REGRESSION BLOCK as proof.)
- **Do NOT regenerate `tests/equiv_oracle.json`.** It is the committed pre-Part-2 golden; Part 3
  changes no verdict path, so the existing 220-row equivalence (`test_applicability_table.py`) **is**
  the verdict-neutrality proof. Re-capturing it would silently overwrite the "before" — forbidden.
- **Verify against the STATUTE, never the answer key.** The new gate MUST run over
  `crosscheck_corpus(law_text)` so the answer-key Selection line (`dm_1975_salva_casa.md:61`,
  "exclude corridoi/bagni/ripostigli → accessory") is **excluded** — else the gate is satisfied by
  echoing the very decomposition it claims to verify (baseline §1). Anchor to the **prose** Art.1
  enumeration (`:8-10`), not to `:61` and not to `checker.py`'s tuples.
- **Fail-closed, mirroring the numeric gate** (`parser.py:328-332,365-368`): an `art1` token that does
  NOT anchor to the Art.1 enumeration **raises** `ValidationGateError`; a DELETED Art.1 enumeration
  **raises** (no backfill); a **duplicate-injected** enumeration (two non-identical captured term-sets
  under `re.findall` — see Task 1) **raises**. Never pass-by-default; an empty stem never anchors.
- **Do NOT over-claim the cross-lingual debt** (baseline §7). The English/German/KIT accessory
  synonyms (`statute_anchor: null`) are **declared named debt**: the gate records them as
  *unanchored*, pins them set-equal to the table's `cross-lingual-glossary` group, and **never**
  reports them as statute-verified. `gabinetti` is an Art.1 term carried only via the `wc`/`toilet`
  synonyms — it is allowed to have **no** `art1` token (the anchor direction is `art1 ⊆ enumeration`,
  not equality).
- **Minimal surface — single concern.** Add ONE gate function + its anchor data to `parser.py`, and
  the matching cases to `test_gate.py`. Do **NOT** add `_SELECTION_DISCRIMINATORS`, a person-count
  dimension, monostanza, compile-path wiring, or populate the compiled `selection: []` — all Part 4.
- **Fix the code, not the harness.** Never weaken a check or a control to make a number pass.
- **One task at a time, in order.** After EACH task run the full REGRESSION BLOCK. If any control
  moves, revert that task and stop. **Observation separate from interpretation**; cite
  `parser.py:<line>` / `dm_1975_salva_casa.md:<line>` in notes for each change.

## REGRESSION BLOCK (run after EVERY task — from `sandbox/`)
```
python tests/test_gate.py                                                                 # 19 -> N (grows, all green)
python tests/test_height_keys.py                                                          # 9/9
python tests/test_geometry_fallback.py                                                    # 12/12
python tests/test_requirement_model.py                                                    # 16/16
python tests/test_applicability_table.py                                                  # 18/18, 0 skipped (220-row equivalence)
python checker.py data/AC20-FZK-Haus.ifc            --json data/AC20-FZK-Haus_report.json            # viol 5
python checker.py data/AC20-FZK-Haus.ifc --salva-casa --json data/AC20-FZK-Haus_report_sc.json       # viol 1
python checker.py data/AC20-Institute-Var-2.ifc     --json data/AC20-Institute-Var-2_report.json     # viol 2
python checker.py data/AC20-Institute-Var-2.ifc --salva-casa --json data/AC20-Institute-Var-2_report_sc.json # viol 2
python checker.py data/Duplex_A_20110907.ifc        --json data/Duplex_A_20110907_report.json        # 0 / 21 undet
python checker.py data/Duplex_A_20110907.ifc --salva-casa --json data/Duplex_A_20110907_report_sc.json # 0 / 21 undet
python probe_controls.py                                                                   # FROZEN CONTROLS HELD
```
**Global invariant (every task):** the four verdict suites + checker counts are **byte-identical** to
START CONTROLS (`test_gate` only *grows*; every other number is frozen): violations `FZK 5→1`,
`Institute 2→2` (GlobalIds `0jbV$RErb7o9P7rp7ALEd$`=402, `3txvJd9V1BPhyU$48F$mnF`=403),
`Duplex 0 / 21 undetermined` both modes; `test_applicability_table` 220-row equivalence still 0-drift.
**Part 3 adds verification, not a verdict** — any movement of a non-gate number means revert.

---

## TASK 1 — Add the statute-anchoring selection gate to `parser.py`  *(verification primitive)*
- **Target:** the gate module `parser.py` (alongside `verify_rule_against_text` `:343-397`). Re-use
  `crosscheck_corpus` (`:259-267`), `_demark` (`:305-309`), the unique-value-or-reject discipline
  (`source_value` `:312-333`), and `ValidationGateError` (`:232-233`).
- **Gap (baseline §5):** the gate has no branch that inspects a selection/applicability assertion;
  the `art1` provenance label in `applicability.json` is bound only to a Python tuple
  (`checker.py:342-346`), never to the statute. So a fabricated accessory token tagged `art1` would
  pass today.
- **Change (single concern):** add **one** function and its anchor datum:
  - `_ACCESSORY_SELECTION_ANCHOR` — a regex over the **de-marked, answer-key-excluded** corpus that
    captures the Art.1 reduced-height accessory enumeration **from the prose**. The enumeration sentence
    is `dm_1975_salva_casa.md:8-10`; the capturable list is on `:9-10` (the span after
    `riducibile a m 2,40 per i …`: `i corridoi, i disimpegni in genere, i bagni, i gabinetti ed i
    ripostigli`). Anchor on that prose phrase, **not** on `:61`.
    - **Tokenize deterministically, then PIN (load-bearing — do not hand-wave it):** lowercase the
      captured span, split on non-letters, and **drop the Italian articles/conjunctions** (`i`, `in`,
      `genere`, `ed`, and any token whose stem-length `< 3`). Assert the surviving set is **exactly**
      `{corridoi, disimpegni, bagni, gabinetti, ripostigli}`; if it differs, **RAISE** (the statute
      drifted from the expected enumeration). Pinning this literal 5-set is what stops the article `i`
      — whose vowel-stem is the **empty string**, a prefix of everything — from silently making the
      gate vacuous (the naive comma-split failure mode).
    - **Unique-or-raise (mirror `source_value` `:328-332`):** locate the span with `re.findall` (**not**
      `re.search`); if it yields **two or more non-identical captured term-sets** (a duplicate/shadow
      injection) **RAISE**; if it yields **none** **RAISE** (absent). Same decoy-shadowing defense the
      numeric gate already carries.
  - `verify_accessory_selection_against_text(art1_tokens, law_text, *, debt_tokens=()) -> dict` —
    takes the tokens **as arguments**; it does **NOT** `import checker` (there is no Python import
    *cycle* — `checker.py` does not import `parser` — the reasons are (a) keep `parser.py`, the neuro
    layer, independent of the symbolic `checker.py`, and (b) `checker.py`'s module-top
    `import ifcopenshell` `sys.exit`s when the wheel is absent, `checker.py:27-37`; importing it would
    couple this gate to that dependency). It:
    1. runs `crosscheck_corpus` → re-derives + pins the enumerated 5-set via the anchor (RAISE if
       absent / drifted / duplicate-injected);
    2. anchors **every** `art1_token` to the enumeration by **stem equality after singular/plural
       normalization**: lowercase, strip a trailing Italian inflection vowel run `[aeiou]+` from BOTH
       the token and each enumerated term, and require the two stems to be **equal** (so `corrid`≡
       `corrid`(oi), `disimpegno`→`disimpegn`≡`disimpegn`(i), `bagno`→`bagn`≡`bagn`(i), `ripostiglio`→
       `ripostigl`≡`ripostigl`(i) all anchor across the singular/plural drift). **Equality, not
       prefix** — a prefix rule false-anchors BOTH a truncated token (`b`→`bagni`) AND a suffix-extended
       fabrication (`bagno_decoy`→`bagni`); equality rejects both. A token matching **no** enumerated
       stem RAISES `ValidationGateError` (NO-INVENT analog); the empty stem never anchors;
    3. records `debt_tokens` as **declared, unanchored** (does NOT statute-check them, does NOT claim
       them verified) and returns `{"anchored": {token: enumerated_term, …}, "debt": [tokens…],
       "enumeration": [the 5 terms]}`.
  - **Direction is subset, not equality:** `art1 ⊆ enumeration`. `gabinetti` — the one enumerated term
    with no `art1` token (`_ART1_ACCESSORY_TOKENS` has exactly 4 entries, `checker.py:77`) — is covered
    by the `wc`/`toilet` debt synonyms and is correctly left unmatched: honest, not a failure.
- **Expected verdict delta:** **NONE** (parser primitive; `checker.py` untouched; nothing in the
  verdict path changes). The full REGRESSION BLOCK stays byte-identical.
- **Acceptance (asserted by Task 2's tests):** the 4 `art1` tokens anchor (incl. the `disimpegno→
  disimpegni` stem case); a fabricated/non-Art.1 token raises; a **truncated/suffix-extended** token
  (`b`, `bagno_decoy`) raises (binds stem-equality); a deleted Art.1 line raises; a duplicate-injected
  enumeration raises.
- **Invariant:** global invariant holds; the new function never returns a default; cross-lingual
  tokens are returned under `debt`, never under `anchored`; the empty stem never anchors.

## TASK 2 — Grow the gate control in `test_gate.py` (19 → N, stays green)  *(non-vacuous proof)*
- **Target:** `tests/test_gate.py` (auto-collected `test_*` by `_main()` `:233-244`; `LAW` already read
  at `:25`). **Do NOT `import checker`** — that couples this deliberately IFC-free, parser-only control
  (docstring `:4`) to `checker.py`'s module-top `import ifcopenshell` + `sys.exit` (`checker.py:27-37`),
  turning the gate suite RED on any box without the wheel. Source the tokens the dependency-free way:
  read `rules/applicability.json` with stdlib `json` and pull the `art1` hint group and the
  `cross-lingual-glossary` group from it (this also keeps the test tracking the table, not a hand-copied
  literal).
- **Do NOT reuse `_expect_reject` (`:216-222`)** for the new cases — it asserts `key_substr in str(e)`
  with a numeric **threshold key**, which the selection gate's token/enumeration error never contains.
  Use a bare `try: …; raise AssertionError(...); except ValidationGateError: pass` (or add a small
  `_expect_gate_raise(callable)` helper). Mirror the *shape* of the existing reject tests, not the
  helper itself.
- **Change:** add these `test_*` cases (both directions: accept-faithful / reject-fabricated):
  1. **Accept (anchored):** `verify_accessory_selection_against_text(art1_group, LAW)` returns all 4
     under `anchored`, each mapped to its Art.1 term, and `"enumeration"` is the 5-term set. Assert the
     `disimpegno→disimpegni` pair specifically — it proves stem-equality survives singular/plural drift
     (a naive `token in prose` would false-reject it).
  2. **Reject — fabricated `art1` token:** a token absent from Art.1 (`"garage"`, `"cucina"`) tagged
     `art1` RAISES `ValidationGateError`.
  3. **Reject — truncated / suffix-extended token (binds stem-equality):** `"bag"` (truncation) and
     `"bagno_decoy"` (suffix extension) tagged `art1` each RAISE. This case is what actually proves the
     match is **equality, not prefix** — without it a looser implementation passes every other case.
  4. **Reject — deleted source:** in a copy of `LAW`, delete the prose enumeration (`:9-10`). It is a
     two-line blockquote with `**` emphasis, so replace the full spans `riducibile a **m 2,40** per i
     corridoi, i disimpegni in genere, i bagni,` and `i gabinetti ed i ripostigli` (belt-and-suspenders,
     like `test_deleted_source_rejected` `:104-108`), and **assert `"ripostigli"` is absent from the
     copy before invoking** so a missed replace cannot pass silently → gate RAISES.
  5. **Inherits the corpus exclusion** (NOT a fresh anti-circularity proof — that is `crosscheck_corpus`'s
     job, already covered by `test_answer_key_is_excluded_from_corpus` `:111-115`): assert the gate
     re-derives from `crosscheck_corpus(LAW)`, i.e. the corpus it runs over does **not** contain the
     `:61` `"exclude corridoi/bagni/ripostigli"` string. Do **not** fabricate a synthetic `:61`-style
     span carrying the `riducibile` lead-in — the real `:61` has no such lead-in, and inventing one
     re-tests an inherited, untouched property.
  6. **Cross-lingual = declared debt, pinned:** call with `debt_tokens` = the table's
     `cross-lingual-glossary` group (read in setup); assert the returned `debt` set equals it and that
     **none** of those tokens appears under `anchored` (over-claim guard, baseline §7). Moving a debt
     token into the `art1` argument RAISES (case-2 path).
  7. **Reject — duplicate / shadow-injected enumeration:** inject a second, divergent
     `riducibile a m 2,40 per i …` span into a `LAW` copy (mirror `test_shadow_montani_into_habitable_rejected`
     `:131-137`) and assert the gate RAISES (`re.findall` sees two non-identical term-sets).
  8. **Decoys stay out (string-level only):** a non-Art.1 surface/room string — `"montani"`,
     `"alloggio monostanza"`, `"seismic"` — tagged `art1` RAISES via the **same** non-enumerated-token
     path as case 2. The selection gate touches **no** `SYSTEM_PROMPT` / `_SOURCE_ANCHORS` /
     `THRESHOLD_KEYS`; `parser.py:97-101` is the numeric-decoy prompt block, cited here as **context
     only** — no monostanza number is touched.
- **Expected verdict delta:** **NONE.** `test_gate` grows from **19** to **N** (all green); every
  other suite + checker count is byte-identical.
- **Invariant (HARD):** if any non-gate control count or GlobalId set moves, or the 220-row equivalence
  drifts, revert. Ship only if every control is green AND the gate is proven non-vacuous: it accepts the
  4 anchored tokens (incl. the `disimpegno→disimpegni` stem-drift pair) and rejects a fabricated token,
  a truncated/suffix-extended token, a deleted source, and a duplicate-injected enumeration.

---

## DECIDE / HAND-OFF
- Part 3 delivers a **statute-anchored accessory selection**: the `art1` tokens are bound to DM-1975
  Art.1 prose (`:8-10`) by a **verified `parser.py` primitive enforced via `test_gate.py`** — the same
  verify-never-trust *machinery* that guards the numbers, but (honestly) **not yet wired into a
  runtime/compile path**: the numeric gate runs at `parse_rule:442`, whereas this one is exercised by
  the test control; runtime/compile wiring is Part 4. The answer-key `:61` is excluded (no circular
  self-proof), and the cross-lingual glossary is an **explicitly declared, test-pinned, unanchored
  debt** — honest, not over-claimed. **Verdict-neutral by construction** (`checker.py` untouched;
  220-row equivalence + frozen controls green).
- **Wiring decision (recorded, defensible, minimal):** the gate is a **`parser.py` primitive enforced
  by `test_gate.py`** — exactly how the Stage-2 numeric gate's correctness is guaranteed (there is no
  runtime call to `verify_rule_against_text` outside `parse_rule` + the test control). `applicability.json`
  is a static Part-2 artifact with no LLM-compile step, so a production compile-time invocation (and
  populating the compiled `selection: []`, `dm_1975_salva_casa.json:8`) is **deferred to Part 4**,
  where the compile path is touched anyway to add the monostanza rule. Keeping Part 3 to `parser.py` +
  `test_gate.py` is the smaller, verdict-safe surface.
- **Part 4 (`/stage44thpart`) — authored later, from Part 3's results (NOT pre-written):** add the
  monostanza 2nd rule end-to-end + extend the gate to its numbers (`28/38/20/28`), un-suppress the
  monostanza surface decoy (`parser.py:101`) while keeping **montani 2,55 and seismic decoys rejected**
  (regression), wire the selection gate into the compile path + populate the compiled `selection: []`,
  monostanza **`undetermined`** on all 3 fixtures (no monolocale/person-count data — baseline §6),
  never a pass; then ADR-005 + ROADMAP renarrow + the Stage-4b graph split.

## DONE-WHEN (Part 3)
1. `parser.py` edited for Task 1 (one anchor datum + `verify_accessory_selection_against_text`:
   pin-the-5-set tokenization, `re.findall` duplicate-or-raise, **stem-equality** anchoring
   `art1 ⊆ enumeration`, cross-lingual returned as declared debt, empty stem never anchors), a
   single-concern change citing `parser.py:<line>`; `checker.py`/`applicability.json`/law `.md`/
   compiled JSON/`ROADMAP.md` untouched; `tests/equiv_oracle.json` NOT regenerated.
2. `tests/test_gate.py` grown with the 8 case-groups above (accept-anchored incl. the stem-drift pair;
   reject-fabricated; reject-truncated/suffix-extended; reject-deleted; corpus-exclusion-inherited;
   debt-declared-and-pinned; reject-duplicate-injection; decoys-stay-out), sourcing tokens from
   `applicability.json` (no `import checker`) and using a `ValidationGateError`-only reject check.
3. REGRESSION BLOCK green after every task: `test_gate` **19→N** (all green), `test_height_keys` 9/9,
   `test_geometry_fallback` 12/12, `test_requirement_model` 16/16, `test_applicability_table` 18/18
   (220-row equivalence 0-drift), `probe_controls.py` = HELD; violations `FZK 5→1`,
   `Institute 2→2` (402/403), `Duplex 0/21` both modes — **byte-identical**.
4. The new gate is **non-vacuous**: it ACCEPTS the 4 `art1` tokens (incl. `disimpegno→disimpegni`) and
   REJECTS a fabricated token, a truncated/suffix-extended token, a deleted Art.1 source, and a
   duplicate-injected enumeration; the corpus it runs over excludes the answer-key `:61`; the
   cross-lingual debt is reported as `debt`, never `anchored`.
5. **No ROADMAP flip, no ADR** in Part 3 (verdict-neutral gate extension; the renarrow + ADR-005 land
   in Part 4). `.idos/events.jsonl`: append a line **only** on a real STOP/GATE/DEFECT.
Then **STOP** and hand back the diff, the regression output, and confirm Part 4 is ready to be
authored from these results (do not start Part 4).
