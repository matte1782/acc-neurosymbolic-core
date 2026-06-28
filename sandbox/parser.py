#!/usr/bin/env python3
"""Neuro layer — parse legal natural-language text into a structured RASE rule (JSON).

A local open LLM (via Ollama, OpenAI-style structured output) extracts the rule's
structure; the output is constrained by the JSON Schema derived from the pydantic
models below and re-validated. The LLM is treated as UNTRUSTED: after schema validation a
VALIDATION GATE (``verify_rule_against_text``) cross-checks every emitted threshold against
the source statute text, so the deterministic checker (`checker.py`) only ever consumes
rules whose numbers are provably bound to the law. On a non-offline run the gate (or an
unreachable LLM) RAISES — it never silently falls through to the regex/defaults. The
deterministic regex extractor survives ONLY behind the explicit --offline flag (Stage-1
wiring: editing the law .md changes the output at €0, no LLM).

    python parser.py rules/dm_1975_salva_casa.md          # Stage-2: local LLM + gate, source=llm
    python parser.py rules/dm_1975_salva_casa.md --offline # Stage-1: deterministic regex, no LLM

Output: JSON {rule, thresholds, source}. 'thresholds' is the flat contract checker.py reads.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from enum import Enum
from typing import List, Optional

try:
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover
    sys.exit("pydantic required: pip install pydantic")


class Operator(str, Enum):
    GE = ">="
    LE = "<="
    GT = ">"
    LT = "<"
    EQ = "=="


class Clause(BaseModel):
    """A single RASE operator extracted from the text."""

    kind: str = Field(description="requirement | applicability | selection | exception")
    subject: str = Field(description="entity the clause is about, e.g. 'habitable room'")
    metric: Optional[str] = Field(None, description="measured property, e.g. 'net height'")
    operator: Optional[Operator] = None
    value: Optional[float] = None
    unit: Optional[str] = Field(None, description="e.g. 'm', 'm2', 'ratio'")
    ifc_hint: Optional[str] = Field(None, description="suggested IFC target, e.g. IfcSpace.Height")
    text: str = Field(description="verbatim source span")


class Rule(BaseModel):
    """RASE-structured, machine-checkable rule (Requirement/Applicability/Selection/Exception)."""

    id: str
    source: str
    description: str
    ifc_target: List[str] = Field(default_factory=list)
    applicability: List[Clause] = Field(default_factory=list)
    selection: List[Clause] = Field(default_factory=list)
    requirement: List[Clause] = Field(default_factory=list)
    exception: List[Clause] = Field(default_factory=list)


RULE_JSON_SCHEMA = Rule.model_json_schema()

SYSTEM_PROMPT = (
    "You are a legal-to-logic extractor for building-code compliance. Decompose ONLY the "
    "regulation text the user provides into the RASE structure (Requirement, Applicability, "
    "Selection, Exception) and emit ONLY JSON matching the given schema.\n"
    "HARD RULES (a violation is a failure, not a style choice):\n"
    "1. Use ONLY numbers written verbatim in THIS text. Never invent, infer, recall from "
    "training, round, or carry over a value. If a threshold is not written, set that clause's "
    "`value` to null.\n"
    "2. EVERY clause that carries a numeric `value` MUST also set `operator` (a minimum is "
    "'>=') and `unit` ('m' for a height, 'ratio' for an area ratio). Write a fraction as its "
    "decimal (1/8 -> 0.125, 1/10 -> 0.1).\n"
    "3. For every numeric clause, copy into `text` the verbatim source span "
    "(character-for-character, including the number) that states it — never paraphrase, "
    "translate, or cite an article number, a date, or any summary/answer table.\n"
    "4. From THIS text extract exactly these numeric limits, each in its own clause citing "
    "its own verbatim span:\n"
    "   (a) habitable-room minimum internal height, in metres — a requirement;\n"
    "   (b) the reduced height for corridors / passages / bathrooms / store-rooms, in metres — "
    "a requirement;\n"
    "   (c) the openable window-area to floor-area ratio, as a decimal — a requirement;\n"
    "   (d) the existing-building exception: in the 'Salva Casa' section, find the bullet whose "
    "text begins with the words 'minimum internal height' — copy that bullet into `text` and "
    "put its value in metres into `value`. This is the ONLY exception. Do NOT use the 'comuni "
    "montani' line as the exception.\n"
    "   (e) the 'alloggio monostanza' minimum SURFACES, in m²/mq — these are REQUIREMENTS, never "
    "the exception: the DM-1975 baseline (one person; two persons) AND the 'Salva Casa' derogated "
    "values (one person; two persons), each in its OWN clause citing its OWN verbatim span and "
    "tagged with its person count.\n"
    "5. Put each in its OWN clause; never merge or swap (a), (b), (d). The exception (d) is a "
    "HEIGHT in metres taken from the 'Salva Casa' section, never a surface.\n"
    "6. Treat every OTHER number as a DECOY and do NOT emit it anywhere (not as a requirement, "
    "not as the exception). In particular the 'comuni montani … s.l.m.' reduced height (a "
    "mountain-municipality value in the DM 1975 section) is a DECOY and must NEVER be the "
    "exception. Other decoys: seismic-zone heights, daylight-factor percentages.\n"
    "\nWORKED EXAMPLE (a DIFFERENT, fictional regulation that mirrors the SHAPE — a montani "
    "decoy and an English exception bullet; copy the structure, NEVER these numbers). Input:\n"
    "\"La larghezza minima utile di un corridoio e' fissata in m 1,20, riducibile a m 0,95 per "
    "i locali tecnici. Per i comuni montani la larghezza puo' essere ridotta a m 1,05. La "
    "superficie aerante non potra' essere inferiore a 1/10 della superficie del vano.\n"
    "Esistente (recupero):\n- minimum clear width 0,80 m (derogating the 1,20 m baseline).\"\n"
    "Correct output — the 'comuni montani m 1,05' line is a DECOY and is NOT emitted; the "
    "exception is the English 'minimum clear width 0,80 m' bullet:\n"
    "{\"id\":\"EX\",\"source\":\"fictional\",\"description\":\"example\",\"requirement\":["
    "{\"kind\":\"requirement\",\"subject\":\"corridoio\",\"metric\":\"width\",\"operator\":"
    "\">=\",\"value\":1.20,\"unit\":\"m\",\"text\":\"larghezza minima utile di un corridoio e' "
    "fissata in m 1,20\"},"
    "{\"kind\":\"requirement\",\"subject\":\"locale tecnico\",\"metric\":\"width\",\"operator\""
    ":\">=\",\"value\":0.95,\"unit\":\"m\",\"text\":\"riducibile a m 0,95 per i locali "
    "tecnici\"},"
    "{\"kind\":\"requirement\",\"subject\":\"vano\",\"metric\":\"aerating area / floor area\","
    "\"operator\":\">=\",\"value\":0.1,\"unit\":\"ratio\",\"text\":\"1/10 della superficie del "
    "vano\"}],"
    "\"exception\":[{\"kind\":\"exception\",\"subject\":\"existing building\",\"metric\":"
    "\"width\",\"operator\":\">=\",\"value\":0.80,\"unit\":\"m\",\"text\":\"minimum clear width "
    "0,80 m (derogating the 1,20 m baseline)\"}]}"
)

# --- Thresholds: the flat checker-ready contract emitted alongside the RASE rule ------
DEFAULT_THRESHOLDS = {
    "min_height_habitable_m": 2.70,
    "min_height_accessory_m": 2.40,
    "min_height_salva_casa_m": 2.40,
    "aero_illuminating_ratio": 0.125,
}


def _num(s: str) -> float:
    """Parse an Italian-style number ('2,70') to float."""
    return float(s.strip().replace(",", "."))


def extract_thresholds_from_text(text: str) -> dict:
    """Deterministic (regex) extraction of the headline numbers from the law text.

    This is the low-code Stage-1 bridge: editing the prose in ``rules/*.md`` changes these
    values, so the verdict changes with no Python edit. Best-effort — any key not found
    falls back to DEFAULT_THRESHOLDS in the caller. (Stage 2 replaces this with the LLM.)
    """
    out: dict = {}
    m = re.search(r"altezza minima interna utile.*?m\s*\*{0,2}\s*(\d+[.,]\d+)", text, re.S | re.I)
    if m:
        out["min_height_habitable_m"] = _num(m.group(1))
    m = re.search(r"riducibile a[^\d]*(\d+[.,]\d+)", text, re.S | re.I)
    if m:
        out["min_height_accessory_m"] = _num(m.group(1))
    m = re.search(r"(\d+)\s*/\s*(\d+)\s*della superficie del pavimento", text, re.S | re.I)
    if m:
        out["aero_illuminating_ratio"] = int(m.group(1)) / int(m.group(2))
    m = re.search(r"minimum internal height\s*\*{0,2}\s*(\d+[.,]\d+)", text, re.S | re.I)
    if m:
        out["min_height_salva_casa_m"] = _num(m.group(1))
    return out


