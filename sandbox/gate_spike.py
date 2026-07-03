#!/usr/bin/env python3
"""Track B span-quote gate SPIKE — high-isolation prototype (research/STRATEGIC_MOAT_ANALYSIS.md §3.2.5).

WHAT THIS IS
    The make-or-break de-risking spike for Track B (the "automated legal engineer"):
    an LLM extracts numeric thresholds from the DM-1975/Salva-Casa statute corpus as
    (value, operator, unit, VERBATIM SPAN) claims, and a deterministic SPAN-QUOTE
    PROTOCOL decides ACCEPT or REJECT for each claim. The bar is 100% PRECISION:
    zero false accepts across the corpus AND its adversarial variants. Recall is
    explicitly subordinate — a rejected-but-true claim routes to human triage
    (rejection is a routing outcome, not a failure).

WHAT THIS IS NOT
    Not production code. The gate path (validate_claim) imports NOTHING from
    parser.py/checker.py (high isolation: a spike defect cannot contaminate the
    shipped gate); the battery additionally runs a lazy anchor-parity pin against
    parser.py so the hand-copied ANCHORS table cannot silently drift. Emits no
    SHACL. Writes no rule files. The 37 test_gate.py pins remain the recall floor
    for the full spike (strategy §3.2.5 step 4); this prototype implements the
    protocol layers and the meta-gate battery those pins will be replayed against.

DECLARED RECALL DEBT (rejections route to triage BY DESIGN; red-teamed 2026-07-03,
recall-tuned in the 37-pin replay round — see gate_replay.py)
    - RESOLVED (host-sentence direction fallback): marker-less tight spans
      ('20 m² (1 person)', '28 m² (2 persons)') now bind — direction is derived from
      the anchor's host statute sentence, which the claimant cannot manipulate.
    - RESOLVED (gloss-anchor tier): the corpus's verbatim English gloss lines bind
      through GLOSS_ANCHORS, gated on value agreement with the primary Italian
      anchor's corpus-unique value (a shadowed/deleted primary rejects the gloss too).
    - REMAINING: true paraphrases (not verbatim anywhere in the corpus, e.g.
      'not less than 0.125 of the floor area') reject at L1 and route to triage —
      the §3.2.5 quotation layer carries them as never-load-bearing gloss alongside
      a verbatim span; the montani reduction ('reduced to m 2,55') stays scope-less
      and anchored to no key, by design.
    Zero false accepts were constructible in either red-team round; precision > recall
    is the contract (strategy §3.2.5 step 3).

PROTOCOL LAYERS (each claim must clear ALL of them — any miss REJECTS)
    L1 span fidelity      claim.span is an exact substring (markdown/whitespace/case
                          normalized) of the answer-key-excluded corpus,
                          occurring exactly once.
    L2 span re-parse      a fixed, rule-agnostic grammar for Italian legal numerics
                          re-derives (value, direction, unit-class) from the SPAN
                          ALONE and must reproduce the claim exactly.
    L3 anchor cross-exam  the span must contain a known deterministic lead-in anchor
                          (the regexes proven by the hand-anchored gate), and the
                          anchor must re-derive the SAME value both in-span and
                          corpus-wide, uniquely (>=2 distinct corpus values under
                          one anchor = decoy injection = REJECT).
    L4 direction policy   every anchored metric here is a MINIMUM: operator must
                          be '>=' (a manipulated 'non superiore' span can never
                          bind a minimum).

RUN
    python gate_spike.py                 # offline meta-gate battery (deterministic, no LLM)
    python gate_spike.py --live          # battery + live Ollama loop over corpus + variants
    python gate_spike.py --live --report out.json
    Exit 0 iff the battery matches every expected verdict AND (if --live) zero
    false accepts occurred. Any other outcome exits 1 (blockable for CI).
"""
from __future__ import annotations

# =============================================================================
# SYSTEM POLICY ANCHOR — structural contract, frozen by
# research/STRATEGIC_MOAT_ANALYSIS.md §3.2.5 (Declaration 2). Do not edit
# without an ADR superseding that declaration. _enforce_policy_anchor() makes
# this a runtime refusal, not a comment: the spike will not run in a
# configuration that claims zero human review.
ZERO_HUMAN_CODING_TARGET = True    # automated SHACL generation is the mechanism; this gate is the license to use it
ZERO_HUMAN_REVIEW_CLAIMED = False  # Regulatory liability requires professional sign-off dashboard
# =============================================================================

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field

_SANDBOX = Path(__file__).resolve().parent
CORPUS_PATH = _SANDBOX / "rules" / "dm_1975_salva_casa.md"
_EQ_TOL = 1e-9


def _enforce_policy_anchor() -> None:
    """Refuse to run under a policy-violating configuration (strategy §3.2.5)."""
    if not ZERO_HUMAN_CODING_TARGET or ZERO_HUMAN_REVIEW_CLAIMED:
        raise SystemExit(
            "POLICY VIOLATION: the span-quote gate may only run with "
            "ZERO_HUMAN_CODING_TARGET=True and ZERO_HUMAN_REVIEW_CLAIMED=False. "
            "Dropping the human sign-off boundary is a strategy violation "
            "(research/STRATEGIC_MOAT_ANALYSIS.md §3.2.5), not a configuration choice."
        )


# --- LLM claim schema (Ollama structured output) --------------------------------------
class SpanClaim(BaseModel):
    """One extracted threshold with its verbatim source span."""

    metric: str = Field(description="short label, e.g. 'habitable min height'")
    value: float = Field(description="the numeric threshold exactly as written (fraction as decimal)")
    operator: str = Field(description="'>=' or '<='")
    unit: str = Field(description="'m' | 'm2' | 'ratio'")
    span: str = Field(description="verbatim source span, character-for-character, containing the number")


class SpanClaims(BaseModel):
    claims: List[SpanClaim] = Field(default_factory=list)


