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


# =========================================================================================
# CORPUS-TRUST MODEL (ADR-014, closes the ADR-013 open item): sha256 manifest over rule
# corpora. The poisoned-corpus attack class red-teamed in ADR-013 assumed an attacker-
# authored statute file reaching the gate. The trust boundary is FILE INGESTION: every
# corpus file the CLIs read must hash-match research/corpus/manifest.json or the gate
# refuses to start. Hashing is over the NEWLINE-NORMALIZED utf-8 text (\r\n -> \n; a
# lone \r is deliberately NOT normalized — it changes the hash and fails closed) so
# git's platform-dependent eol conversion cannot invalidate a legitimate checkout.
# HONEST LIMITS, stated plainly: (a) the manifest is a HASH ALLOW-LIST, not a signature —
# an actor who can write the corpus can also rewrite the manifest; the audit boundary
# for that is git history/review, not this process; (b) validate_claim()/
# validate_vocab_claim() operate on TEXT and are deliberately callable with in-memory
# adversarial variants (the battery's V1-V13, the replay's C_*) — those are the
# harness's own attack simulations, derived AFTER a trusted load, inside the boundary.
# =========================================================================================
class UntrustedCorpusError(RuntimeError):
    """A corpus file failed the manifest check: altered, unlisted, or manifest missing."""


_REPO_ROOT = _SANDBOX.parent
MANIFEST_PATH = _REPO_ROOT / "research" / "corpus" / "manifest.json"