def build_rule(thr: dict) -> Rule:
    """Assemble a RASE Rule from a thresholds dict (offline / text-extraction path)."""
    return Rule(
        id="IT-DM-1975-HAB",
        source="DM Sanità 5 luglio 1975; DL 69/2024 conv. L 105/2024 (Salva Casa)",
        description="Habitability: minimum internal height and aero-illuminating ratio for dwellings.",
        ifc_target=["IfcSpace", "IfcWindow"],
        applicability=[
            Clause(kind="applicability", subject="locale di abitazione", metric="use",
                   text="locali adibiti ad abitazione"),
        ],
        selection=[
            Clause(kind="selection", subject="habitable room", ifc_hint="IfcSpace",
                   text="vani abitabili (escl. corridoi, bagni, ripostigli)"),
        ],
        requirement=[
            Clause(kind="requirement", subject="habitable room", metric="net height",
                   operator=Operator.GE, value=thr["min_height_habitable_m"], unit="m",
                   ifc_hint="Qto_SpaceBaseQuantities.Height", text="altezza minima interna utile"),
            Clause(kind="requirement", subject="accessory room", metric="net height",
                   operator=Operator.GE, value=thr["min_height_accessory_m"], unit="m",
                   ifc_hint="Qto_SpaceBaseQuantities.Height",
                   text="riducibile per corridoi, disimpegni, bagni, ripostigli"),
            Clause(kind="requirement", subject="window", metric="openable area / floor area",
                   operator=Operator.GE, value=thr["aero_illuminating_ratio"], unit="ratio",
                   ifc_hint="IfcWindow area / IfcSpace NetFloorArea",
                   text="superficie finestrata apribile >= 1/8 della superficie del pavimento"),
        ],
        exception=[
            Clause(kind="exception", subject="existing building (recupero)", metric="net height",
                   operator=Operator.GE, value=thr["min_height_salva_casa_m"], unit="m",
                   ifc_hint="Qto_SpaceBaseQuantities.Height",
                   text="Salva Casa (DPR 380/2001 art. 24 c. 5-bis/5-ter): asseverabile, edificio esistente"),
        ],
    )