SPIKE_PROMPT = (
    "You are a legal threshold extractor. From ONLY the regulation text provided, extract "
    "EVERY numeric threshold (minimum heights in metres, minimum surfaces in mq/m², minimum "
    "window-to-floor ratios) as one claim each, and emit ONLY JSON matching the schema.\n"
    "HARD RULES:\n"
    "1. `span` is the verbatim source text, character-for-character, including the number. "
    "Never paraphrase, translate, summarize, or quote any answer/summary table.\n"
    "2. Keep each span TIGHT: one threshold per claim, one number per span where the text "
    "allows it.\n"
    "3. `value` is the number as written (Italian comma '2,70' -> 2.70; fraction '1/8' -> 0.125).\n"
    "4. `operator` is '>=' for minima ('non inferiore', 'fissata in', 'almeno', 'minimum', "
    "'riducibile a' = a reduced minimum) and '<=' for maxima ('non superiore').\n"
    "5. `unit` is 'm' for heights, 'm2' for surfaces, 'ratio' for area fractions.\n"
    "6. Do NOT emit dates, article numbers, altitudes (s.l.m.), or percentages."
)


# --- normalization (aligned with the proven gate's semantics, reimplemented here) ------
def crosscheck_corpus(law_text: str) -> str:
    """Answer-key exclusion: drop everything from the 'Target rule' heading onward."""
    m = re.search(r"^#{1,6}\s*Target rule", law_text, re.I | re.M)
    return law_text[: m.start()] if m else law_text


def _demark(s: str) -> str:
    """Strip markdown emphasis/quote markers, collapse whitespace. Commas/case intact
    (this is the form the deterministic anchors run over, exactly like the shipped gate)."""
    s = (s or "").replace("*", " ").replace(">", " ").replace("`", " ")
    return re.sub(r"\s+", " ", s).strip()


def _norm(s: str) -> str:
    """Fidelity form: demarked + lowercased + decimal commas unified + apostrophes unified.
    A verbatim span must survive markdown wrapping ('**2,40**'), not word changes."""
    s = _demark(s).lower().replace("’", "'").replace("«", " ").replace("»", " ")
    s = re.sub(r"(\d),(\d)", r"\1.\2", s)
    s = re.sub(r"\s+([,;.:])", r"\1", s)   # '2.70 ,' (markdown-strip artifact) -> '2.70,'
    return re.sub(r"\s+", " ", s).strip()


# --- L3: the deterministic anchors (the hand-proven lead-ins, spike-local copy) --------
# Keys/regexes mirror the shipped gate (parser.py _SOURCE_ANCHORS/_MONOSTANZA_ANCHORS);
# duplicated here BY DESIGN: the spike must not import production code (isolation), and
# the full spike will later diff this table against parser.py as its own consistency pin.
ANCHORS = {
    "min_height_habitable_m":   r"fissata\s+in\s+m\s*(\d+[.,]\d+)",
    "min_height_accessory_m":   r"riducibile a\s*m\s*(\d+[.,]\d+)",
    "min_height_salva_casa_m":  r"minimum internal height\s*(\d+[.,]\d+)",
    "aero_illuminating_ratio":  r"(\d+)\s*/\s*(\d+)\s*della superficie del pavimento",
    "min_surface_monostanza_1p":    r"non inferiore a\s*mq\s*(\d+)\b(?!\s+se per due)",
    "min_surface_monostanza_2p":    r"mq\s*(\d+)\s+se per due persone",
    "min_surface_monostanza_sc_1p": r"(\d+)\s*m²\s*\(\s*1 person\s*\)",
    "min_surface_monostanza_sc_2p": r"(\d+)\s*m²\s*\(\s*2 persons\s*\)",
}
# Unit class each anchored metric must carry (L2/L3 agreement).
ANCHOR_UNIT = {
    "min_height_habitable_m": "m", "min_height_accessory_m": "m",
    "min_height_salva_casa_m": "m", "aero_illuminating_ratio": "ratio",
    "min_surface_monostanza_1p": "m2", "min_surface_monostanza_2p": "m2",
    "min_surface_monostanza_sc_1p": "m2", "min_surface_monostanza_sc_2p": "m2",
}

# --- GLOSS-ANCHOR TIER (37-pin replay upgrade; strategy §3.2.5 quotation layer) ---------
# The corpus carries verbatim ENGLISH gloss lines for three thresholds; the historical
# bilingual accepts (test_gate.py:165-181) bind through them. A gloss anchor is a SECOND
# way to match L3 — never a second source of truth: a gloss-anchored claim must ALSO agree
# with the PRIMARY (Italian statutory) anchor's corpus-unique value. Consequences that keep
# precision intact: (a) if the primary anchor is decoy-shadowed (ambiguous) or deleted, the
# gloss path rejects too; (b) an injected gloss look-alike with a different value makes the
# gloss anchor corpus-ambiguous AND fails primary agreement — both reject. Gloss patterns
# run over the NORMALIZED form (decimal commas unified), unlike the primary tier which
# stays byte-equal to parser.py (the parity pin) and runs over the demarked form.
# gloss_accessory is SCOPE-BOUND to its continuation ('for corridors'): the statute holds
# 2.40 m under TWO legally distinct regimes (unconditional accessory vs conditional
# Salva-Casa 5-bis), so a value-agreement check alone cannot disambiguate scope — the
# red team showed a poisoned 'reducible to 2.40 m under Salva-Casa 5-ter' gloss would
# otherwise bind the accessory key. Encoding the scope words in the pattern makes any
# differently-scoped look-alike fall through to REJECT_NO_ANCHOR. Numerics are bounded
# (max 2 decimals; 1-2 digit numerator) so '2.400' / '11/8' cannot slip a magnitude.
GLOSS_ANCHORS = {
    "gloss_habitable":  r"min net internal height\s*(\d+\.\d{1,2})\s*m\b",
    "gloss_accessory":  r"reducible to\s*(\d+\.\d{1,2})\s*m for corridors",
    "gloss_aero":       r"\b(\d{1,2})\s*/\s*(\d{1,3})\s*of the floor area",
}
GLOSS_TO_PRIMARY = {
    "gloss_habitable": "min_height_habitable_m",
    "gloss_accessory": "min_height_accessory_m",
    "gloss_aero": "aero_illuminating_ratio",
}
GLOSS_UNIT = {"gloss_habitable": "m", "gloss_accessory": "m", "gloss_aero": "ratio"}


