# Stage 4 — Part 1 baseline + design freeze (READ-ONLY on production code)

> **Scope of this document.** Facts re-derived from the on-disk artifacts (every claim
> `file:line`-cited and byte-verified by the orchestrator, not trusted from any subagent), plus
> the **frozen design** for Stage 4 (rescoped: verified applicability + rule generalization;
> graph DEFERRED). No production code was changed in Part 1 — see §8 git proof. This is the
> input contract for `/stage42ndpart` (authored alongside this doc).
>
> Method: 3 parallel READ-ONLY probe tracks (`wf_1ba5348e-3fa`, treated as UNTRUSTED) were each
> re-verified against the files by the orchestrator; every START CONTROL was re-run from the
> artifacts. Two probe claims were extended/corrected on re-derivation (see §5, §7).

---

## 0. Repo-state note (surfaced, per CLAUDE.md "STOP on discrepancy")

Stage 2 + Stage 3 (Parts 2–3) changes are **in the working tree, uncommitted** — this is
*expected and recorded* (ADR-002/003/004 each state "HEAD `ffd9c1e` … changes in the working
tree; not yet committed"). The current working-tree state of `checker.py`/`parser.py`/the
compiled JSON **is** the production surface Stage 4 builds on. "No tracked source changed"
(DONE-WHEN #4) is therefore measured **relative to this working tree**: Part 1 adds only this
doc + the Part-2 command (+ git-ignored `probe_*.py` / `data/*_report.json`).

---

## 1. Rescope record (the frozen scope — not re-litigated here)

**Why the graph was deferred (adversarial finding, one paragraph).** ROADMAP Stage 4
(`ROADMAP.md:117-127`) is written as "Graph anchoring (scalability) … the checker no longer
queries a flat JSON but queries the Graph to discover which requirements apply to a specific
room." A 7-lens adversarial workflow (`wf_d142c4e3-ee2`, verdict **rescope**) found the minimal
graph migration is a premature abstraction: a vocab-only graph leaves `classify()`
(`checker.py:166-172`) running in Python *before* any query (the load-bearing room→occupancy
step — the Institute 402/403 canary — stays a Python conditional); the safety "proof" is
circular (the frozen controls are *outputs of* the current Python, so transcribing it into a
graph proves self-consistency, not correctness — the exact "echo the decomposition" move the
gate forbids one layer up, `parser.py:259-267`); and the `thresholdKey`/`getattr` indirection
is cosmetic because `Thresholds` has exactly 4 fixed fields (`checker.py:66-69`) verified by
exactly 4 `THRESHOLD_KEYS` (`parser.py:222-227`) — a real 2nd rule's key has no field, so
`getattr`/attribute access raises and the gate has no anchor. The *real* unsolved problems are a
**verification gap** (applicability/selection is unverified — the compiled rule's
`applicability`/`selection` arrays are empty, `dm_1975_salva_casa.json:7-8`, while the gate only
ever checks the 4 numbers) and **unproven generalization past one rule**.

**The 4 user decisions (frozen):**
1. **Table first, defer the graph** — externalize applicability/selection out of Python into a
   declarative, gate-verifiable data file; build the graph only when inference/scale needs it.
2. **Co-deliver the alloggio monostanza surface rule** as a real 2nd rule (≥28 m² 1p / ≥38 m² 2p;
   →20/28 under Salva Casa) — to force the abstraction to be real.
3. **Extend the verify-never-trust gate to applicability/selection**, to the extent the statute
   anchors it (Italian terms ↔ Art.1; German/KIT hints have no Italian-statute anchor → declared,
   test-pinned cross-lingual glossary = named debt, do not overclaim).
4. **Graph store, when later built (Stage 4b): rdflib (`==7.6.0` pinned, standard Store API +
   SPARQL 1.1 so Oxigraph is a one-line backend swap); Oxigraph the documented upgrade; Neo4j
   rejected (GPL-3.0 on a commercial asset).**

**Explicit split.** **Stage 4** = generalize the requirement model + externalize a
*gate-verified* applicability/selection table + add monostanza as a real 2nd rule, **no graph**.
**Stage 4b** = graph anchoring, store pre-decided (decision 4), when room-type hierarchies /
multi-jurisdiction conflict / ~150 rules actually need it; the IfcSpace/room must enter the graph
in that stage (else the done-when is met in letter only). **No ADR / ROADMAP flip in Part 1** — a
baseline is not a system change; the renarrow + ADR-005 land in Part 4 after green.

---

## 2. Anchor table — statute (byte-verified against `sandbox/rules/dm_1975_salva_casa.md`)

| # | Anchor | Line | Verbatim excerpt (on-disk bytes) | Role in Stage 4 |
|---|--------|------|----------------------------------|-----------------|
| A | **Selection — Art.1 accessory enumeration** | `:9-10` | `> in **m 2,70**, riducibile a **m 2,40** per i corridoi, i disimpegni in genere, i bagni,` / `> i gabinetti ed i ripostigli.»` | The **only** accessory terms gate-verifiable vs the statute. Italian tokens: **corridoi · disimpegni (in genere) · bagni · gabinetti · ripostigli**. |
| A'| RASE selection line | `:61` | `- **Selection:** habitable `IfcSpace` (exclude corridoi/bagni/ripostigli → accessory).` | In the answer-key block → **dropped** by the gate (§5). Anchor to the *prose* `:9-10`, not this. |
| B | **Monostanza baseline surfaces** | `:27` | `> minima, comprensiva dei servizi, non inferiore a **mq 28**, e non inferiore a **mq 38** se per` | 2nd-rule anchors: **≥28 m² (1p) / ≥38 m² (2p)** (paragraph `:26-28`). |
| B'| **Monostanza Salva-Casa derogation** | `:37` | `- *alloggio monostanza* minimum surface (incl. services) **20 m²** (1 person) / **28 m²** (2 persons).` | Derogated: **≥20 m² (1p) / ≥28 m² (2p)**. Lives in the DL 69/2024 section, not the DM-1975 paragraph. |
| B"| Comma 5-ter cumulative-AND regime | `:39-46` | `Comma **5-ter** … admissible **only if ALL of the following hold (cumulative / logical AND):**` + 3 numbered conditions (recupero/cambio d'uso; adattabilità DM 236/1989; concurrent ristrutturazione w/ alternative solutions) | Salva Casa is a **regime/scenario** (logical AND of conditions), **not** a per-field flag. |
| C | **DECOY-to-keep: comuni montani 2,55** | `:15-17` | `> *Separate provision:* for **comuni montani above 1000 m s.l.m.**, the habitable-room minimum` / `> may be reduced to **m 2,55** … Do not confuse this with the 2.40 m` / `> accessory-room value.` | Real number in the text, explicitly **"Separate provision"** — must STAY rejected by the gate after monostanza is un-suppressed (Part 4). |
| C'| **DECOY-to-keep: seismic-zone height** | *(none)* | whole-file grep `seismic`/`sismic`/`zona sismica` = **0 hits** | **No seismic number exists in the statute.** The seismic decoy is a **name-only defensive guard** in `parser.py:100` (no `_SOURCE_ANCHORS`/`_METRIC_DISCRIMINATORS`/`THRESHOLD_KEYS` entry). Must STAY a name-only reject. |

Verified numbers already gate-bound today (the 4 frozen thresholds): habitable **2.70** (`:8`,
"fissata in m 2,70"), accessory **2.40** (`:9`, "riducibile a m 2,40"), aero **1/8 = 0.125**
(`:22`, "1/8 della superficie del pavimento"), Salva-Casa height **2.40** (`:36`, "minimum
internal height **2,40 m**").

---

## 3. Generalization surface (what makes the model extensible — byte-identical frozen numbers)

**The rigidity, proven from disk:**
- `Thresholds` is a dataclass with **exactly 4 float fields** (`checker.py:66-69`).
- `Thresholds.from_rules_json` builds kwargs from a **hardcoded 4-key whitelist** (`checker.py:76-78`)
  → any 5th key in the rules JSON is **silently dropped** before `cls(**kw)`.
- `parser.compile_thresholds` seeds from the 4-key `DEFAULT_THRESHOLDS` (`parser.py:126-131`) and
  only ever writes those same 4 keys (`parser.py:199-213`) → a key like `min_surface_monostanza_1p`
  is **never produced**.
- `check_space` reads `thr.min_height_accessory_m` / `min_height_habitable_m` /
  `min_height_salva_casa_m` / `aero_illuminating_ratio` as **attributes** (`checker.py:195-197,
  222`) → `thr.<new_metric>` would raise `AttributeError`.

**Frozen change (to IMPLEMENT in Part 2 — verdict-neutral):** model requirements as a small
**verifiable list of records** `{rule_id, metric, subject/applicability, operator, value, unit,
salva_casa_value?}`, canonical. Keep a **backward-compatible accessor** so the existing four
names resolve **byte-identically**:

| legacy attribute | must resolve to | source |
|---|---|---|
| `min_height_habitable_m` | `2.70` | DM 1975 art.1 |
| `min_height_accessory_m` | `2.40` | DM 1975 art.1 |
| `min_height_salva_casa_m` | `2.40` | DPR 380 art.24 c.5-bis |
| `aero_illuminating_ratio` | `0.125` | DM 1975 art.5 |

Constraints (bake in): the 4 legacy reads return identical floats so `check_space`/report/print
are unchanged; a new metric (monostanza) resolves through the **same accessor** without a
dataclass edit and without the `AttributeError` the panel flagged; **fail-closed** — an unknown
key/metric **raises** (mirror the `parser.py` gate-raise, `parser.py:329-332,365-367`), never a
silent default. Part 2 keeps `check_space` consuming the 4 legacy values (resolved via the
accessor) so verdicts cannot move; the monostanza metric is *added to the model* in Part 4.

---

## 4. Frozen declarative applicability/selection table schema

A declarative data file (e.g. `sandbox/rules/applicability.toml`/`.json`) that `check_space`
reads, replacing the Python `classify()` hint tuples (`checker.py:45-59`) and the two `if`
branches (`checker.py:195-197` height bar; `:219-226` aero applicability). **No graph, no SPARQL.**

**Record shape (frozen):**
```
occupancy_class:                       # accessory | habitable    (unknown is NOT stored — §below)
  hints:        [substring, …]         # lowercased Name+LongName substrings (classify() semantics)
  statute_anchor: "DM1975-art1" | null # non-null ONLY for Italian terms enumerated in Art.1
  provenance:   "art1" | "cross-lingual-glossary"   # debt flag (§7)
  height_metric: "accessory" | "habitable"          # which height bar applies
  aero_applies:  true | false          # accessory → false (separate ventilation rules)
salva_casa_regime:                     # a SCENARIO, not a per-field flag (comma 5-ter is an AND)
  swaps: { non_accessory_height: min_height_salva_casa_m }
```

**Critical correctness semantics (from the adversarial panel — non-negotiable):**
- **`unknown` = strict complement** of (accessory ∪ habitable). It is **never a positive entry**,
  so a broadened hint cannot silently steal Institute **402/403** (`Dachboden-1/-2`) out of
  unknown→accessory and erase their aero check. (402/403 are `unknown` today by *no hint matching*
  "Dachboden" — §6.)
- **Accessory-first precedence** preserved structurally: test accessory, else habitable, else
  unknown — mirrors `classify()` order (`checker.py:168-172`).
- **Fail-closed**: a NOT-FOUND lookup → `undetermined` (`None`), **never** a pass.
- **Hint set must stay set-equal to the Python tuples including codepoints.** Load-bearing example
  (`checker.py:48`): the tuple holds BOTH `"kuche"` (ASCII) AND `"küche"` (`k\xfcche`, U+00FC);
  FZK space `6` `LongName='Küche'` (codepoints `0x4b 0xfc 0x63 0x68 0x65`) matches the **U+00FC**
  hint, not the ASCII one — drop the umlaut and FZK regresses. Enforce by a test that asserts
  byte-equality of the table hints vs the Python tuples, or generate one from the other so
  divergence is impossible by construction.

---

## 5. The gate surface + the verification gap (byte-verified vs `parser.py`)

- **The gap, on disk:** `verify_rule_against_text` builds its candidate `clauses` pool from
  `rule.requirement + rule.exception + rule.selection + rule.applicability` (`parser.py:353-354`)
  but its only loop is `for key in THRESHOLD_KEYS:` (`parser.py:359`) — the 4 numeric keys. A
  selection/applicability clause can therefore *only* serve as a candidate **binder for one of the
  4 numbers** (`parser.py:371-390`); **no branch ever inspects what a selection/applicability
  clause asserts.** The compiled rule confirms the consequence: `applicability: []`, `selection:
  []` (`dm_1975_salva_casa.json:7-8`). This is the verification gap Part 3 closes.
- **Corpus exclusion (re-derived, refines the command's ":58-66"):** `crosscheck_corpus`
  (`parser.py:259-267`) drops everything from the `^#{1,6}\s*Target rule` heading onward. Measured:
  full `.md` = 70 lines; **kept = lines 1–57; dropped = 58→EOF** (the decomposition `:58-66`, the
  blank `:67`, and Citations `:68-69`). Confirmed the kept corpus **contains** `mq 28` (monostanza
  prose, `:27`) and Art.1 (`:9-10`) but **not** `Target rule` / `Citations`. ⇒ Part 3's accessory
  selection and Part 4's monostanza numbers **are gate-anchorable** to the kept prose.
- **No-fallthrough guarantee (correction to the command's "assert source=='llm'"):** there is **no
  literal** `assert source=='llm'`. The assert is `assert set(thr) == set(THRESHOLD_KEYS)`
  (`parser.py:443`) — a coverage check that all 4 thresholds resolved; `"llm"` is set as the return
  tuple's 3rd element (`parser.py:444`). Fail-closed comes from `parse_with_ollama` raising on
  unreachable/HTTP/schema (`parser.py:441`) and `verify_rule_against_text` raising
  `ValidationGateError` on any discrepancy (`parser.py:442`), so the regex/defaults branch
  (`parser.py:445-447`) is unreachable when `offline=False`.
- **Decoy clauses (Part 4 must preserve while un-suppressing monostanza):** `SYSTEM_PROMPT`
  names the monostanza-surface decoy at `parser.py:101` ("'alloggio monostanza' minimum SURFACES
  in m2/mq"), the montani decoy at `:93-94` and `:97-99`, and seismic at `:100` (name-only, §2-C').
- **Machinery to extend:** `THRESHOLD_KEYS` (`:222-227`), `_SOURCE_ANCHORS` per-key regexes
  (`:279-284`), `_METRIC_DISCRIMINATORS` bilingual tokens (`:291-302`), `_norm_value` Italian-comma
  + fraction (`:236-246`), aero `1/8→0.125` via `int(a)/int(b)` (`:324-325`), and the
  **unique-value-or-reject** raise (`:328-332`).

---

## 6. Monostanza applicability dimension + START CONTROLS (re-run from artifacts)

**Monostanza applicability is UNIT-level, not per-IfcSpace occupancy** (monolocale = single-room
dwelling unit + person count). The current room-occupancy vocabulary cannot express it → the table
must admit **one applicability dimension that is not room-occupancy** (an `is-monolocale` / unit
attribute + person count).

**Recorded fact — UNDETERMINED on all 3 fixtures (verdict-neutral, honest):** an orchestrator
re-derivation over every `IfcSpace` pset found **no occupant count and no monolocale flag anywhere**:
- FZK & Institute IfcSpace psets: **zero** monolocale/occupancy/person hits; `IfcZone`/
  `IfcSpatialZone`/`IfcGroup` count = 0. FZK's many `Anzahl …` properties are ArchiCAD **geometric
  tallies** (`Anzahl aller Raumecken` corners, `Anzahl der Türen` doors, `Anzahl der Fenster`
  windows, `Anzahl der Wandelemente` walls) — **never** an occupant count; the `Personenanzahl`
  field exists in schema but is an **empty `IFCLABEL('')`** (so `get_psets` does not even return it).
- Duplex: `OccupancyNumber` attr = 0; the only "occupancy" hits are descriptive zone-name LABELS
  `PSet_Revit_Other.OccupancyZoneName = 'Unit A/B …'` — dwelling-unit **names**, not counts, and
  with **no** `IfcZone`/`IfcSpatialZone`/`IfcGroup` actually grouping spaces into units. A *Duplex*
  apartment is by definition multi-room (not a monolocale) regardless.
- `monolocale`/`monostanza` token frequency across all 3 files = **0**.

⇒ Monostanza will evaluate to **`undetermined`** on all 3 fixtures — the correct, honest,
**verdict-neutral** outcome. Its value here is *proving the model + gate generalize*, not changing
verdicts. (An optional future monolocale fixture would exercise it positively — recorded as
deferred.)

**START CONTROLS — all green, re-run from the artifacts (2026-06-19):**

| Suite / fixture | Result | Exit |
|---|---|---|
| `tests/test_gate.py` | **19/19** | 0 |
| `tests/test_height_keys.py` | **9/9** | 0 |
| `tests/test_geometry_fallback.py` | **12/12** (0 skipped) | 0 |
| FZK baseline | IFC4, 7 IfcSpace, **5 violations**, 0 undet | 1 |
| FZK `--salva-casa` | **1 violation**, 0 undet | 1 |
| Institute baseline | IFC4, 82 IfcSpace, **2 violations**, 0 undet | 1 |
| Institute `--salva-casa` | **2 violations**, 0 undet | 1 |
| Duplex baseline | IFC2X3, 21 IfcSpace, **0 viol / 21 undetermined** | 1 |
| Duplex `--salva-casa` | **0 viol / 21 undetermined** | 1 |

**FROZEN GlobalId acceptance anchors (identical to Stage 3 — `probe_controls.py` = "HELD"):**
- **FZK baseline (5):** `0Lt8gR_E9ESeGH5uY_g9e9`, `17JZcMFrf5tOftUTidA0d3`, `2RSCzLOBz4FAK$_wE8VckM`,
  `2dQFggKBb1fOc1CqZDIDlx`, `347jFE2yX7IhCEIALmupEH`
- **FZK salva-casa (1):** `2dQFggKBb1fOc1CqZDIDlx` (the residual fails on **aero**, not height)
- **Institute baseline & salva-casa (2, identical both modes):** `0jbV$RErb7o9P7rp7ALEd$`
  (**Name 402 = Dachboden-1**), `3txvJd9V1BPhyU$48F$mnF` (**Name 403 = Dachboden-2**). Both
  `occupancy=unknown`, `h=2.7` → height passes the 2.70 bar in *both* modes; they fail the **aero**
  ratio, which is why salva-casa (a height derogation) leaves them 2→2.
- **Duplex baseline & salva-casa:** 0 violations / **21 undetermined** (no Qto height/area; the
  `compliant=None` keystone keeps it non-certifiable, exit ≠ 0).

**Distinct `{Name, LongName}→occupancy` corpus (the Part-2 equivalence oracle):** **110 distinct
rows** (no row recurs across fixtures — Names differ), partition **69 habitable / 33 accessory /
8 unknown**; per fixture: FZK **5h/2a**, Institute **55h/25a/2u** (the 2u = 402/403), Duplex
**9h/6a/6u** (6u = Foyer×2/Utility×2/Stair/Roof). Full dump regenerable via `probe_freeze_s4.py`.

---

## 7. Cross-lingual-glossary debt boundary (the honesty line — Part 3)

Art.1 (`:9-10`) enumerates the accessory rooms; the **complement** ("locali adibiti ad abitazione",
`:8`) is habitable. So the statute anchors the **accessory selection vocabulary only**, and only
its **Italian** tokens. Mapping the current `_ACCESSORY_HINTS` (`checker.py:55-59`):

| hint | anchors to Art.1? | note |
|---|---|---|
| `corrid`, `disimpegno`, `bagno`, `ripostiglio` | **YES** | literal Art.1 tokens (corridoi/disimpegni/bagni/ripostigli) — the gate can anchor these |
| (`gabinetti`) | partial | Art.1 lists *gabinetti* but the checker represents it via the synonyms `wc`/`toilet` — the literal token is absent from the hints |
| `wc`, `toilet`, `bath`, `closet`, `hall`, `ingresso`, `storage`, `lavanderia`, `laundry` | **NO** | English + non-enumerated Italian (ingresso/lavanderia are not in Art.1) |
| `flur`, `diele`, `bad`, `abstell`, `keller`, `treppe`, `gaste`, `gäste`, `speis`, `technik`, `hwr`, `garage` | **NO** | German/KIT (Stage 3 Part 2) — no Italian-statute anchor |
| ALL `_HABITABLE_HINTS` (`checker.py:45-54`) | **NO** | Art.1 does not enumerate habitable room types; habitable is the complement — every habitable hint is an unanchored heuristic |

**Bounded debt:** Part 3 may gate-verify the **Italian accessory tokens against Art.1**
(corrid/disimpegno/bagno/ripostiglio, + gabinetti via its synonym, declared). **Everything else —
all German hints, all English hints, the non-enumerated Italian hints, and the entire habitable
vocabulary — is a declared, test-pinned cross-lingual/heuristic glossary = named debt**, to be
logged (ideally later anchored to a bilingual authority or a verified IFC room vocabulary). **Do
NOT** present the A/S layer as fully gate-verified; the translation/heuristic layer is not.

---

## 8. Production-safety invariant (unchanged — must survive Stage 4)

Never silently mark an unmeasurable space compliant; missing data ⇒ `undetermined`, never a pass.
On disk: `SpaceFinding.compliant` (`checker.py:96-108`) returns `None` if any **applicable** check
is `None` (accessory needs `{height_ok}`; habitable/unknown need `{height_ok, aero_ok}`); `run()`
counts `spaces_undetermined` (`checker.py:245`) and `main()` exits non-zero on violations **or**
undetermined (`checker.py:298`). Stage 4 must preserve this: adding the monostanza metric must
**not** let a missing/unknown monostanza input flip anything to `compliant=True` — an inapplicable
or undetermined monostanza check is `None`/N-A, never a pass. `SpaceFinding`/`compliant` stay
untouched in Parts 2–3.

---

## 9. REFINE — completeness critic (resolved before authoring Part 2)

- **Anchor ambiguities — resolved, none carried forward.** (i) The command's answer-key range
  "`:58-66`" is the decomposition list; the gate actually drops **58→EOF** incl. Citations
  `:68-69` (re-derived, §5). (ii) Monostanza "≥28/≥38" tokens both sit on the single line `:27`
  (paragraph `:26-28`). (iii) "assert source=='llm'" is conceptual; the literal assert is
  `set(thr)==set(THRESHOLD_KEYS)` (§5). (iv) FZK `Personenanzahl` exists but is empty — re-verified,
  no occupant count anywhere (§6). No further read needed.
- **Part order — independent, sequenced lowest→highest risk:**
  - **P2** (generalize model + externalize table) — **verdict-neutral / lowest risk**: backward-
    compatible accessor + declarative table; controls must stay byte-identical.
  - **P3** (extend gate to applicability/selection) — **verification-only**: anchor Italian
    accessory vocab to Art.1, declare the cross-lingual glossary as debt; `test_gate` grows but
    stays green; **no verdict change**.
  - **P4** (monostanza 2nd rule + gate to its numbers) — **highest-risk generalization proof**:
    un-suppress the monostanza decoy while keeping montani/seismic rejected; monostanza
    `undetermined` on the 3 fixtures (not a pass); then ADR-005 + ROADMAP renarrow.
  - They are **independent in code** (P2 = model/table; P3 = gate A/S; P4 = a new rule + gate
    numbers) but **sequenced** so each runs against a green, controls-frozen base. **Parts 3 & 4
    are authored later from P2/P3 results — not pre-written blind.**
- **Debt boundary — bounded (§7):** exactly which hints can (4 Italian accessory tokens) and
  cannot (German + English + non-enumerated Italian + all habitable) anchor to Art.1 is enumerated.

---

## 10. Artifacts (Part 1)

- **This doc:** `sandbox/STAGE4_BASELINE.md`.
- **Authored:** `.claude/commands/stage42ndpart.md` (Part 2 from these findings).
- **Git-ignored diagnostics (regenerable):** `sandbox/probe_controls.py` (frozen-control check, =
  HELD), `sandbox/probe_freeze_s4.py` (corpus + monolocale re-derivation), `sandbox/probe_corpus.py`
  (probe scratch), `sandbox/data/*_report*.json` (6 reports).
- **No tracked source changed** (`checker.py`/`parser.py`/`*.md` statute/compiled JSON/`ROADMAP.md`
  untouched). No ADR, no ROADMAP flip, no `events.jsonl` line (no STOP/GATE/DEFECT — the repo-state
  note §0 is expected-and-recorded, not a defect).