def compile_thresholds(rule: Rule) -> dict:
    """Map a RASE Rule's clauses back to the flat checker contract (LLM path)."""
    thr = dict(DEFAULT_THRESHOLDS)
    for c in rule.requirement:
        if c.value is None:
            continue
        if c.metric == "net height":
            key = "min_height_accessory_m" if "accessory" in c.subject.lower() else "min_height_habitable_m"
            thr[key] = float(c.value)
        elif c.unit == "ratio" or "area" in (c.metric or ""):
            thr["aero_illuminating_ratio"] = float(c.value)
    for c in rule.exception:
        if c.metric == "net height" and c.value is not None:
            thr["min_height_salva_casa_m"] = float(c.value)
    return thr


# === VALIDATION GATE ===================================================================
# The LLM is UNTRUSTED. After schema validation, no threshold reaches the checker unless it
# is provably bound to the source statute text: present at its own metric anchor, equal to
# what the LLM emitted (normalized, tol 1e-9), with the right operator/unit, and cited from a
# clause carrying that metric's discriminator (so a swapped or decoy span is rejected).

THRESHOLD_KEYS = (
    "min_height_habitable_m",
    "min_height_accessory_m",
    "min_height_salva_casa_m",
    "aero_illuminating_ratio",
)

_EQ_TOL = 1e-9


class ValidationGateError(ValueError):
    """Raised when an LLM-emitted rule fails the numeric/provenance cross-check vs the text."""


def _norm_value(x) -> Optional[float]:
    """Normalize a clause value to float: Italian comma (2,70), fraction (1/8), trailing zeros."""
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace(",", ".")
    if "/" in s:
        a, b = s.split("/", 1)
        return float(a) / float(b)
    return float(s)


def _norm_text(s: str) -> str:
    """Lowercase, drop markdown emphasis/quote markers, unify decimal commas, collapse space.

    Used for substring/discriminator tests so a verbatim span survives '**2,40**' -> '2.40'.
    """
    s = (s or "").lower().replace("*", " ").replace(">", " ").replace("`", " ")
    s = re.sub(r"(\d),(\d)", r"\1.\2", s)         # 2,40 -> 2.40 (decimal comma only)
    return re.sub(r"\s+", " ", s).strip()


def crosscheck_corpus(law_text: str) -> str:
    """The cross-check source of truth: statute quote blocks ONLY.

    Everything from the '## Target rule (RASE decomposition)' heading onward — the answer-key
    table AND the trailing Citations (dates/article numbers) — is dropped, so the gate cannot
    be satisfied by the model echoing the decomposition we are trying to verify.
    """
    m = re.search(r"^#{1,6}\s*Target rule", law_text, re.I | re.M)
    return law_text[: m.start()] if m else law_text


# Deterministic, metric-anchored extraction of the value the SOURCE permits for each key.
# Each anchor pins the number to its OWN lead-in phrase ('fissata in m', 'riducibile a m',
# 'minimum internal height', '… della superficie del pavimento'), so: (a) the 'comuni montani
# 2,55' decoy never binds the habitable height; and (b) DELETING a number yields None (the
# anchor cannot slide onto a neighbouring value) — that is what makes NO-INVENT reject instead
# of laundering the accessory 2,40 in. Run over a de-marked corpus so '> ' / '**' don't split
# the phrase. source_value() requires the anchor to resolve to a UNIQUE value (see below): a
# decoy span injected with the same lead-in phrase makes the source ambiguous and is REJECTED,
# rather than the first match silently winning (the anchor-shadowing false-pass from the audit).
_SOURCE_ANCHORS = {
    "min_height_habitable_m": r"fissata\s+in\s+m\s*(\d+[.,]\d+)",
    "min_height_accessory_m": r"riducibile a\s*m\s*(\d+[.,]\d+)",
    "min_height_salva_casa_m": r"minimum internal height\s*(\d+[.,]\d+)",
    "aero_illuminating_ratio": r"(\d+)\s*/\s*(\d+)\s*della superficie del pavimento",
}

# Tokens (drawn from the source span itself, bilingual) that a clause MUST carry to bind a key.
# They are DISJOINT for the equal-valued accessory vs salva-casa heights, so a swap is caught
# even though both are 2.40 m. Breadth here only lets a clause bind when its value already equals
# the source value, so it cannot create a false-pass — it only prevents false-fails on faithful
# Italian/English citations (the over-strict rejections the audit found).
_METRIC_DISCRIMINATORS = {
    "min_height_habitable_m": ("interna utile", "net internal height", "internal height",
                               "adibiti ad abitazione", "abitazione", "habitable"),
    "min_height_accessory_m": ("riducibile", "corridoi", "disimpegni", "ripostigli", "gabinetti",
                               "bagni", "reducible", "corridors", "circulation", "bathrooms",
                               "wc", "store", "closet"),
    "min_height_salva_casa_m": ("minimum internal height", "derogating", "salva casa",
                                "recupero", "esistent", "5-bis", "5bis", "assever"),
    "aero_illuminating_ratio": ("della superficie del pavimento", "superficie del pavimento",
                                "finestrata", "1/8", "1 / 8", "floor area", "window", "openable",
                                "aeroilluminant"),
}