def _gloss_values(text_norm: str, key: str) -> set:
    """All distinct values a gloss anchor resolves to in normalized `text_norm`."""
    found = re.findall(GLOSS_ANCHORS[key], text_norm, re.S | re.I)
    if key == "gloss_aero":
        return {int(a) / int(b) for a, b in found}
    return {float(g) for g in found}


def _anchor_values(text: str, key: str) -> set:
    """All distinct values an anchor resolves to in `text` (demarked form)."""
    found = re.findall(ANCHORS[key], _demark(text), re.S | re.I)
    if key == "aero_illuminating_ratio":
        return {int(a) / int(b) for a, b in found}
    return {float(str(g).replace(",", ".")) for g in found}


# --- L2: fixed, rule-agnostic span grammar for Italian legal numerics ------------------
_DEROG_PAREN = re.compile(r"\((?:derogating|che deroga|in deroga)[^)]*\)", re.I)
# NOTE: bare '\bmin\b' was red-teamed OUT (fires on minutes/abbreviation senses: '30 min',
# 'min. 0,5 vol/h'); the English shorthand is honored only in its height-gloss context.
_GE_PAT = re.compile(r"non\s+(?:potr[aà]'?\s+essere\s+)?inferiore|\balmeno\b|fissata\s+in"
                     r"|\bminim[ao]\b|\bminimum\b|\bmin\b(?=\.?\s+(?:net|internal|height))"
                     r"|≥|>=", re.I)
_LE_PAT = re.compile(r"non\s+(?:potr[aà]'?\s+essere\s+)?superiore|\bmassim[ao]\b|\bmaximum\b|≤|<=", re.I)
_DEROG_PAT = re.compile(r"riducibile\s+a|ridott[ao]\s+a|reduced\s+to|reducible\s+to"
                        r"|derogating|in\s+deroga", re.I)

_NUM_M = re.compile(r"\bm\s+(\d+\.\d+)|(\d+\.\d+)\s*m\b")          # heights (normalized text: 2.70)
_NUM_M2 = re.compile(r"\bmq\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*m(?:²|2)\b")  # surfaces
_NUM_RATIO = re.compile(r"(\d+)\s*/\s*(\d+)")                       # fractions

# Closed unit lexicon with synonym canonicalization (pure relabeling: the unit must STILL
# agree with the span re-parse (L2) and the anchor's unit class (L3), so this can widen
# recall but never precision).
_UNIT_CANON = {
    "m": "m", "metri": "m", "metro": "m", "meter": "m", "meters": "m", "metres": "m",
    "m2": "m2", "m²": "m2", "mq": "m2", "sqm": "m2",
    "ratio": "ratio", "frazione": "ratio", "fraction": "ratio",
}


def _canon_unit(unit: str) -> Optional[str]:
    return _UNIT_CANON.get((unit or "").strip().lower())


_CONFLICT = "CONFLICT"


def _span_direction(span_norm: str) -> Optional[str]:
    """Closed operator lexicon over the span. Three states, kept distinct (a red-teamed
    contract hole): neither marker -> None (may still resolve via the host chunk); BOTH
    directions -> _CONFLICT (a self-contradictory span can never bind, host chunk or not)."""
    ge = bool(_GE_PAT.search(span_norm)) or bool(_DEROG_PAT.search(span_norm))
    le = bool(_LE_PAT.search(span_norm))
    if ge and le:
        return _CONFLICT
    if ge:
        return ">="
    if le:
        return "<="
    return None


# Negated derogation/reduction phrasing ('never reducible to', 'non è riducibile a'):
# polarity inversion the span-lexicon alone cannot see when the claimant truncates the
# negator out of the span. Checked over the claimant-immutable HOST CHUNK. The legitimate
# Italian GE idiom 'non potrà essere inferiore' is NOT matched (inferiore is not a
# reduction stem).
_NEG_DEROG = re.compile(
    r"\b(?:never|not|mai|non)\s+(?:\w+\s+){0,2}?(?:riducibil|reducibl|ridott|reduc|derogat)\w*",
    re.I)

# Host-chunk boundaries in normalized text: ';', ':' and bullet separators ' - ' (a dot
# between digits is a decimal, and abbreviation dots — 'incl.', 'art.' — would cut real
# sentences; the bullet boundary stops an adjacent provision's marker from bleeding in
# when a ';' is edited away — red-teamed). Capped to ±150 chars around the SPAN to stay
# local; a chunk with CONFLICTING markers yields no direction (reject upstream).
_SENT_SPLIT = re.compile(r"(?<!\d)[;:](?!\d)|\s-\s")


def _host_chunk(corpus_norm: str, span_norm: str) -> str:
    """The corpus chunk hosting THE CLAIMANT'S OWN span occurrence (L1 has already proven
    it occurs exactly once). Red-team lesson: direction must be read where the validated
    span actually sits — a first-match anchor search can land on a DIFFERENT occurrence
    of the same value (e.g. a minimum bullet elsewhere) while the span sits inside a
    maximum provision."""
    pos = corpus_norm.find(span_norm)
    if pos < 0:                                    # unreachable after L1; fail closed
        return ""
    p_end = pos + len(span_norm)
    start, end = 0, len(corpus_norm)
    for b in _SENT_SPLIT.finditer(corpus_norm):
        if b.start() < pos:
            start = b.end()
        elif b.start() >= p_end:
            end = b.start()
            break
    start = max(start, pos - 150)
    end = min(end, p_end + 150)
    return corpus_norm[start:end]


def _span_values(span_norm: str, unit: str) -> List[float]:
    """Distinct numeric candidates of the claim's unit class, from the span ONLY.
    Derogation parentheticals ('(derogating the 2,70 m baseline)') are stripped first:
    they reference the baseline being derogated, not the asserted threshold."""
    s = _DEROG_PAREN.sub(" ", span_norm)
    vals: List[float] = []
    if unit == "m":
        for a, b in _NUM_M.findall(s):
            vals.append(float(a or b))
    elif unit == "m2":
        for a, b in _NUM_M2.findall(s):
            vals.append(float(a or b))
    elif unit == "ratio":
        for a, b in _NUM_RATIO.findall(s):
            vals.append(int(a) / int(b))
    out: List[float] = []
    for v in vals:
        if not any(abs(v - w) <= _EQ_TOL for w in out):
            out.append(v)
    return out