def corpus_sha256(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def load_trusted_corpus(path: Path, manifest_path: Path = None) -> str:
    """The ONLY sanctioned file-ingestion path for statute/rule corpora. FAIL-CLOSED:
    a missing manifest, an unlisted (unsigned) file, or a hash mismatch (altered) all
    raise UntrustedCorpusError before a single byte reaches the gate."""
    path = Path(path).resolve()
    mpath = Path(manifest_path) if manifest_path else MANIFEST_PATH
    if not mpath.exists():
        raise UntrustedCorpusError(
            f"corpus-trust manifest missing ({mpath}) — refusing to ingest ANY corpus "
            f"without a trust root (fail-closed)")
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    if manifest.get("algorithm") != "sha256":
        raise UntrustedCorpusError(f"unsupported manifest algorithm {manifest.get('algorithm')!r}")
    try:
        key = str(path.relative_to(_REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        key = str(path).replace("\\", "/")
    expected = manifest.get("trusted_corpora", {}).get(key)
    if expected is None:
        raise UntrustedCorpusError(
            f"corpus {key!r} is UNLISTED (unsigned: absent from {mpath.name}) — "
            f"refusing to ingest")
    text = path.read_text(encoding="utf-8")
    actual = corpus_sha256(text)
    if actual != expected:
        raise UntrustedCorpusError(
            f"corpus {key!r} is ALTERED: sha256 {actual} != manifest {expected} — "
            f"refusing to ingest (poisoned-corpus class, ADR-013)")
    return text


# =========================================================================================
# SELECTION-VOCABULARY GATE (strategy §3.2.4 gate type 6): non-numeric applicability
# tokens (room types) bind to ontology classes ONLY through the statute's own enumeration
# prose — verify-never-trust extended from numbers to vocabulary. The tables below are
# hand-copied from parser.py BY DESIGN (gate-path isolation) and diffed by the battery's
# parity pin, exactly like ANCHORS.
# =========================================================================================
class VocabClaim(BaseModel):
    """One LLM classification claim: token -> ontology class, citing a verbatim span."""

    token: str = Field(description="applicability token, e.g. 'corridoio'")
    ontology_class: str = Field(description="'accessory' (acc:AccessorySpace) — closed lexicon")
    span: str = Field(description="verbatim statute span containing the enumeration")


_SELECTION_ANCHOR = r"riducibile\s+a\s+m\s*\d+[.,]\d+\s+per\s+(.+?)[.»]"     # parser.py:416
# Span-local variant: a claim span is a FRAGMENT and legitimately ends where the claimant
# cut it, so end-of-string is an admissible terminator IN-SPAN ONLY. The corpus-wide
# derivation (_derive_enumeration) keeps the parser-parity pattern with its hard [.»]
# terminator — the parity pin diffs THAT one against parser.py.
_SELECTION_ANCHOR_SPAN = r"riducibile\s+a\s+m\s*\d+[.,]\d+\s+per\s+(.+?)(?:[.»]|$)"
_SELECTION_STOPWORDS = frozenset({"i", "in", "genere", "ed"})                # parser.py:418
_ART1_ENUMERATION = frozenset({"corridoi", "disimpegni", "bagni", "gabinetti", "ripostigli"})
# Closed class lexicon: the Art.1 enumeration maps to exactly one ontology class.
_VOCAB_CLASSES = {"accessory": "acc:AccessorySpace"}
# CLOSED INFLECTION LEXICON (red-team blocker fix): bare vowel-run stem-equality admits
# invented colliders ('bagnio', 'corridoia', 'gabinetta' all stem-equal real terms). The
# spike's tokens are LLM-extracted UNTRUSTED input (unlike production, where tokens come
# from the integrity-pinned applicability.json), so stem-equality alone is not enough
# here: after the stem matches, the token must ALSO be one of the term's closed admissible
# inflections (plural / regular singular / the table's canonical truncated hint). This is
# a spike-layer ADDITION on top of the parity-pinned stem semantics — parser.py's own
# _it_stem/stem-equality are untouched (their tokens are table-pinned, not attacker-
# reachable); a coordinated production hardening is recorded in ADR-014 as follow-up.
_TERM_INFLECTIONS = {
    "corridoi":   frozenset({"corridoi", "corridoio", "corrid"}),
    "disimpegni": frozenset({"disimpegni", "disimpegno", "disimpegn"}),
    "bagni":      frozenset({"bagni", "bagno", "bagn"}),
    "gabinetti":  frozenset({"gabinetti", "gabinetto", "gabinett"}),
    "ripostigli": frozenset({"ripostigli", "ripostiglio", "ripostigl"}),
}


def _it_stem(token: str) -> str:
    """parser.py:423-429 verbatim semantics: strip the trailing inflection-vowel run."""
    return re.sub(r"[aeiou]+$", "", (token or "").lower())


def _termset_from_capture(captured: str) -> frozenset:
    toks = [t for t in re.split(r"[^a-zàèéìòù]+", captured.lower()) if t]
    return frozenset(t for t in toks
                     if t not in _SELECTION_STOPWORDS and len(_it_stem(t)) >= 3)


def _derive_enumeration(corpus: str):
    """(termset, error) — unique-or-reject re-derivation of the Art.1 enumeration from the
    answer-key-excluded prose; drift from the pinned 5-set is itself a rejection."""
    spans = re.findall(_SELECTION_ANCHOR, _demark(corpus), re.S | re.I)
    termsets = {_termset_from_capture(s) for s in spans}
    if not termsets:
        return None, ("REJECT_ENUM_ABSENT", "the Art.1 reduced-height enumeration is absent "
                                            "from the statute prose — no backfill")
    if len(termsets) > 1:
        return None, ("REJECT_ENUM_AMBIGUOUS",
                      f"the enumeration anchor matches multiple distinct term-sets "
                      f"{sorted(sorted(s) for s in termsets)} (duplicate/shadow injection)")
    enumeration = next(iter(termsets))
    if enumeration != _ART1_ENUMERATION:
        return None, ("REJECT_ENUM_DRIFT",
                      f"statute enumeration {sorted(enumeration)} drifted from the pinned "
                      f"Art.1 5-set {sorted(_ART1_ENUMERATION)}")
    return enumeration, None


def validate_vocab_claim(claim: VocabClaim, corpus_raw: str) -> Verdict:
    """The vocabulary protocol: V-L1 span fidelity -> V-L2 enumeration re-derivation
    (unique + drift-pinned) -> V-L3 stem-EQUALITY token binding (never prefix) ->
    V-L4 closed class lexicon. Any miss REJECTS to human triage."""
    _enforce_policy_anchor()
    corpus = crosscheck_corpus(corpus_raw)
    span_norm = _norm(claim.span)
    if not span_norm or not (claim.token or "").strip():
        return Verdict.reject("REJECT_MALFORMED", "empty span or token")

    # V-L1 — span fidelity: verbatim, exactly once (answer-key excluded).
    n = _norm(corpus).count(span_norm)
    if n == 0:
        return Verdict.reject("REJECT_SPAN_NOT_FOUND",
                              "span is not a verbatim substring of the statute corpus")
    if n > 1:
        return Verdict.reject("REJECT_SPAN_NOT_UNIQUE", f"span occurs {n} times")
    # The span itself must carry the enumeration anchor and yield the SAME termset the
    # corpus yields (in-span/corpus agreement, mirroring the numeric L3 two-level check).
    m = re.search(_SELECTION_ANCHOR_SPAN, _demark(claim.span), re.S | re.I)
    if not m:
        return Verdict.reject("REJECT_NO_ANCHOR",
                              "span does not carry the Art.1 enumeration lead-in "
                              "('riducibile a m X per ...')")
    span_terms = _termset_from_capture(m.group(1))

    # V-L2 — corpus-wide enumeration re-derivation (unique-or-reject, drift-pinned).
    enumeration, err = _derive_enumeration(corpus)
    if err:
        return Verdict.reject(*err)
    if span_terms != enumeration:
        return Verdict.reject("REJECT_SPAN_ENUM_MISMATCH",
                              f"span termset {sorted(span_terms)} != corpus enumeration "
                              f"{sorted(enumeration)}")

    # V-L3 — stem-EQUALITY binding (parser.py:469-499 semantics): empty stems never
    # anchor; truncations ('bag') and extensions ('bagno_decoy') do not stem-equal.
    stem = _it_stem(claim.token)
    if not stem:
        return Verdict.reject("REJECT_EMPTY_STEM",
                              f"token {claim.token!r} has an empty stem — never anchors")
    term = next((t for t in sorted(enumeration) if _it_stem(t) == stem), None)
    if term is None:
        return Verdict.reject("REJECT_TOKEN_UNANCHORED",
                              f"token {claim.token!r} (stem {stem!r}) stem-equals no Art.1 "
                              f"enumerated term — NO-INVENT: an unanchored token is never "
                              f"certified (cross-lingual synonyms stay declared debt)")
    if claim.token.strip().lower() not in _TERM_INFLECTIONS.get(term, frozenset()):
        return Verdict.reject("REJECT_TOKEN_INFLECTION",
                              f"token {claim.token!r} stem-collides with {term!r} but is not "
                              f"one of its closed admissible inflections "
                              f"{sorted(_TERM_INFLECTIONS.get(term, ()))} — invented "
                              f"vowel-run colliders never bind (red-teamed)")

    # V-L4 — closed class lexicon: the Art.1 enumeration maps to exactly one class.
    if claim.ontology_class not in _VOCAB_CLASSES:
        return Verdict.reject("REJECT_CLASS_POLICY",
                              f"class {claim.ontology_class!r} outside the closed lexicon "
                              f"{sorted(_VOCAB_CLASSES)} for enumeration-bound tokens")

    return Verdict(True, "ACCEPT",
                   f"token {claim.token!r} anchored to statute term {term!r} -> "
                   f"{_VOCAB_CLASSES[claim.ontology_class]}", f"vocab:{term}")


# =========================================================================================
# SHACL COMPILE-PATH EMITTER: gate-verified parameters -> production-shaped Turtle.
# FAIL-CLOSED EMISSION: refuses unless ALL four numeric keys verified AND the vocabulary
# gate verified the full enumeration. Output mirrors sandbox/ontology/dm1975_salvacasa.ttl
# (stable *_PS URIs, sh:minCount 1 + sh:maxCount 1, xsd:decimal bars via Decimal(str(v)) —
# the ADR-008a exact-at-bar lesson — value-carrying sh:message regenerated from the live
# value per ADR-008, rdfs:seeAlso provenance anchors) so orchestrator.load_shacl_shapes'
# guard set accepts it unchanged.
# =========================================================================================
class EmitRefusedError(RuntimeError):
    """Emission refused: incomplete/unverified inputs can never become a rule pack."""


def _corpus_bar_decimal(corpus: str, key: str):
    """The statute's OWN lexical value for an anchored key, as an exact Decimal
    (unique-or-None over the demarked, answer-key-excluded corpus — same discipline as
    _anchor_values, but preserving the lexical form: '2,70' -> Decimal('2.70'))."""
    from decimal import Decimal as _D
    found = re.findall(ANCHORS[key], _demark(crosscheck_corpus(corpus)), re.S | re.I)
    if key == "aero_illuminating_ratio":
        vals = {_D(a) / _D(b) for a, b in found}
    else:
        vals = {_D(str(g).replace(",", ".")) for g in found}
    return next(iter(vals)) if len(vals) == 1 else None


_EMIT_KEYS = ("min_height_habitable_m", "min_height_accessory_m",
              "min_height_salva_casa_m", "aero_illuminating_ratio")
_EMIT_SEEALSO = {
    "MinHeightHabitable_PS": "legal:DM_1975_Abitabilita",
    "MinHeightAccessory_PS": "legal:DM_1975_Abitabilita",
    "MinHeightSalvaCasa_PS": "legal:DPR380_art24_SalvaCasa",
    "MinAeroRatio_PS": "legal:DM_1975_Abitabilita",
}
_EMIT_PATHS = {
    "MinHeightHabitable_PS": "acc:heightM", "MinHeightAccessory_PS": "acc:heightM",
    "MinHeightSalvaCasa_PS": "acc:heightM", "MinAeroRatio_PS": "acc:aeroRatio",
}


def emit_shacl(verified: dict, vocab: dict, corpus_text: str) -> str:
    """Serialize gate-verified thresholds + vocabulary into loadable SHACL Turtle.

    `verified`: {the 4 numeric keys: value} — every key mandatory, values finite and > 0.
    `vocab`:    validate_vocab_claim-shaped result set: {'enumeration': [5 terms],
                'anchored': {token: term}} — the full pinned 5-set mandatory.
    `corpus_text`: the trusted corpus the values were verified against; its sha256 is
                embedded as emission provenance."""
    import math
    missing = [k for k in _EMIT_KEYS if k not in verified]
    if missing:
        raise EmitRefusedError(f"emission refused: unverified/missing keys {missing} "
                               f"(all four numeric thresholds must pass the gate)")
    for k, v in verified.items():
        if not isinstance(v, (int, float)) or isinstance(v, bool) \
                or not math.isfinite(v) or v <= 0:
            raise EmitRefusedError(f"emission refused: {k} carries a non-finite/non-positive "
                                   f"value {v!r}")
    # NUMERIC RE-VALIDATION against the corpus (red-team fix: emission previously took
    # `verified` on faith while re-checking only the vocabulary — the asymmetry let
    # statute-contradicting bars and mutated corpora emit with a FALSE provenance hash).
    # Each bar is re-derived from the corpus's own anchor (unique-or-refuse) and the
    # EMITTED lexical form is the STATUTE's ('2,70' -> Decimal('2.70')), so caller-side
    # float drift (2.6999999999999997) normalizes to the statutory precision instead of
    # leaking into a legal bar or an operator-facing message.
    dec = {}
    for k in _EMIT_KEYS:
        bar = _corpus_bar_decimal(corpus_text, k)
        if bar is None:
            raise EmitRefusedError(f"emission refused: the corpus anchor for {k} is absent "
                                   f"or ambiguous — a deleted/decoy-shadowed corpus can "
                                   f"never become a rule pack")
        if abs(float(bar) - float(verified[k])) > _EQ_TOL:
            raise EmitRefusedError(f"emission refused: verified[{k}]={verified[k]!r} "
                                   f"contradicts the corpus anchor value {bar} — refusing "
                                   f"to attest unverifiable numbers")
        dec[k] = bar                                   # the STATUTE's lexical form is emitted
    enum = sorted(vocab.get("enumeration") or [])
    if frozenset(enum) != _ART1_ENUMERATION:
        raise EmitRefusedError(f"emission refused: vocabulary enumeration {enum} is not the "
                               f"gate-pinned Art.1 5-set {sorted(_ART1_ENUMERATION)}")
    for token in (vocab.get("anchored") or {}):
        v = validate_vocab_claim(
            VocabClaim(token=token, ontology_class="accessory",
                       span="riducibile a **m 2,40** per i corridoi, i disimpegni in genere, "
                            "i bagni, i gabinetti ed i ripostigli"), corpus_text)
        if not v.accepted:
            raise EmitRefusedError(f"emission refused: vocabulary token {token!r} failed the "
                                   f"selection gate ({v.reason}: {v.detail})")

    # Lazy import of the RULES-side templates (single source for messages; the validation
    # gate path above never imports production code — emission is compile-path).
    sys.path.insert(0, str(_SANDBOX))
    import orchestrator as _orch
    msg = {ps: tmpl.format(v=dec[attr])
           for ps, attr, tmpl in _orch._THRESHOLD_SLOTS}
    slot_attr = {ps: attr for ps, attr, _t in _orch._THRESHOLD_SLOTS}
    enum_it = ", ".join(enum)

    lines = [
        "# AUTO-EMITTED by sandbox/gate_spike.py emit_shacl() — span-quote-gate-verified "
        "parameters.",
        f"# emission provenance: corpus sha256 {corpus_sha256(corpus_text)}; "
        f"gate: 4 numeric keys + {len(enum)}-term Art.1 enumeration, all verified.",
        "# Structure mirrors sandbox/ontology/dm1975_salvacasa.ttl (ADR-008/008a contracts).",
        "",
        "@prefix sh:    <http://www.w3.org/ns/shacl#> .",
        "@prefix xsd:   <http://www.w3.org/2001/XMLSchema#> .",
        "@prefix rdfs:  <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix acc:   <https://acc.local/ontology#> .",
        "@prefix legal: <https://acc.local/legal#> .",
        "",
        "acc:EvaluatedSpace a rdfs:Class ;",
        '    rdfs:comment "An IfcSpace materialized for legal evaluation." .',
        "",
        "acc:AccessorySpace a rdfs:Class ;",
        "    rdfs:subClassOf acc:EvaluatedSpace ;",
        f'    rdfs:comment "Accessory room — gate-verified DM 1975 art.1 enumeration: '
        f'{enum_it}. Lower height bar; the aero rule does NOT apply." .',
        "",
        "acc:HabitableBaselineSpace a rdfs:Class ;",
        "    rdfs:subClassOf acc:EvaluatedSpace ;",
        '    rdfs:comment "Habitable (or unknown = strict complement) under the ordinary '
        'DM 1975 regime." .',
        "",
        "acc:HabitableSalvaCasaSpace a rdfs:Class ;",
        "    rdfs:subClassOf acc:EvaluatedSpace ;",
        '    rdfs:comment "Habitable (or unknown) under the Salva Casa derogation '
        '(DPR 380/2001 art.24 c.5-bis; c.5-ter conditions operator-asserted)." .',
        "",
        "legal:NormativeProvision a rdfs:Class .",
        "legal:DM_1975_Abitabilita a legal:NormativeProvision ;",
        '    rdfs:label "D.M. 5 luglio 1975 (altezze minime e requisiti igienico-sanitari)" .',
        "legal:DPR380_art24_SalvaCasa a legal:NormativeProvision ;",
        '    rdfs:label "DPR 380/2001 art. 24 commi 5-bis/5-ter (Salva Casa)" .',
        "",
    ]
    for ps in ("MinHeightHabitable_PS", "MinHeightAccessory_PS",
               "MinHeightSalvaCasa_PS", "MinAeroRatio_PS"):
        lines += [
            f"legal:{ps} a sh:PropertyShape ;",
            f"    sh:path {_EMIT_PATHS[ps]} ;",
            "    sh:minCount 1 ;",
            "    sh:maxCount 1 ;",
            f"    sh:minInclusive {format(dec[slot_attr[ps]], 'f')} ;",
            f'    sh:message "{msg[ps]}" ;',
            f"    rdfs:seeAlso {_EMIT_SEEALSO[ps]} .",
            "",
        ]
    lines += [
        "legal:AccessoryShape a sh:NodeShape ;",
        "    sh:targetClass acc:AccessorySpace ;",
        "    sh:property legal:MinHeightAccessory_PS .",
        "",
        "legal:HabitableBaselineShape a sh:NodeShape ;",
        "    sh:targetClass acc:HabitableBaselineSpace ;",
        "    sh:property legal:MinHeightHabitable_PS ;",
        "    sh:property legal:MinAeroRatio_PS .",
        "",
        "legal:HabitableSalvaCasaShape a sh:NodeShape ;",
        "    sh:targetClass acc:HabitableSalvaCasaSpace ;",
        "    sh:property legal:MinHeightSalvaCasa_PS ;",
        "    sh:property legal:MinAeroRatio_PS .",
        "",
    ]
    return "\n".join(lines)


_EMIT_WIRING = {
    "AccessoryShape": ("AccessorySpace", frozenset({"MinHeightAccessory_PS"})),
    "HabitableBaselineShape": ("HabitableBaselineSpace",
                               frozenset({"MinHeightHabitable_PS", "MinAeroRatio_PS"})),
    "HabitableSalvaCasaShape": ("HabitableSalvaCasaSpace",
                                frozenset({"MinHeightSalvaCasa_PS", "MinAeroRatio_PS"})),
}


def verify_emitted_shapes(ttl_text: str, verified: dict) -> bool:
    """TWO-STAGE tamper verification (red-teamed: the production loader RE-PARAMETERIZES
    sh:minInclusive from `verified`, so checking only the loaded graph is tautological —
    a tampered emitted bar would verify green against its own overwrite).

    Stage 1 — RAW-GRAPH audit of the emitted text itself: per property shape, the raw
    sh:minInclusive literal must numerically equal the gate-verified value (tolerance
    1e-9 — emission normalizes to the statute's lexical form), sh:path must be the pinned
    path, sh:minCount >= 1 and sh:maxCount == 1 must be present; per node shape, the
    sh:targetClass and the EXACT sh:property wiring must match (AccessoryShape must NOT
    carry the aero shape; both habitable shapes must).
    Stage 2 — the production loader's own ADR-008a guard set on top.
    Raises EmitRefusedError / ValueError on any miss."""
    import tempfile
    from decimal import Decimal as _D
    from types import SimpleNamespace
    from rdflib import Graph, Namespace
    sys.path.insert(0, str(_SANDBOX))
    import orchestrator as _orch
    SH, LEGAL = _orch.SH, _orch.LEGAL
    ACC = Namespace("https://acc.local/ontology#")
    path_uri = {"acc:heightM": ACC["heightM"], "acc:aeroRatio": ACC["aeroRatio"]}

    g = Graph()
    g.parse(data=ttl_text, format="turtle")            # parse error -> fail-closed
    slot_attr = {ps: attr for ps, attr, _t in _orch._THRESHOLD_SLOTS}
    for ps_name, attr in slot_attr.items():
        ps = LEGAL[ps_name]
        raw = g.value(ps, SH.minInclusive)
        if raw is None:
            raise EmitRefusedError(f"emitted TTL: {ps_name} has no raw sh:minInclusive")
        if abs(_D(str(raw)) - _D(str(float(verified[attr])))) > _D("1e-9"):
            raise EmitRefusedError(f"emitted bar TAMPER for {ps_name}: raw literal {raw} "
                                   f"!= gate-verified {verified[attr]!r}")
        mc = g.value(ps, SH.minCount)
        if mc is None or int(mc) < 1:
            raise EmitRefusedError(f"emitted TTL: {ps_name} missing sh:minCount >= 1")
        xc = g.value(ps, SH.maxCount)
        if xc is None or int(xc) != 1:
            raise EmitRefusedError(f"emitted TTL: {ps_name} missing sh:maxCount 1")
        if g.value(ps, SH.path) != path_uri[_EMIT_PATHS[ps_name]]:
            raise EmitRefusedError(f"emitted TTL: {ps_name} sh:path TAMPER "
                                   f"({g.value(ps, SH.path)})")
    for shape, (target, props) in _EMIT_WIRING.items():
        node = LEGAL[shape]
        if g.value(node, SH.targetClass) != ACC[target]:
            raise EmitRefusedError(f"emitted TTL: {shape} targetClass mismatch")
        got = {p for p in g.objects(node, SH.property)}
        if got != {LEGAL[p] for p in props}:
            raise EmitRefusedError(f"emitted TTL: {shape} property WIRING mismatch "
                                   f"(fail-open/fail-spurious risk): {sorted(str(x) for x in got)}")

    thr = SimpleNamespace(**{k: verified[k] for k in _EMIT_KEYS})
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "emitted.ttl"
        p.write_text(ttl_text, encoding="utf-8")
        _orch.load_shacl_shapes(thr, path=str(p))       # ADR-008a guards on top
    return True


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
    # Vocabulary-gate mutations (the test_gate.py:264-272 / :299-307 corpus surgeries, verbatim):
    v12 = raw.replace(
        "riducibile a **m 2,40** per i corridoi, i disimpegni in genere, i bagni,", "") \
        .replace("i gabinetti ed i ripostigli", "")
    assert v12 != raw, "V12 enumeration deletion point not found"
    v13 = raw.replace(
        "i gabinetti ed i ripostigli.»",
        "i gabinetti ed i ripostigli.»\n> Inoltre riducibile a m 2,40 per i garage e le cantine.»",
        1)
    assert v13 != raw, "V13 duplicate-enumeration injection point not found"
    out["V12_enum_deleted"] = v12          # Art.1 enumeration prose removed
    out["V13_enum_duplicated"] = v13       # second, divergent 'riducibile ... per' term-set
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
    """Battery-time drift pin: the spike's hand-copied ANCHORS *and* selection tables must
    equal the shipped gate's. Lazy import at battery time ONLY — validate_claim() itself
    never imports production code (isolation is preserved on the gate path)."""
    try:
        sys.path.insert(0, str(_SANDBOX))
        import parser as _p  # noqa: PLC0415
        shipped = {**_p._SOURCE_ANCHORS, **_p._MONOSTANZA_ANCHORS}
        drift = [k for k in set(shipped) | set(ANCHORS) if shipped.get(k) != ANCHORS.get(k)]
        if _SELECTION_ANCHOR != _p._ACCESSORY_SELECTION_ANCHOR:
            drift.append("_SELECTION_ANCHOR")
        if _SELECTION_STOPWORDS != _p._IT_SELECTION_STOPWORDS:
            drift.append("_SELECTION_STOPWORDS")
        if _ART1_ENUMERATION != _p._ART1_ENUMERATION:
            drift.append("_ART1_ENUMERATION")
        stem_probe = ("corridoi", "corrid", "disimpegno", "disimpegni", "bagno", "bagni",
                      "gabinetti", "ripostiglio", "ripostigli", "i", "bag", "bagno_decoy")
        if any(_it_stem(t) != _p._it_stem(t) for t in stem_probe):
            drift.append("_it_stem")
        ok = not drift
        detail = "" if ok else f"drift keys: {sorted(drift)}"
    except Exception as exc:  # noqa: BLE001 — an unimportable parser is a parity failure, not a skip
        ok, detail = False, f"parser import failed: {exc}"
    return {"variant": "-", "case": "anchor_parity_vs_parser", "expected": "MATCH",
            "got": "MATCH" if ok else "DRIFT", "reason": "ANCHORS == parser tables" if ok else "ANCHOR_DRIFT",
            "detail": detail, "ok": ok}


def _vc(token, ontology_class, span) -> VocabClaim:
    return VocabClaim(token=token, ontology_class=ontology_class, span=span)


def vocab_battery() -> List[Tuple[str, str, VocabClaim, str]]:
    """(variant, case_id, vocab_claim, expected) — the selection-vocabulary ground truth,
    mirroring the 8 historical test_gate.py selection pins at claim level."""
    S = _SPAN_ACCESSORY
    return [
        # The 4 art1 tokens anchor across singular/plural stem drift (accepts).
        ("V0_baseline", "vok_corrid", _vc("corrid", "accessory", S), "ACCEPT"),
        ("V0_baseline", "vok_disimpegno_drift", _vc("disimpegno", "accessory", S), "ACCEPT"),
        ("V0_baseline", "vok_bagno_drift", _vc("bagno", "accessory", S), "ACCEPT"),
        ("V0_baseline", "vok_ripostiglio_drift", _vc("ripostiglio", "accessory", S), "ACCEPT"),
        # Fabricated / truncated / extended / empty-stem tokens (rejects).
        ("V0_baseline", "vatk_fabricated_garage", _vc("garage", "accessory", S), "REJECT"),
        ("V0_baseline", "vatk_fabricated_cucina", _vc("cucina", "accessory", S), "REJECT"),
        ("V0_baseline", "vatk_truncated_bag", _vc("bag", "accessory", S), "REJECT"),
        ("V0_baseline", "vatk_extended_bagno_decoy", _vc("bagno_decoy", "accessory", S), "REJECT"),
        ("V0_baseline", "vatk_empty_stem_article", _vc("i", "accessory", S), "REJECT"),
        # Decoy strings as tokens (rejects).
        ("V0_baseline", "vatk_decoy_montani", _vc("montani", "accessory", S), "REJECT"),
        ("V0_baseline", "vatk_decoy_monostanza", _vc("alloggio monostanza", "accessory", S), "REJECT"),
        ("V0_baseline", "vatk_decoy_seismic", _vc("seismic", "accessory", S), "REJECT"),
        # Class policy + span fidelity (rejects).
        ("V0_baseline", "vatk_wrong_class", _vc("corrid", "habitable", S), "REJECT"),
        ("V0_baseline", "vatk_answer_key_echo",
         _vc("corrid", "accessory", "exclude corridoi/bagni/ripostigli"), "REJECT"),
        ("V0_baseline", "vatk_paraphrase_span",
         _vc("corrid", "accessory", "riducibile per i corridoi e i bagni"), "REJECT"),
        # Corpus mutations (rejects — deleted / duplicate-injected enumeration).
        ("V12_enum_deleted", "vmut_enum_deleted", _vc("corrid", "accessory", S), "REJECT"),
        ("V13_enum_duplicated", "vmut_enum_duplicated", _vc("corrid", "accessory", S), "REJECT"),
        # Stem-collision colliders (red-team blocker: invented vowel-run variants of real
        # terms stem-equal them; the closed inflection lexicon must refuse every one).
        ("V0_baseline", "vatk_collider_bagnio", _vc("bagnio", "accessory", S), "REJECT"),
        ("V0_baseline", "vatk_collider_corridoia", _vc("corridoia", "accessory", S), "REJECT"),
        ("V0_baseline", "vatk_collider_gabinetta", _vc("gabinetta", "accessory", S), "REJECT"),
        ("V0_baseline", "vatk_collider_disimpegnu", _vc("disimpegnu", "accessory", S), "REJECT"),
        # ...while the genuine singular/plural/hint inflections still bind.
        ("V0_baseline", "vok_inflection_gabinetto", _vc("gabinetto", "accessory", S), "ACCEPT"),
    ]


def _trust_and_emit_rows(raw: str) -> List[dict]:
    """Structural battery rows for the corpus-trust model and the SHACL emitter."""
    import tempfile
    rows = []

    def row(case, ok, reason, detail=""):
        rows.append({"variant": "-", "case": case, "expected": "PASS",
                     "got": "PASS" if ok else "FAIL", "reason": reason,
                     "detail": detail, "ok": ok})

    # --- corpus trust ---
    try:
        trusted = load_trusted_corpus(CORPUS_PATH)
        row("trust_manifest_accepts_shipped_corpus", trusted == raw,
            "sha256 matches manifest")
    except Exception as exc:  # noqa: BLE001
        row("trust_manifest_accepts_shipped_corpus", False, "UNEXPECTED", str(exc))
    with tempfile.TemporaryDirectory() as d:
        tampered = Path(d) / "dm_1975_salva_casa.md"
        tampered.write_text(raw.replace("m 2,70", "m 2,10"), encoding="utf-8")
        try:
            load_trusted_corpus(tampered)
            row("trust_tampered_corpus_refused", False, "ACCEPTED_TAMPERED")
        except UntrustedCorpusError as exc:
            row("trust_tampered_corpus_refused", True, "UntrustedCorpusError",
                str(exc)[:80])
        unsigned = Path(d) / "unsigned_statute.md"
        unsigned.write_text(raw, encoding="utf-8")
        try:
            load_trusted_corpus(unsigned)
            row("trust_unsigned_corpus_refused", False, "ACCEPTED_UNSIGNED")
        except UntrustedCorpusError as exc:
            row("trust_unsigned_corpus_refused", True, "UntrustedCorpusError", str(exc)[:80])

    # --- emitter ---
    verified = {"min_height_habitable_m": 2.70, "min_height_accessory_m": 2.40,
                "min_height_salva_casa_m": 2.40, "aero_illuminating_ratio": 0.125}
    vocab = {"enumeration": sorted(_ART1_ENUMERATION),
             "anchored": {"corrid": "corridoi", "disimpegno": "disimpegni",
                          "bagno": "bagni", "ripostiglio": "ripostigli"}}
    try:
        ttl = emit_shacl(verified, vocab, raw)
        loaded = verify_emitted_shapes(ttl, verified)
        terms_ok = all(t in ttl for t in _ART1_ENUMERATION)
        row("emit_loads_via_production_loader", bool(loaded) and terms_ok,
            "load_shacl_shapes OK + all 5 enumeration terms present",
            "" if terms_ok else "enumeration terms missing from emitted TTL")
    except Exception as exc:  # noqa: BLE001
        row("emit_loads_via_production_loader", False, "UNEXPECTED", str(exc))
    try:
        emit_shacl({k: v for k, v in verified.items()
                    if k != "min_height_salva_casa_m"}, vocab, raw)
        row("emit_refuses_incomplete_thresholds", False, "EMITTED_INCOMPLETE")
    except EmitRefusedError:
        row("emit_refuses_incomplete_thresholds", True, "EmitRefusedError")
    try:
        bad_vocab = {"enumeration": sorted(_ART1_ENUMERATION),
                     "anchored": {**vocab["anchored"], "garage": "garage"}}
        emit_shacl(verified, bad_vocab, raw)
        row("emit_refuses_fabricated_vocab_token", False, "EMITTED_FABRICATED")
    except EmitRefusedError:
        row("emit_refuses_fabricated_vocab_token", True, "EmitRefusedError")
    try:
        ttl = emit_shacl(verified, vocab, raw)
        stripped = "\n".join(l for l in ttl.splitlines() if "sh:minCount" not in l)
        try:
            verify_emitted_shapes(stripped, verified)
            row("emit_tampered_ttl_refused_by_loader", False, "LOADED_MINCOUNT_STRIPPED")
        except (ValueError, EmitRefusedError):
            row("emit_tampered_ttl_refused_by_loader", True,
                "loader raised on minCount-stripped TTL (ADR-008a guard)")
    except Exception as exc:  # noqa: BLE001
        row("emit_tampered_ttl_refused_by_loader", False, "UNEXPECTED", str(exc))

    # Red-team round 3 pins: the tamper classes the tautological verifier missed.
    try:
        ttl = emit_shacl(verified, vocab, raw)
        cases = [
            ("emit_bar_tamper_refused",
             ttl.replace("sh:minInclusive 2.70 ;", "sh:minInclusive 2.10 ;", 1)),
            ("emit_wiring_tamper_refused",
             ttl.replace("    sh:property legal:MinHeightHabitable_PS ;\n"
                         "    sh:property legal:MinAeroRatio_PS .",
                         "    sh:property legal:MinHeightHabitable_PS .", 1)),
            ("emit_path_swap_refused",
             ttl.replace("sh:path acc:aeroRatio", "sh:path acc:heightM", 1)),
        ]
        for case_id, tampered in cases:
            if tampered == ttl:
                row(case_id, False, "TAMPER_NOT_APPLIED")
                continue
            try:
                verify_emitted_shapes(tampered, verified)
                row(case_id, False, "TAMPER_VERIFIED_GREEN")
            except (ValueError, EmitRefusedError) as exc:
                row(case_id, True, "refused", str(exc)[:80])
    except Exception as exc:  # noqa: BLE001
        row("emit_bar_tamper_refused", False, "UNEXPECTED", str(exc))
    # Caller-side float drift normalizes to the STATUTE's lexical bar (never leaks).
    try:
        drift = dict(verified, min_height_habitable_m=2.6999999999999997)
        ttl = emit_shacl(drift, vocab, raw)
        ok = "sh:minInclusive 2.70 ;" in ttl and "2.6999999999999997" not in ttl
        verify_emitted_shapes(ttl, drift)
        row("emit_normalizes_float_drift", ok,
            "bar emitted as statutory lexical 2.70; drift never reaches the artifact")
    except Exception as exc:  # noqa: BLE001
        row("emit_normalizes_float_drift", False, "UNEXPECTED", str(exc))
    # A corpus the numeric gate rejects (deleted / decoy-shadowed) can never emit.
    variants = battery_variants(raw)
    for case_id, vkey in (("emit_refuses_deleted_corpus", "V3_habitable_span_deleted"),
                          ("emit_refuses_shadowed_corpus", "V1_coastal_decoy_shadow")):
        try:
            emit_shacl(verified, vocab, variants[vkey])
            row(case_id, False, "EMITTED_FROM_REJECTED_CORPUS")
        except EmitRefusedError as exc:
            row(case_id, True, "EmitRefusedError", str(exc)[:80])
    return rows


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
    for variant, case_id, vclaim, expected in vocab_battery():
        v = validate_vocab_claim(vclaim, variants[variant])
        got = "ACCEPT" if v.accepted else "REJECT"
        ok = got == expected
        mismatches += 0 if ok else 1
        rows.append({"variant": variant, "case": case_id, "expected": expected,
                     "got": got, "reason": v.reason, "detail": v.detail, "ok": ok})
    for r in _trust_and_emit_rows(raw):
        rows.append(r)
        mismatches += 0 if r["ok"] else 1
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

    # Corpus-trust boundary: the CLI ingests statute files ONLY through the manifest check.
    raw = load_trusted_corpus(CORPUS_PATH)
    report: dict = {"policy_anchor": {"zero_human_coding_target": ZERO_HUMAN_CODING_TARGET,
                                      "zero_human_review_claimed": ZERO_HUMAN_REVIEW_CLAIMED},
                    "corpus_sha256": corpus_sha256(raw)}

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