def _demark(s: str) -> str:
    """Strip markdown emphasis + blockquote markers and collapse whitespace, so tight phrase
    anchors survive the '> ' / '**' wrapping. Decimal commas are left intact for the anchors."""
    s = (s or "").replace("*", " ").replace(">", " ")
    return re.sub(r"\s+", " ", s).strip()


def source_value(corpus: str, key: str) -> Optional[float]:
    """Value the statute text permits for ``key``; None if its anchor is absent.

    Uses re.findall and requires the anchor to resolve to a UNIQUE value. If two or more DISTINCT
    values match the same anchor — e.g. a 'comuni montani' carve-out injected with the baseline's
    own lead-in phrase, or a competing aero fraction — the source is ambiguous and we RAISE rather
    than let the first match silently win. This closes the decoy-shadowing false-pass: the gate
    cannot be steered onto a decoy value by prepending a look-alike span.
    """
    found = re.findall(_SOURCE_ANCHORS[key], _demark(corpus), re.S | re.I)
    if not found:
        return None
    if key == "aero_illuminating_ratio":
        vals = {int(a) / int(b) for a, b in found}
    else:
        vals = {_norm_value(g) for g in found}
    if len(vals) > 1:
        raise ValidationGateError(
            f"{key}: ambiguous source — anchor matches multiple distinct values "
            f"{sorted(vals)} (possible decoy injection); refusing to pick one"
        )
    return next(iter(vals))


def _unit_ok(key: str, unit: Optional[str]) -> bool:
    u = (unit or "").strip().lower()
    if key == "aero_illuminating_ratio":
        return ("ratio" in u) or u in ("", "-", "frazione")
    return u in ("m", "metri", "metro", "meter", "meters")


def verify_rule_against_text(rule: Rule, law_text: str) -> dict:
    """VALIDATION GATE — verify, never trust. Return the 4 verified thresholds or RAISE.

    For each threshold the source value is re-derived deterministically from the statute corpus
    (answer key excluded). A clause binds the key only if it is a DISTINCT clause whose value
    equals that source value, with operator '>=' and the right unit, and whose ``text`` carries
    the metric's discriminator. Any missing/partial/mismatched/decoy/swapped value RAISES — no
    default is ever substituted.
    """
    corpus = crosscheck_corpus(law_text)
    clauses = [c for grp in (rule.requirement, rule.exception, rule.selection,
                             rule.applicability) for c in grp]
    verified: dict = {}
    errors: List[str] = []
    used: set = set()

    for key in THRESHOLD_KEYS:
        try:
            src = source_value(corpus, key)
        except ValidationGateError as exc:           # ambiguous source (decoy injection) -> reject
            errors.append(str(exc))
            continue
        if src is None:
            errors.append(f"{key}: absent from the source statute text (anchor unmatched) — "
                          f"refusing to backfill a default")
            continue
        discs = _METRIC_DISCRIMINATORS[key]
        match = None
        for c in clauses:
            if id(c) in used:
                continue
            val = _norm_value(c.value)
            if val is None or abs(val - src) > _EQ_TOL:
                continue                                   # number not bound to this metric
            if c.operator != Operator.GE:
                continue                                   # wrong operator for a minimum
            if not _unit_ok(key, c.unit):
                continue                                   # wrong unit
            if not any(tok in _norm_text(c.text) for tok in discs):
                continue                                   # cited span lacks this metric (swap/decoy)
            match = c
            break
        if match is None:
            errors.append(f"{key}: no clause faithfully cites source value {src} for this metric "
                          f"(empty/partial, wrong operator/unit, or swapped/decoy span)")
            continue
        used.add(id(match))
        verified[key] = src

    if errors:
        raise ValidationGateError(
            "LLM rule failed source cross-check (verify, never trust):\n  - "
            + "\n  - ".join(errors)
        )
    return verified


# === SELECTION/APPLICABILITY GATE (Stage 4 Part 3) =====================================
# Extends verify-never-trust from the four NUMBERS to the accessory SELECTION vocabulary. Until
# now the art1-provenance accessory tokens in rules/applicability.json are pinned only to a Python
# tuple (checker.py:342-346) — table<->Python self-consistency, NOT a statute anchor (the
# circularity trap, STAGE4_BASELINE §1). Here each art1 token is bound to the DM-1975 Art.1 PROSE
# enumeration (rules/dm_1975_salva_casa.md:8-10), the English/German/KIT synonyms are returned as
# declared, UNANCHORED debt (never claimed statute-verified, baseline §7), and the answer-key
# Selection line (:61) is excluded via crosscheck_corpus (no echo-the-decomposition). This is a
# parser-layer primitive enforced by tests/test_gate.py; runtime/compile wiring + populating the
# compiled selection:[] are Part 4. checker.py is untouched -> no verdict path moves.