# --- the verdict ------------------------------------------------------------------------
@dataclass
class Verdict:
    accepted: bool
    reason: str                    # 'ACCEPT' or a REJECT_* code
    detail: str = ""
    anchor_key: Optional[str] = None
    route: str = ""                # 'human-triage' on every rejection

    @staticmethod
    def reject(reason: str, detail: str = "") -> "Verdict":
        return Verdict(False, reason, detail, route="human-triage")


def validate_claim(claim: SpanClaim, corpus_raw: str) -> Verdict:
    """The span-quote protocol: L1 fidelity -> L2 re-parse -> L3 anchor cross-exam -> L4 policy."""
    _enforce_policy_anchor()                       # on the gate path itself, not only the CLI entry
    corpus = crosscheck_corpus(corpus_raw)         # L1 precondition: answer key can never satisfy the gate
    span_norm = _norm(claim.span)
    corpus_norm = _norm(corpus)

    if not span_norm or claim.value is None:
        return Verdict.reject("REJECT_MALFORMED", "empty span or missing value")

    # L1 — span fidelity: exact substring, exactly once.
    n = corpus_norm.count(span_norm)
    if n == 0:
        return Verdict.reject("REJECT_SPAN_NOT_FOUND",
                              "span is not a verbatim substring of the statute corpus "
                              "(paraphrase, translation, answer-key echo, or deleted text)")
    if n > 1:
        return Verdict.reject("REJECT_SPAN_NOT_UNIQUE", f"span occurs {n} times in the corpus")

    # Host chunk of the claimant's own (unique) occurrence — used for the polarity guard
    # and, for marker-less spans, the direction fallback.
    chunk = _host_chunk(corpus_norm, span_norm)
    if _NEG_DEROG.search(chunk):
        return Verdict.reject("REJECT_POLARITY_NEGATED",
                              "the statute chunk hosting this span NEGATES the reduction "
                              "('never/non ... reducible') — a truncated span cannot drop "
                              "the negator")

    # L2 — deterministic re-parse from the span alone.
    unit = _canon_unit(claim.unit)
    if unit is None:
        return Verdict.reject("REJECT_UNIT_UNKNOWN", f"unit {claim.unit!r} outside the closed lexicon")
    direction = _span_direction(span_norm)
    if direction == _CONFLICT:
        return Verdict.reject("REJECT_SPAN_DIRECTION_CONFLICT",
                              "span carries BOTH minimum and maximum phrasing — a "
                              "self-contradictory span can never bind")
    if direction is not None and direction != claim.operator:
        return Verdict.reject("REJECT_OPERATOR_MISMATCH",
                              f"span phrasing implies {direction!r}, claim says {claim.operator!r}")
    # direction None is NOT yet a rejection: a marker-less span may still bind through a
    # corpus-unique anchor, whose host statute chunk then supplies the direction (below).
    cands = _span_values(span_norm, unit)
    if not cands:
        return Verdict.reject("REJECT_VALUE_NOT_IN_SPAN",
                              f"no {unit}-class number found in the span")
    if len(cands) > 1:
        return Verdict.reject("REJECT_SPAN_AMBIGUOUS",
                              f"span carries {len(cands)} distinct {unit}-class values "
                              f"{sorted(cands)}; isolate one threshold per span")
    if abs(cands[0] - claim.value) > _EQ_TOL:
        return Verdict.reject("REJECT_VALUE_MISMATCH",
                              f"span states {cands[0]}, claim states {claim.value}")

    # L3 — anchor cross-examination, two tiers.
    # PRIMARY tier: the span carries a statutory lead-in anchor re-deriving the same value
    # in-span AND corpus-wide, uniquely.
    matched_key = None
    for key, pat in ANCHORS.items():
        if ANCHOR_UNIT[key] != unit:
            continue
        m = re.search(pat, _demark(claim.span), re.S | re.I)
        if not m:
            continue
        in_span = (int(m.group(1)) / int(m.group(2)) if key == "aero_illuminating_ratio"
                   else float(str(m.group(1)).replace(",", ".")))
        if abs(in_span - claim.value) > _EQ_TOL:
            return Verdict.reject("REJECT_ANCHOR_VALUE_MISMATCH",
                                  f"anchor {key} re-derives {in_span} from the span, "
                                  f"claim states {claim.value}", )
        matched_key = key
        break

    if matched_key is not None:
        corpus_vals = _anchor_values(corpus, matched_key)
        if not corpus_vals:
            return Verdict.reject("REJECT_ANCHOR_ABSENT_IN_CORPUS",
                                  f"anchor {matched_key} matches the span but not the corpus")
        if len(corpus_vals) > 1:
            return Verdict.reject("REJECT_CORPUS_ANCHOR_AMBIGUOUS",
                                  f"anchor {matched_key} resolves to multiple distinct corpus values "
                                  f"{sorted(corpus_vals)} (possible decoy injection); refusing to pick one")
        src = next(iter(corpus_vals))
        if abs(src - claim.value) > _EQ_TOL:
            return Verdict.reject("REJECT_CORPUS_VALUE_MISMATCH",
                                  f"corpus permits {src} for {matched_key}, claim states {claim.value}")
    else:
        # GLOSS tier: the span carries a verbatim English-gloss anchor. Never a second
        # source of truth — the gloss must be corpus-unique AND its value must equal the
        # PRIMARY anchor's corpus-unique value (cross-language agreement). A shadowed,
        # deleted, or divergent primary rejects the gloss path too.
        for gkey, gpat in GLOSS_ANCHORS.items():
            if GLOSS_UNIT[gkey] != unit:
                continue
            gm = re.search(gpat, span_norm, re.S | re.I)
            if not gm:
                continue
            in_span = (int(gm.group(1)) / int(gm.group(2)) if gkey == "gloss_aero"
                       else float(gm.group(1)))
            if abs(in_span - claim.value) > _EQ_TOL:
                return Verdict.reject("REJECT_ANCHOR_VALUE_MISMATCH",
                                      f"gloss anchor {gkey} re-derives {in_span} from the span, "
                                      f"claim states {claim.value}")
            gvals = _gloss_values(corpus_norm, gkey)
            if len(gvals) != 1:
                return Verdict.reject("REJECT_CORPUS_ANCHOR_AMBIGUOUS",
                                      f"gloss anchor {gkey} resolves to {sorted(gvals)} in the "
                                      f"corpus (absent or ambiguous); refusing")
            pkey = GLOSS_TO_PRIMARY[gkey]
            pvals = _anchor_values(corpus, pkey)
            if len(pvals) != 1 or abs(next(iter(pvals)) - claim.value) > _EQ_TOL or \
                    abs(next(iter(gvals)) - claim.value) > _EQ_TOL:
                return Verdict.reject("REJECT_GLOSS_PRIMARY_DISAGREEMENT",
                                      f"gloss {gkey}={sorted(gvals)} must agree with primary "
                                      f"{pkey}={sorted(pvals)} and the claim ({claim.value}); "
                                      f"any shadowed/deleted/divergent primary rejects the gloss path")
            matched_key = pkey
            break
    if matched_key is None:
        return Verdict.reject("REJECT_NO_ANCHOR",
                              "span carries no known deterministic lead-in anchor "
                              "(decoy scope, or a genuinely new phrasing -> triage)")

    # Direction resolution for marker-less spans: derived from the statute chunk hosting
    # THE SPAN'S OWN occurrence (claimant-immutable), never from the claim itself and
    # never from a different occurrence of the same anchor value.
    if direction is None:
        direction = _span_direction(chunk)
        if direction is None or direction == _CONFLICT:
            return Verdict.reject("REJECT_DIRECTION_AMBIGUOUS",
                                  "no comparative phrasing in the span, and the span's host "
                                  "statute chunk supplies none (or conflicting) either")
        if direction != claim.operator:
            return Verdict.reject("REJECT_OPERATOR_MISMATCH",
                                  f"host statute chunk implies {direction!r}, "
                                  f"claim says {claim.operator!r}")

    # L4 — direction policy: every anchored metric here is a minimum.
    if claim.operator != ">=":
        return Verdict.reject("REJECT_DIRECTION_POLICY",
                              f"{matched_key} is a statutory minimum; operator must be '>='")

    return Verdict(True, "ACCEPT", f"value {claim.value} bound to {matched_key}", matched_key)