# Prose anchor for the Art.1 reduced-height accessory enumeration: the span after
# 'riducibile a m 2,40 per …', captured up to the closing period/guillemet of the sentence.
_ACCESSORY_SELECTION_ANCHOR = r"riducibile\s+a\s+m\s*\d+[.,]\d+\s+per\s+(.+?)[.»]"
# Italian articles/conjunctions to drop from the captured list (the rest fall to the stem<3 rule).
_IT_SELECTION_STOPWORDS = frozenset({"i", "in", "genere", "ed"})
# The pinned 5-term enumeration the statute prose must yield (else it has drifted -> raise).
_ART1_ENUMERATION = frozenset({"corridoi", "disimpegni", "bagni", "gabinetti", "ripostigli"})


def _it_stem(token: str) -> str:
    """Collapse Italian singular/plural drift by stripping a trailing inflection-vowel run:
    corridoi->corrid, disimpegno->disimpegn, bagni->bagn, ripostiglio->ripostigl. The bare article
    'i' stems to '' — which (by the empty-stem guard in the gate) never anchors: the failure mode
    that would otherwise make a naive comma-split gate vacuous (an empty stem is a prefix of every
    token)."""
    return re.sub(r"[aeiou]+$", "", (token or "").lower())


def _derive_accessory_enumeration(law_text: str) -> "List[str]":
    """Re-derive + PIN the DM-1975 Art.1 accessory enumeration from the statute PROSE.

    Runs over crosscheck_corpus (answer-key :61 excluded — anti-circularity, baseline §1) and
    _demark (so '> '/'**' don't split the phrase). Tokenizes the captured list, drops articles/
    conjunctions and sub-stem (<3) tokens, then asserts the survivors are EXACTLY the expected
    5-set. Unique-or-raise, mirroring source_value (:312-333): findall (not search) must yield
    exactly one distinct term-set — RAISE on none (absent/deleted; no backfill) or two+
    non-identical (duplicate/shadow injection)."""
    corpus = crosscheck_corpus(law_text)
    spans = re.findall(_ACCESSORY_SELECTION_ANCHOR, _demark(corpus), re.S | re.I)
    termsets = set()
    for span in spans:
        toks = [t for t in re.split(r"[^a-zàèéìòù]+", span.lower()) if t]
        kept = frozenset(t for t in toks
                         if t not in _IT_SELECTION_STOPWORDS and len(_it_stem(t)) >= 3)
        termsets.add(kept)
    if not termsets:
        raise ValidationGateError(
            "accessory selection: the DM-1975 Art.1 reduced-height enumeration is absent from the "
            "statute prose (anchor unmatched) — refusing to backfill a default")
    if len(termsets) > 1:
        raise ValidationGateError(
            "accessory selection: ambiguous Art.1 enumeration — the anchor matches multiple "
            f"distinct term-sets {sorted(sorted(s) for s in termsets)} (possible duplicate "
            "injection); refusing to pick one")
    enumeration = next(iter(termsets))
    if enumeration != _ART1_ENUMERATION:
        raise ValidationGateError(
            f"accessory selection: statute enumeration {sorted(enumeration)} drifted from the "
            f"expected DM-1975 Art.1 5-set {sorted(_ART1_ENUMERATION)}")
    return sorted(enumeration)


def verify_accessory_selection_against_text(art1_tokens, law_text, *, debt_tokens=()) -> dict:
    """SELECTION GATE — verify, never trust, for the accessory SELECTION vocabulary.

    Bind every art1-provenance token to the DM-1975 Art.1 prose enumeration by STEM EQUALITY after
    singular/plural normalization (so corrid≡corridoi, disimpegno≡disimpegni, bagno≡bagni,
    ripostiglio≡ripostigli anchor across the drift). Equality, NOT prefix: a truncated ('bag') or
    suffix-extended ('bagno_decoy') token does not anchor. Direction is subset — art1 ⊆ enumeration
    — so 'gabinetti' (carried only via the wc/toilet debt synonyms, no art1 token) is correctly
    left unmatched (honest, not a failure). Cross-lingual debt_tokens are recorded as DECLARED,
    UNANCHORED debt — never statute-checked, never reported anchored (baseline §7).

    Fail-closed (mirror parser.py:328-332,365-368): an art1 token that stem-equals no enumerated
    term RAISES (NO-INVENT analog); a deleted/absent/duplicate-injected enumeration RAISES; the
    empty stem never anchors. Returns {"anchored": {token: art1_term}, "debt": [...],
    "enumeration": [the 5 terms]}. checker.py is NOT imported (keep this neuro layer independent of
    the symbolic checker, whose module-top `import ifcopenshell` sys.exits when the wheel is absent,
    checker.py:27-37); tokens are passed in as arguments."""
    enumeration = _derive_accessory_enumeration(law_text)
    enum_by_stem = {}
    for term in enumeration:
        enum_by_stem.setdefault(_it_stem(term), term)
    anchored: dict = {}
    for token in art1_tokens:
        stem = _it_stem(token)
        if not stem:                                   # empty stem (e.g. an article) never anchors
            raise ValidationGateError(
                f"accessory selection: token {token!r} has an empty stem — never anchors "
                "(fail-closed)")
        term = enum_by_stem.get(stem)
        if term is None:
            raise ValidationGateError(
                f"accessory selection: art1 token {token!r} (stem {stem!r}) does not anchor to the "
                f"DM-1975 Art.1 enumeration {enumeration} — NO-INVENT: refusing to certify an "
                "unanchored accessory token as statute-verified")
        anchored[token] = term
    return {"anchored": anchored, "debt": list(debt_tokens), "enumeration": enumeration}


# === MONOSTANZA SURFACE GATE (Stage 4 Part 4) ==========================================
# Extends verify-never-trust from the four height/aero NUMBERS + the accessory SELECTION to a
# genuine 2nd RULE: the 'alloggio monostanza' minimum surfaces. Four numbers — the DM-1975 baseline
# mq 28 (1 person) / mq 38 (2 persons) (rules/dm_1975_salva_casa.md:26-28) and the Salva-Casa
# derogation 20 m² (1 person) / 28 m² (2 persons) (:37). Each is re-derived from the de-marked,
# answer-key-excluded corpus by a PERSON-COUNT-QUALIFIED anchor that resolves to a UNIQUE value
# (mirroring source_value below): a naive `mq\s*(\d+)` is ambiguous (matches BOTH 28 and 38) and
# would raise, so the qualified anchors are load-bearing. This is a STANDALONE primitive, exactly
# like the Part-3 selection gate: it does NOT touch THRESHOLD_KEYS, verify_rule_against_text, or
# parse_rule, so the four frozen thresholds + the live pipeline stay verdict-neutral by
# construction. Enforced by tests/test_gate.py. (The checker's hardcoded monostanza records, Part-4
# Task 2, are deliberately NOT gate-checked here — honesty boundary, see the command DECIDE/HAND-OFF.)

_MONOSTANZA_KEYS = (
    "min_surface_monostanza_1p",
    "min_surface_monostanza_2p",
    "min_surface_monostanza_sc_1p",
    "min_surface_monostanza_sc_2p",
)

# DISJOINT anchors, each resolving to a UNIQUE value over _demark(crosscheck_corpus(LAW)) and each
# pinned to its OWN immediate, RECURRING lead-in so a prepended look-alike span yields a SECOND
# distinct value -> ambiguous -> RAISE (anti-decoy-shadowing, mirroring source_value:312-333 and the
# sibling numeric anchors). The shared 28 (1p baseline vs Salva-Casa 2p) is fine: uniqueness is
# PER-ANCHOR, not global.
#   _1p anchors to `non inferiore a mq (\d+)` — the lead-in shared by BOTH 28 and 38 — and isolates
#     28 via `\b(?!\s+se per due)` (38 is the one followed by `se per due persone`). A wider
#     `per una persona[^0-9]*?mq …` gap was REJECTED by the adversarial audit: with only ONE
#     `per una persona` lead-in, a decoy `mq 99` PREPENDED before `mq 28` is captured first and is the
#     ONLY match, so the unique-value guard passes and the gate silently binds the decoy (a
#     decoy-shadowing false-pass). The recurring `non inferiore a mq` lead-in closes that hole — an
#     injected `non inferiore a mq NN` becomes a 2nd distinct value -> RAISE (verified: intact ['28'],
#     `mq 28` deleted [], decoy-prepended ['99','28']->ambiguous).
#   _2p/_sc_1p/_sc_2p are right-anchored by their person-count trailer (`se per due persone` /
#     `(1 person)` / `(2 persons)`), likewise recurring -> an injected look-alike RAISES.
# The `m²` literal is U+00B2 (round-trips in a UTF-8 raw string like the Part-3 guillemet). Run with
# re.I ONLY — the de-marked corpus has 0 newlines, so re.S is inert and the `se per due persone` line
# break is already collapsed by _demark.
_MONOSTANZA_ANCHORS = {
    "min_surface_monostanza_1p":    r"non inferiore a\s*mq\s*(\d+)\b(?!\s+se per due)",
    "min_surface_monostanza_2p":    r"mq\s*(\d+)\s+se per due persone",
    "min_surface_monostanza_sc_1p": r"(\d+)\s*m²\s*\(\s*1 person\s*\)",
    "min_surface_monostanza_sc_2p": r"(\d+)\s*m²\s*\(\s*2 persons\s*\)",
}

# Bilingual discriminator tokens a clause must carry. The only shared VALUE is 28 (_1p vs _sc_2p);
# those two keys are kept disjoint by Italian (una persona / mq) vs English (2 persons / m² /
# surface) tokens, while the 28/38 pair is separated by value-equality first. 'monostanza' is
# deliberately ABSENT — it sits in BOTH the baseline (:26-27) and the Salva-Casa (:37) spans, so it
# carries no disambiguating power and would only risk an order-dependent false-REJECT. Breadth is
# safe (any-token, mirroring _METRIC_DISCRIMINATORS): a token binds only when the clause value
# already equals the unique source value, so it cannot manufacture a false-pass.
_MONOSTANZA_DISCRIMINATORS = {
    "min_surface_monostanza_1p":    ("una persona", "mq"),
    "min_surface_monostanza_2p":    ("due persone", "mq"),
    "min_surface_monostanza_sc_1p": ("1 person", "m²", "surface"),
    "min_surface_monostanza_sc_2p": ("2 persons", "m²", "surface"),
}