# --- adversarial corpus variants (NEW decoys, per the Day-1 brief) ----------------------
_COASTAL_DECOY = (
    "\n> *Separate provision (decoy):* nei **comuni costieri** sotto i 300 m s.l.m. "
    "l'altezza minima interna utile dei locali adibiti ad abitazione è fissata "
    "in **m 2,60** (typology carve-out).\n"
)


def corpus_variants(raw: str) -> dict:
    """Deterministic adversarial mutations of the statute corpus (live-loop set)."""
    v1 = raw.replace("## \"Salva Casa\"", _COASTAL_DECOY + "\n## \"Salva Casa\"", 1)
    assert v1 != raw, "V1 injection point not found"
    v2 = raw.replace("non potrà essere\n> inferiore a **1/8", "non potrà essere\n> superiore a **1/8", 1)
    assert v2 != raw, "V2 operator flip point not found"
    v3 = raw.replace("è fissata\n> in **m 2,70**, ", "è ", 1)
    assert v3 != raw, "V3 span deletion point not found"
    return {
        "V0_baseline": raw,
        "V1_coastal_decoy_shadow": v1,     # look-alike 'fissata in m 2,60' with wrong municipal scope
        "V2_operator_manipulated": v2,     # 'non potra essere superiore a 1/8'
        "V3_habitable_span_deleted": v3,   # 'fissata in m 2,70' removed
    }


def battery_variants(raw: str) -> dict:
    """corpus_variants + battery-only mutations targeting the gloss tier and the
    host-sentence direction fallback (not part of the live loop's truth table)."""
    out = corpus_variants(raw)
    v4 = raw.replace("reducible to 2.40 m for corridors",
                     "reducible to 2.10 m for garages and cellars; reducible to 2.40 m "
                     "for corridors", 1)
    assert v4 != raw, "V4 gloss-decoy injection point not found"
    v5 = raw.replace("*alloggio monostanza* minimum surface (incl. services)",
                     "*alloggio monostanza* surface (incl. services)", 1)
    assert v5 != raw, "V5 direction-strip point not found"
    out["V4_gloss_decoy_shadow"] = v4      # look-alike English gloss with a divergent value
    out["V5_direction_stripped"] = v5      # 'minimum' removed from the monostanza sc bullet
    # Red-team round 2 mutations (poisoned-corpus class; each pins a fixed enabler):
    v6 = raw.replace("due persone.»",
                     "due persone. Nota: il numero degli occupanti non superiore a due.»", 1)
    assert v6 != raw, "V6 conflict injection point not found"
    v7 = raw.replace("*alloggio monostanza* minimum surface (incl. services)",
                     "*alloggio monostanza* surface (ricambio aria min. 0,5 vol/h, "
                     "incl. services)", 1)
    assert v7 != raw, "V7 min-token injection point not found"
    v8 = raw.replace("## Target rule",
                     "La superficie per nucleo non potrà essere superiore a 28 m² (2 persons) "
                     "per nucleo di emergenza.\n\n## Target rule", 1)
    assert v8 != raw, "V8 max-provision injection point not found"
    v9 = raw.replace("(derogating the 2,70 m baseline);", "(derogating the 2,70 m baseline),", 1) \
            .replace("*alloggio monostanza* minimum surface", "*alloggio monostanza* surface", 1)
    assert v9 != raw, "V9 boundary-removal point not found"
    v10 = raw.replace("reducible to 2.40 m for corridors",
                      "never reducible to 2.40 m for corridors", 1)
    assert v10 != raw, "V10 negation injection point not found"
    v11 = raw.replace("down to the reduced minimums:",
                      "down to the reduced minimums (existing buildings are reducible to "
                      "2.40 m under Salva-Casa 5-ter):", 1)
    assert v11 != raw, "V11 scope-crossover injection point not found"
    out["V6_conflicting_span"] = v6        # LE note appended inside the monostanza sentence
    out["V7_min_token_decoy"] = v7         # 'min.' time/abbrev token where 'minimum' was stripped
    out["V8_same_value_max"] = v8          # second sc_2p-shaped occurrence inside a MAX provision
    out["V9_boundary_bleed"] = v9          # ';' -> ',' so the height bullet abuts the stripped bullet
    out["V10_negated_gloss"] = v10         # 'never reducible to 2.40 m' — truncation attack
    out["V11_gloss_scope_crossover"] = v11 # Salva-Casa-scoped gloss look-alike at the shared 2.40
    return out