def _monostanza_unit_ok(unit: Optional[str]) -> bool:
    """Surface-unit check LOCAL to the monostanza gate — deliberately NOT the shared _unit_ok
    (:336-340), which the frozen numeric gate consumes (:379) and must stay byte-identical. Accepts
    a surface unit (m²/mq/m2) only; a ratio or a metre unit (the montani/seismic height decoys) is
    rejected, so a height value can never bind a surface key."""
    u = (unit or "").strip().lower()
    return u in ("m²", "mq", "m2", "m^2", "sqm")


def _monostanza_source_value(corpus: str, key: str) -> Optional[float]:
    """The surface the statute permits for ``key``; None if its anchor is absent. Mirrors
    source_value (:312-333): re.findall over the de-marked corpus, UNIQUE-value-or-raise (>=2
    distinct matches => ambiguous => RAISE). re.I only (the de-marked corpus has no newlines, so
    re.S is inert)."""
    found = re.findall(_MONOSTANZA_ANCHORS[key], _demark(corpus), re.I)
    if not found:
        return None
    vals = {_norm_value(g) for g in found}
    if len(vals) > 1:
        raise ValidationGateError(
            f"{key}: ambiguous source — anchor matches multiple distinct values "
            f"{sorted(vals)} (possible decoy injection); refusing to pick one")
    return next(iter(vals))


def verify_monostanza_against_text(rule_or_clauses, law_text) -> dict:
    """MONOSTANZA SURFACE GATE — verify, never trust, for the 2nd rule's four surfaces.

    For each _MONOSTANZA_KEYS key the source surface is re-derived deterministically from the statute
    corpus (answer key excluded) with unique-value-or-raise. A clause binds the key only if it is a
    DISTINCT clause whose value equals that source value, with operator '>=', a surface unit
    (_monostanza_unit_ok — NOT the shared _unit_ok), and whose ``text`` carries the key's metric
    discriminator. Any missing/partial/mismatched/decoy/swapped/ambiguous value RAISES — no default
    is ever substituted. Returns the four verified surfaces {key: value}.

    Standalone primitive (mirror verify_accessory_selection_against_text): it does NOT touch
    THRESHOLD_KEYS, verify_rule_against_text, or parse_rule, so the four frozen thresholds stay
    byte-identical. Accepts either a Rule (its requirement/exception/selection/applicability clauses
    are flattened) or a flat iterable of Clause objects."""
    corpus = crosscheck_corpus(law_text)
    if isinstance(rule_or_clauses, Rule):
        clauses = [c for grp in (rule_or_clauses.requirement, rule_or_clauses.exception,
                                 rule_or_clauses.selection, rule_or_clauses.applicability)
                   for c in grp]
    else:
        clauses = list(rule_or_clauses)
    verified: dict = {}
    errors: List[str] = []
    used: set = set()

    for key in _MONOSTANZA_KEYS:
        try:
            src = _monostanza_source_value(corpus, key)
        except ValidationGateError as exc:           # ambiguous source (decoy injection) -> reject
            errors.append(str(exc))
            continue
        if src is None:
            errors.append(f"{key}: absent from the source statute text (anchor unmatched) — "
                          f"refusing to backfill a default")
            continue
        discs = _MONOSTANZA_DISCRIMINATORS[key]
        match = None
        for c in clauses:
            if id(c) in used:
                continue
            val = _norm_value(c.value)
            if val is None or abs(val - src) > _EQ_TOL:
                continue                                   # number not bound to this surface
            if c.operator != Operator.GE:
                continue                                   # wrong operator for a minimum
            if not _monostanza_unit_ok(c.unit):
                continue                                   # not a surface unit (ratio/metre decoy)
            if not any(tok in _norm_text(c.text) for tok in discs):
                continue                                   # cited span lacks this metric (swap/decoy)
            match = c
            break
        if match is None:
            errors.append(f"{key}: no clause faithfully cites source surface {src} for this metric "
                          f"(empty/partial, wrong operator/unit, or swapped/decoy span)")
            continue
        used.add(id(match))
        verified[key] = src

    if errors:
        raise ValidationGateError(
            "monostanza rule failed source cross-check (verify, never trust):\n  - "
            + "\n  - ".join(errors))
    return verified


# === GATE-ON-COMPILE: emit a gate-verified accessory SELECTION (Stage 4 Part 4) ========
# Part 3 added verify_accessory_selection_against_text but enforced it ONLY in tests; nothing called
# it when a rule was compiled, so the compiled rule's `selection: []` stayed empty
# (rules/compiled/dm_1975_salva_casa.json:8). This wires it into a deterministic, Ollama-FREE compile
# path: read the art1-provenance accessory tokens from the declarative table (stdlib json, NOT
# `import checker` — checker's module-top `import ifcopenshell` sys.exits without the wheel), run the
# Part-3 gate against the statute prose, and on success return the verified selection as Clauses the
# offline/compile path CAN emit. Fail-closed: a fabricated/unanchored art1 token RAISES. checker.py
# reads ONLY `thresholds` (from_rules_json:181-199) and the START controls use DM-1975 defaults (no
# --rules), so populating `selection` changes provenance/completeness, NOT any verdict.

_APPLICABILITY_TABLE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "rules", "applicability.json")