# --- the offline meta-gate battery (deterministic; no LLM) ------------------------------
def _c(metric, value, operator, unit, span) -> SpanClaim:
    return SpanClaim(metric=metric, value=value, operator=operator, unit=unit, span=span)


_SPAN_HABITABLE = ("L'altezza minima interna utile dei locali adibiti ad abitazione è fissata "
                   "in m 2,70")
_SPAN_ACCESSORY = ("riducibile a m 2,40 per i corridoi, i disimpegni in genere, i bagni, "
                   "i gabinetti ed i ripostigli")
_SPAN_AERO = ("la superficie finestrata apribile non potrà essere inferiore a 1/8 della "
              "superficie del pavimento")
_SPAN_SALVA = "minimum internal height 2,40 m (derogating the 2,70 m baseline)"
_SPAN_MONO_1P = ("deve avere una superficie minima, comprensiva dei servizi, non inferiore a mq 28")
_SPAN_MONO_2P = "non inferiore a mq 38 se per due persone"
_SPAN_MONTANI = "the habitable-room minimum may be reduced to m 2,55"


def battery() -> List[Tuple[str, str, SpanClaim, str]]:
    """(variant, case_id, claim, expected 'ACCEPT'|'REJECT') — the meta-gate ground truth."""
    return [
        # Legitimate claims on the untouched corpus -> ACCEPT (the recall floor of this prototype).
        ("V0_baseline", "ok_habitable_270", _c("habitable min height", 2.70, ">=", "m", _SPAN_HABITABLE), "ACCEPT"),
        ("V0_baseline", "ok_accessory_240", _c("accessory min height", 2.40, ">=", "m", _SPAN_ACCESSORY), "ACCEPT"),
        ("V0_baseline", "ok_aero_0125", _c("aero ratio", 0.125, ">=", "ratio", _SPAN_AERO), "ACCEPT"),
        ("V0_baseline", "ok_salva_240", _c("salva casa height", 2.40, ">=", "m", _SPAN_SALVA), "ACCEPT"),
        ("V0_baseline", "ok_mono_1p_28", _c("monostanza 1p", 28.0, ">=", "m2", _SPAN_MONO_1P), "ACCEPT"),
        ("V0_baseline", "ok_mono_2p_38", _c("monostanza 2p", 38.0, ">=", "m2", _SPAN_MONO_2P), "ACCEPT"),
        # Attacks -> REJECT, every one.
        ("V0_baseline", "atk_montani_decoy_quoted",
         _c("habitable min height", 2.55, ">=", "m", _SPAN_MONTANI), "REJECT"),
        ("V0_baseline", "atk_value_echo_wrong",
         _c("habitable min height", 2.55, ">=", "m", _SPAN_HABITABLE), "REJECT"),
        ("V0_baseline", "atk_paraphrase_span",
         _c("habitable min height", 2.70, ">=", "m", "l'altezza minima abitabile è di metri 2,70"), "REJECT"),
        ("V0_baseline", "atk_answer_key_echo",
         _c("habitable min height", 2.70, ">=", "m", "habitable net height ≥ 2.70 m (accessory ≥ 2.40 m)"), "REJECT"),
        ("V0_baseline", "atk_operator_flip_claim",
         _c("aero ratio", 0.125, "<=", "ratio", _SPAN_AERO), "REJECT"),
        ("V0_baseline", "atk_unit_swap",
         _c("habitable min height", 2.70, ">=", "ratio", _SPAN_HABITABLE), "REJECT"),
        ("V0_baseline", "atk_two_value_span",
         _c("habitable min height", 2.70, ">=", "m",
            "è fissata in m 2,70, riducibile a m 2,40"), "REJECT"),
        # Mutated corpora: the very claims that were legitimate must now REJECT.
        ("V1_coastal_decoy_shadow", "mut_decoy_shadow_habitable",
         _c("habitable min height", 2.70, ">=", "m", _SPAN_HABITABLE), "REJECT"),
        ("V1_coastal_decoy_shadow", "mut_decoy_shadow_injected_260",
         _c("habitable min height", 2.60, ">=", "m",
            "nei comuni costieri sotto i 300 m s.l.m. l'altezza minima interna utile dei locali "
            "adibiti ad abitazione è fissata in m 2,60"), "REJECT"),
        ("V2_operator_manipulated", "mut_operator_ge_claim",
         _c("aero ratio", 0.125, ">=", "ratio",
            "la superficie finestrata apribile non potrà essere superiore a 1/8 della "
            "superficie del pavimento"), "REJECT"),
        ("V2_operator_manipulated", "mut_operator_le_claim",
         _c("aero ratio", 0.125, "<=", "ratio",
            "la superficie finestrata apribile non potrà essere superiore a 1/8 della "
            "superficie del pavimento"), "REJECT"),
        ("V3_habitable_span_deleted", "mut_deleted_span_habitable",
         _c("habitable min height", 2.70, ">=", "m", _SPAN_HABITABLE), "REJECT"),
        # V1 collateral check: the injection must NOT break unrelated metrics (still ACCEPT).
        ("V1_coastal_decoy_shadow", "ok_v1_accessory_unaffected",
         _c("accessory min height", 2.40, ">=", "m", _SPAN_ACCESSORY), "ACCEPT"),
        ("V3_habitable_span_deleted", "ok_v3_aero_unaffected",
         _c("aero ratio", 0.125, ">=", "ratio", _SPAN_AERO), "ACCEPT"),
        # --- GLOSS TIER (37-pin replay upgrade): verbatim English-gloss accepts... ---
        ("V0_baseline", "ok_gloss_accessory_240",
         _c("accessory min height", 2.40, ">=", "m",
            "reducible to 2,40 m for corridors, circulation, bathrooms, WCs and store rooms"), "ACCEPT"),
        ("V0_baseline", "ok_gloss_habitable_270",
         _c("habitable min height", 2.70, ">=", "m",
            "Habitable rooms: min net internal height 2.70 m"), "ACCEPT"),
        ("V0_baseline", "ok_gloss_aero_verbatim",
         _c("aero ratio", 0.125, ">=", "ratio",
            "Openable window area must be ≥ 1/8 of the floor area"), "ACCEPT"),
        # ...and the attacks that must keep the tier honest.
        ("V0_baseline", "atk_gloss_paraphrase_not_verbatim",
         _c("aero ratio", 0.125, ">=", "ratio",
            "openable window area not less than 0.125 of the floor area"), "REJECT"),
        ("V4_gloss_decoy_shadow", "mut_gloss_decoy_value",
         _c("accessory min height", 2.10, ">=", "m",
            "reducible to 2.10 m for garages and cellars"), "REJECT"),
        ("V4_gloss_decoy_shadow", "ok_gloss_scope_bound_survives_offscope_decoy",
         _c("accessory min height", 2.40, ">=", "m",
            "reducible to 2.40 m for corridors, circulation, bathrooms, WCs and store rooms"), "ACCEPT"),
        ("V4_gloss_decoy_shadow", "ok_v4_primary_accessory_unaffected",
         _c("accessory min height", 2.40, ">=", "m", _SPAN_ACCESSORY), "ACCEPT"),
        ("V1_coastal_decoy_shadow", "mut_gloss_blocked_by_shadowed_primary",
         _c("habitable min height", 2.70, ">=", "m",
            "Habitable rooms: min net internal height 2.70 m"), "REJECT"),
        # --- HOST-SENTENCE DIRECTION FALLBACK: marker-less tight spans... ---
        ("V0_baseline", "ok_host_dir_sc1p_tight",
         _c("monostanza sc 1p", 20.0, ">=", "m2", "20 m² (1 person)"), "ACCEPT"),
        ("V0_baseline", "ok_host_dir_sc2p_tight",
         _c("monostanza sc 2p", 28.0, ">=", "m2", "28 m² (2 persons)"), "ACCEPT"),
        # ...and its attacks.
        ("V0_baseline", "atk_host_dir_le_claim",
         _c("monostanza sc 2p", 28.0, "<=", "m2", "28 m² (2 persons)"), "REJECT"),
        ("V5_direction_stripped", "mut_host_dir_stripped",
         _c("monostanza sc 2p", 28.0, ">=", "m2", "28 m² (2 persons)"), "REJECT"),
        # --- RED-TEAM ROUND 2 pins (poisoned-corpus enablers, each individually fixed) ---
        ("V6_conflicting_span", "mut_conflicting_span_never_binds",
         _c("monostanza 2p", 38.0, ">=", "mq",
            "non inferiore a mq 38 se per due persone. Nota: il numero degli occupanti "
            "non superiore a due"), "REJECT"),
        ("V7_min_token_decoy", "mut_min_time_token_no_direction",
         _c("monostanza sc 2p", 28.0, ">=", "m2", "28 m² (2 persons)"), "REJECT"),
        ("V8_same_value_max", "mut_same_value_max_occurrence",
         _c("nucleo surface", 28.0, ">=", "m2", "28 m² (2 persons) per nucleo di emergenza"),
         "REJECT"),
        ("V8_same_value_max", "mut_v8_naked_span_now_ambiguous",
         _c("monostanza sc 2p", 28.0, ">=", "m2", "28 m² (2 persons)"), "REJECT"),
        ("V8_same_value_max", "ok_v8_true_minimum_still_reachable",
         _c("monostanza sc 2p", 28.0, ">=", "m2", "/ 28 m² (2 persons)"), "ACCEPT"),
        ("V9_boundary_bleed", "mut_boundary_bleed_no_inherited_direction",
         _c("monostanza sc 2p", 28.0, ">=", "m2", "28 m² (2 persons)"), "REJECT"),
        ("V10_negated_gloss", "mut_negation_truncated_out_of_span",
         _c("accessory min height", 2.40, ">=", "m",
            "reducible to 2.40 m for corridors, circulation, bathrooms, WCs and store rooms"),
         "REJECT"),
        ("V11_gloss_scope_crossover", "mut_gloss_scope_crossover_no_anchor",
         _c("accessory min height", 2.40, ">=", "m",
            "reducible to 2.40 m under Salva-Casa 5-ter"), "REJECT"),
    ]


def _anchor_parity_row() -> dict:
    """Battery-time drift pin: the spike's hand-copied ANCHORS must equal the shipped gate's
    tables. Lazy import at battery time ONLY — validate_claim() itself never imports
    production code (isolation is preserved on the gate path)."""
    try:
        sys.path.insert(0, str(_SANDBOX))
        import parser as _p  # noqa: PLC0415
        shipped = {**_p._SOURCE_ANCHORS, **_p._MONOSTANZA_ANCHORS}
        ok = shipped == ANCHORS
        detail = "" if ok else f"drift keys: {sorted(k for k in set(shipped) | set(ANCHORS) if shipped.get(k) != ANCHORS.get(k))}"
    except Exception as exc:  # noqa: BLE001 — an unimportable parser is a parity failure, not a skip
        ok, detail = False, f"parser import failed: {exc}"
    return {"variant": "-", "case": "anchor_parity_vs_parser", "expected": "MATCH",
            "got": "MATCH" if ok else "DRIFT", "reason": "ANCHORS == parser tables" if ok else "ANCHOR_DRIFT",
            "detail": detail, "ok": ok}


def run_battery(raw: str) -> Tuple[int, int, List[dict]]:
    variants = battery_variants(raw)
    rows, mismatches = [], 0
    for variant, case_id, claim, expected in battery():
        v = validate_claim(claim, variants[variant])
        got = "ACCEPT" if v.accepted else "REJECT"
        ok = got == expected
        mismatches += 0 if ok else 1
        rows.append({"variant": variant, "case": case_id, "expected": expected,
                     "got": got, "reason": v.reason, "detail": v.detail, "ok": ok})
    parity = _anchor_parity_row()
    rows.append(parity)
    mismatches += 0 if parity["ok"] else 1
    return len(rows), mismatches, rows