def _accessory_tokens_from_table(applicability_path: Optional[str] = None):
    """Return (art1_tokens, debt_tokens) from the declarative applicability table, dependency-free
    (stdlib json — the way tests/test_gate.py reads it; NEVER `import checker`). art1 tokens are the
    statute-anchorable Art.1 enumeration subset; debt tokens are the declared, unanchored
    cross-lingual synonyms (baseline §7)."""
    path = applicability_path or _APPLICABILITY_TABLE_PATH
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    groups = data["occupancy_classes"]["accessory"]["hint_groups"]
    art1 = [h for g in groups if g.get("provenance") == "art1" for h in g.get("hints", [])]
    debt = [h for g in groups if g.get("provenance") == "cross-lingual-glossary"
            for h in g.get("hints", [])]
    return art1, debt


def gate_verified_selection(law_text: str, *, applicability_path: Optional[str] = None) -> "List[Clause]":
    """Gate-on-compile: re-derive the accessory SELECTION from the statute and return it as verified
    selection Clauses, so the offline/compile path CAN emit a statute-anchored `selection` instead of
    an empty array. Each art1 token is anchored to the DM-1975 Art.1 enumeration via the Part-3 gate
    (verify_accessory_selection_against_text); a fabricated/unanchored token RAISES (NO-INVENT,
    fail-closed). The cross-lingual synonyms are carried as DECLARED, UNANCHORED debt — never reported
    statute-anchored (baseline §7). Returns one habitable-inclusion clause + one clause per anchored
    accessory token (subject/text citing the Art.1 enumeration + the anchored term)."""
    art1, debt = _accessory_tokens_from_table(applicability_path)
    verified = verify_accessory_selection_against_text(art1, law_text, debt_tokens=debt)
    enumeration = ", ".join(verified["enumeration"])
    clauses = [
        Clause(kind="selection", subject="habitable room", metric="occupancy", ifc_hint="IfcSpace",
               text=("vani abitabili (locali adibiti ad abitazione), esclusi gli accessori "
                     f"enumerati dall'Art.1 DM 5 luglio 1975: {enumeration}")),
    ]
    for token, term in verified["anchored"].items():
        clauses.append(Clause(
            kind="selection", subject="accessory room", metric="occupancy", ifc_hint="IfcSpace",
            text=(f"accessorio Art.1 DM 5 luglio 1975 ({enumeration}); hint '{token}' "
                  f"anchored to statute term '{term}'")))
    return clauses


def parse_with_ollama(text: str, model: Optional[str] = None) -> Rule:
    """Call a local Ollama model with JSON-schema-constrained output. Raises on failure."""
    import requests  # local import: only needed for the neuro path

    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    model = model or os.environ.get("ACC_LLM_MODEL", "llama3.1")
    resp = requests.post(
        f"{host}/api/chat",
        json={
            "model": model,
            "format": RULE_JSON_SCHEMA,  # Ollama structured outputs (>= 0.5)
            "stream": False,
            # temperature 0 + fixed seed: reproducible neuro output (DONE-WHEN: >=3x identical).
            # num_ctx large enough that the whole law text fits — otherwise the tail (the
            # 'Salva Casa' section) is truncated and the exception silently goes missing.
            "options": {"temperature": 0, "seed": 0, "top_k": 1, "num_ctx": 8192},
            "keep_alive": "30m",  # keep the model resident across the >=3 reproducibility runs
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        },
        timeout=300,  # local CPU/GPU: warm structured call ~1 min; cold load + grammar build longer
    )
    resp.raise_for_status()
    content = resp.json()["message"]["content"]
    return Rule.model_validate_json(content)


def parse_rule(text: str, offline: bool = False):
    """Return (rule, thresholds, source).

    Non-offline (Stage 2): the local LLM emits the rule, the VALIDATION GATE verifies every
    threshold against the source statute text, and the result is returned with source=='llm'.
    If the LLM is unreachable OR the gate rejects, this RAISES — it never silently degrades to
    the regex/defaults, which would launder an unverified or invented value into the checker.

    Offline (Stage 1): deterministic regex extraction from the law text, no LLM. source =
    'text-extraction' (or 'defaults' if the text yields nothing).
    """
    if not offline:
        rule = parse_with_ollama(text)               # raises on unreachable / HTTP / schema failure
        thr = verify_rule_against_text(rule, text)   # raises ValidationGateError on any discrepancy
        assert set(thr) == set(THRESHOLD_KEYS), "gate must resolve all four thresholds from clauses"
        return rule, thr, "llm"
    extracted = extract_thresholds_from_text(text)
    thr = {**DEFAULT_THRESHOLDS, **extracted}
    return build_rule(thr), thr, ("text-extraction" if extracted else "defaults")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Parse a legal snippet into a RASE rule + thresholds JSON")
    ap.add_argument("rule_md", help="path to the markdown law snippet")
    ap.add_argument("--offline", action="store_true", help="skip the LLM, use deterministic extraction")
    ap.add_argument("--out", metavar="FILE", help="write the compiled {rule, thresholds} JSON here")
    args = ap.parse_args(argv)

    with open(args.rule_md, encoding="utf-8") as fh:
        text = fh.read()
    rule, thr, source = parse_rule(text, offline=args.offline)
    payload = {"rule": json.loads(rule.model_dump_json()), "thresholds": thr, "source": source}
    out_json = json.dumps(payload, indent=2, ensure_ascii=False)

    if args.out:
        out_dir = os.path.dirname(args.out)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(out_json + "\n")
        print(f"[parser] wrote {args.out} (source={source}) thresholds={thr}", file=sys.stderr)
    else:
        print(out_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