# --- live Ollama loop --------------------------------------------------------------------
def ollama_extract(text: str, model: str) -> SpanClaims:
    import os
    import requests
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    resp = requests.post(
        f"{host}/api/chat",
        json={
            "model": model,
            "format": SpanClaims.model_json_schema(),
            "stream": False,
            "options": {"temperature": 0, "seed": 0, "top_k": 1, "num_ctx": 8192},
            "keep_alive": "30m",
            "messages": [{"role": "system", "content": SPIKE_PROMPT},
                         {"role": "user", "content": text}],
        },
        timeout=300,
    )
    resp.raise_for_status()
    return SpanClaims.model_validate_json(resp.json()["message"]["content"])


# Ground truth for the live loop: (anchor_key, value) pairs a claim may legitimately bind,
# per variant. Anything ACCEPTED outside this set is a FALSE ACCEPT (precision breach).
_V0_TRUTH = {("min_height_habitable_m", 2.70), ("min_height_accessory_m", 2.40),
             ("min_height_salva_casa_m", 2.40), ("aero_illuminating_ratio", 0.125),
             ("min_surface_monostanza_1p", 28.0), ("min_surface_monostanza_2p", 38.0),
             ("min_surface_monostanza_sc_1p", 20.0), ("min_surface_monostanza_sc_2p", 28.0)}
_LIVE_TRUTH = {
    "V0_baseline": _V0_TRUTH,
    # V1: the habitable anchor is decoy-shadowed -> NO habitable accept is legitimate.
    "V1_coastal_decoy_shadow": {p for p in _V0_TRUTH if p[0] != "min_height_habitable_m"},
    # V2: the aero sentence is a maximum now -> NO aero accept is legitimate.
    "V2_operator_manipulated": {p for p in _V0_TRUTH if p[0] != "aero_illuminating_ratio"},
    # V3: the habitable span is gone -> NO habitable accept is legitimate.
    "V3_habitable_span_deleted": {p for p in _V0_TRUTH if p[0] != "min_height_habitable_m"},
}


def run_live(raw: str, model: str) -> Tuple[int, int, int, List[dict]]:
    """Returns (claims, accepts, false_accepts, rows)."""
    variants = corpus_variants(raw)
    rows, n_claims, n_accepts, n_false = [], 0, 0, 0
    for vname, vtext in variants.items():
        claims = ollama_extract(vtext, model).claims
        truth = _LIVE_TRUTH[vname]
        for cl in claims:
            n_claims += 1
            v = validate_claim(cl, vtext)
            false_accept = False
            if v.accepted:
                n_accepts += 1
                false_accept = not any(k == v.anchor_key and abs(cl.value - val) <= _EQ_TOL
                                       for k, val in truth)
                n_false += 1 if false_accept else 0
            rows.append({"variant": vname, "metric": cl.metric, "value": cl.value,
                         "operator": cl.operator, "unit": cl.unit,
                         "span": cl.span[:100], "got": "ACCEPT" if v.accepted else "REJECT",
                         "reason": v.reason, "anchor": v.anchor_key,
                         "false_accept": false_accept})
    return n_claims, n_accepts, n_false, rows


# --- entry -------------------------------------------------------------------------------
def main(argv=None) -> int:
    _enforce_policy_anchor()
    try:  # Windows consoles may default to a legacy codepage
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="Track B span-quote gate spike (strategy §3.2.5)")
    ap.add_argument("--live", action="store_true", help="also run the live Ollama loop")
    ap.add_argument("--model", default="llama3.1:8b")
    ap.add_argument("--report", type=Path, default=None, help="write a JSON report here")
    args = ap.parse_args(argv)

    raw = CORPUS_PATH.read_text(encoding="utf-8")
    report: dict = {"policy_anchor": {"zero_human_coding_target": ZERO_HUMAN_CODING_TARGET,
                                      "zero_human_review_claimed": ZERO_HUMAN_REVIEW_CLAIMED}}

    total, mismatches, rows = run_battery(raw)
    report["battery"] = {"cases": total, "mismatches": mismatches, "rows": rows}
    print(f"== META-GATE BATTERY (deterministic, no LLM): {total} cases ==")
    for r in rows:
        flag = "ok " if r["ok"] else "XX "
        print(f"{flag} [{r['variant']}] {r['case']}: expected {r['expected']}, "
              f"got {r['got']} ({r['reason']})")
    print(f"-- battery: {total - mismatches}/{total} as expected")
    exit_code = 0 if mismatches == 0 else 1

    if args.live and exit_code == 0:
        print(f"\n== LIVE LOOP (Ollama {args.model}, temperature 0, seed 0) ==")
        n_claims, n_accepts, n_false, live_rows = run_live(raw, args.model)
        report["live"] = {"model": args.model, "claims": n_claims, "accepts": n_accepts,
                          "false_accepts": n_false, "rows": live_rows}
        for r in live_rows:
            mark = "FALSE-ACCEPT" if r["false_accept"] else r["got"]
            print(f"  [{r['variant']}] {r['metric']!r} {r['operator']} {r['value']} {r['unit']}"
                  f" -> {mark} ({r['reason']})")
        precision = 1.0 if n_accepts == 0 else (n_accepts - n_false) / n_accepts
        expected_v0 = len(_V0_TRUTH)
        recalled = len({(r["anchor"], r["value"]) for r in live_rows
                        if r["variant"] == "V0_baseline" and r["got"] == "ACCEPT"
                        and not r["false_accept"]})
        print(f"-- live: {n_claims} claims, {n_accepts} accepts, {n_false} FALSE ACCEPTS; "
              f"precision {precision:.3f}; V0 recall {recalled}/{expected_v0} "
              f"(recall is subordinate: rejections route to human triage)")
        if n_false:
            exit_code = 1

    if args.report:
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"report written: {args.report}")
    print(f"\nRESULT: {'PASS (zero false accepts)' if exit_code == 0 else 'FAIL'}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
