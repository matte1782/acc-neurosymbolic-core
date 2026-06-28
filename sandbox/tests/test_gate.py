#!/usr/bin/env python3
"""Verifier self-test for the Stage-2 VALIDATION GATE (parser.verify_rule_against_text).

100% offline, no Ollama: we mock the model's reply (a `Rule`) and assert the gate ACCEPTS a
faithful extraction and REJECTS fabricated / decoy / swapped / partial / deleted-source ones.
This is the positive-and-negative control that keeps the gate non-vacuous.

Run either way:
    python test_gate.py        # plain asserts, prints PASS/FAIL, exit 1 on any failure
    pytest test_gate.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # import sandbox/parser.py

import parser as P  # noqa: E402
from parser import (  # noqa: E402
    Clause, Operator, Rule, ValidationGateError,
    parse_rule, verify_rule_against_text, verify_accessory_selection_against_text,
    verify_monostanza_against_text,
)

LAW = (Path(__file__).resolve().parents[1] / "rules" / "dm_1975_salva_casa.md").read_text(
    encoding="utf-8"
)

# Stage 4 Part 3: source the accessory token groups from the SAME declarative table the checker
# reads (rules/applicability.json), the dependency-free way (stdlib json, NO `import checker` —
# checker's module-top `import ifcopenshell` sys.exits without the wheel, which would turn this
# parser-only, IFC-free gate suite RED on any box lacking it). This also keeps the test tracking
# the table rather than a hand-copied literal. _ART1_GROUP = the art1-provenance hints (must anchor
# to DM-1975 Art.1); _DEBT_GROUP = the cross-lingual-glossary synonyms (declared, unanchored named
# debt — baseline §7).
_APPLIC = json.loads(
    (Path(__file__).resolve().parents[1] / "rules" / "applicability.json").read_text(
        encoding="utf-8"))
_ACC_GROUPS = _APPLIC["occupancy_classes"]["accessory"]["hint_groups"]
_ART1_GROUP = [g["hints"] for g in _ACC_GROUPS if g["provenance"] == "art1"][0]
_DEBT_GROUP = [g["hints"] for g in _ACC_GROUPS if g["provenance"] == "cross-lingual-glossary"][0]

# Verbatim source spans (the gate normalises '**2,40**' -> '2.40').
_HAB = "L'altezza minima interna utile dei locali adibiti ad abitazione è fissata in **m 2,70**"
_ACC = "riducibile a **m 2,40** per i corridoi, i disimpegni in genere, i bagni, i gabinetti ed i ripostigli"
_SC = "minimum internal height **2,40 m** (derogating the 2,70 m baseline)"
_AERO = "la superficie finestrata apribile non potrà essere inferiore a **1/8 della superficie del pavimento**"


def _clause(kind, subject, value, unit, text, *, metric="net height", op=Operator.GE):
    return Clause(kind=kind, subject=subject, metric=metric, operator=op, value=value,
                  unit=unit, text=text)


def make_rule(*, hab=2.70, acc=2.40, sc=2.40, aero=0.125,
              hab_text=_HAB, acc_text=_ACC, sc_text=_SC, aero_text=_AERO,
              include_sc=True) -> Rule:
    """An oracle-shaped Rule; tweak a knob to fabricate a specific failure mode."""
    req = [
        _clause("requirement", "habitable room", hab, "m", hab_text),
        _clause("requirement", "accessory room", acc, "m", acc_text),
        _clause("requirement", "window", aero, "ratio", aero_text,
                metric="openable area / floor area"),
    ]
    exc = [_clause("exception", "existing building (recupero)", sc, "m", sc_text)] if include_sc else []
    return Rule(id="IT-DM-1975-HAB", source="DM 5/7/1975; Salva Casa",
                description="test", ifc_target=["IfcSpace", "IfcWindow"],
                requirement=req, exception=exc)


# --- direct gate tests -----------------------------------------------------------------

def test_oracle_accepts():
    thr = verify_rule_against_text(make_rule(), LAW)
    assert thr == {"min_height_habitable_m": 2.70, "min_height_accessory_m": 2.40,
                   "min_height_salva_casa_m": 2.40, "aero_illuminating_ratio": 0.125}, thr


def test_fabricated_2_65_rejected():
    # DONE-WHEN (d): a fabricated 2.65 must be rejected.
    _expect_reject(make_rule(hab=2.65), "min_height_habitable_m")


def test_montani_decoy_value_rejected():
    # ORACLE/(c): habitable 2,55 (comuni montani) is not the habitable internal height.
    _expect_reject(make_rule(hab=2.55), "min_height_habitable_m")


def test_decoy_span_rejected_even_with_right_number():
    # Presence != correctness: the RIGHT number (2.70) cited from the WRONG span must fail.
    montani = "per i comuni montani al di sopra dei 1000 m la minima può essere ridotta a m 2,55"
    _expect_reject(make_rule(hab=2.70, hab_text=montani), "min_height_habitable_m")


def test_partial_rule_rejected():
    # Requirement 3: all four must resolve from real clauses.
    _expect_reject(make_rule(include_sc=False), "min_height_salva_casa_m")


def test_wrong_operator_rejected():
    r = make_rule()
    r.requirement[0].operator = Operator.LE
    _expect_reject(r, "min_height_habitable_m")


def test_aero_rounding_rejected():
    _expect_reject(make_rule(aero=0.13), "aero_illuminating_ratio")


def test_track_edit_flows_through():
    # DONE-WHEN (a) mirror: edit the source to 2,73 -> gate accepts only the matching value.
    edited = LAW.replace("m 2,70", "m 2,73")
    assert verify_rule_against_text(make_rule(hab=2.73, hab_text=_HAB.replace("2,70", "2,73")),
                                    edited)["min_height_habitable_m"] == 2.73
    _expect_reject(make_rule(hab=2.70), "min_height_habitable_m", law=edited)  # stale value


def test_deleted_source_rejected():
    # DONE-WHEN (b) mirror: remove the habitable height from the text -> no backfill, reject.
    deleted = LAW.replace("è fissata\n> in **m 2,70**", "è fissata\n> in **m ___**")
    deleted = deleted.replace("**m 2,70**", "**m ___**")  # belt-and-suspenders
    _expect_reject(make_rule(), "min_height_habitable_m", law=deleted)


def test_answer_key_is_excluded_from_corpus():
    corpus = P.crosscheck_corpus(LAW)
    assert "Target rule (RASE decomposition)" not in corpus
    assert "Citations:" not in corpus
    assert "altezza minima interna utile" in corpus  # statute prose retained


# --- adversarial-audit regressions: decoy SHADOWING must yield an ambiguous-source reject ----
# (a montani/decoy span injected with a baseline lead-in phrase must NOT silently win)

def test_shadow_montani_into_salva_rejected():
    law = LAW.replace(
        "- minimum internal height **2,40 m** (derogating the 2,70 m baseline);",
        "- for comuni montani: minimum internal height **2,55 m** (local typology);\n"
        "- minimum internal height **2,40 m** (derogating the 2,70 m baseline);")
    _expect_reject(make_rule(sc=2.55, sc_text="minimum internal height 2,55 m (Salva Casa, esistente)"),
                   "min_height_salva_casa_m", law=law)
    _expect_reject(make_rule(), "min_height_salva_casa_m", law=law)  # even the honest value: ambiguous src


def test_shadow_montani_into_habitable_rejected():
    law = LAW.replace(
        "L'altezza minima interna utile",
        "Per i comuni montani l'altezza è fissata in m 2,55. L'altezza minima interna utile", 1)
    _expect_reject(make_rule(hab=2.55, hab_text="l'altezza è fissata in m 2,55 interna utile"),
                   "min_height_habitable_m", law=law)
    _expect_reject(make_rule(), "min_height_habitable_m", law=law)


def test_shadow_fraction_into_aero_rejected():
    law = LAW.replace("1/8 della superficie del pavimento",
                      "1/20 della superficie del pavimento e 1/8 della superficie del pavimento")
    _expect_reject(make_rule(), "aero_illuminating_ratio", law=law)


# --- adversarial-audit regressions: faithful bilingual citations must be ACCEPTED (no false-fail) ---

def test_accept_accessory_english_gloss():
    thr = verify_rule_against_text(
        make_rule(acc_text="reducible to 2,40 m for corridors, circulation, bathrooms, WCs and store rooms"),
        LAW)
    assert thr["min_height_accessory_m"] == 2.40


def test_accept_aero_english_paraphrase():
    thr = verify_rule_against_text(
        make_rule(aero_text="openable window area not less than 0.125 of the floor area"), LAW)
    assert thr["aero_illuminating_ratio"] == 0.125


def test_accept_habitable_english_paraphrase():
    thr = verify_rule_against_text(
        make_rule(hab_text="habitable rooms minimum internal height 2,70 m"), LAW)
    assert thr["min_height_habitable_m"] == 2.70


# --- end-to-end via a MOCKED model reply (parse_rule, non-offline) ----------------------

def _with_mocked_llm(rule_or_exc):
    """Context-managerless monkeypatch of parser.parse_with_ollama; returns a restore fn."""
    orig = P.parse_with_ollama
    if isinstance(rule_or_exc, BaseException):
        def fake(_text, model=None):
            raise rule_or_exc
    else:
        def fake(_text, model=None):
            return rule_or_exc
    P.parse_with_ollama = fake
    return lambda: setattr(P, "parse_with_ollama", orig)


def test_parse_rule_mocked_oracle_accepts():
    restore = _with_mocked_llm(make_rule())
    try:
        rule, thr, source = parse_rule(LAW, offline=False)
        assert source == "llm", source
        assert thr["min_height_habitable_m"] == 2.70
    finally:
        restore()


def test_parse_rule_mocked_fabrication_rejects():
    restore = _with_mocked_llm(make_rule(hab=2.65))
    try:
        _expect_reject_call(lambda: parse_rule(LAW, offline=False))
    finally:
        restore()


def test_parse_rule_no_fallthrough_on_llm_error():
    # The launderer is dead: an LLM error on a non-offline run must RAISE, not regex/defaults.
    restore = _with_mocked_llm(RuntimeError("ollama down"))
    try:
        raised = False
        try:
            parse_rule(LAW, offline=False)
        except RuntimeError:
            raised = True
        assert raised, "non-offline parse_rule must propagate LLM errors, not fall through"
    finally:
        restore()


# --- Stage 4 Part 3: the SELECTION gate (accessory tokens <-> DM-1975 Art.1 prose) ----------
# verify_accessory_selection_against_text anchors the art1-provenance accessory tokens to the
# Art.1 enumeration (rules/dm_1975_salva_casa.md:8-10) and declares the cross-lingual synonyms as
# unanchored debt. These cases keep THAT gate non-vacuous: accept the 4 anchored (incl. the
# disimpegno->disimpegni stem-drift pair); reject fabricated / truncated / suffix-extended /
# deleted / duplicate-injected; inherit the answer-key corpus exclusion; and pin the cross-lingual
# debt without over-claiming it (baseline §7). Tokens are sourced from applicability.json (no
# `import checker`); rejects are checked with the ValidationGateError-only _expect_gate_raise.

def test_selection_accepts_art1_tokens():
    out = verify_accessory_selection_against_text(_ART1_GROUP, LAW)
    assert set(out["anchored"]) == set(_ART1_GROUP), out["anchored"]
    assert set(out["enumeration"]) == {"corridoi", "disimpegni", "bagni", "gabinetti", "ripostigli"}
    # stem-equality survives singular/plural drift — a naive `token in prose` would false-reject:
    assert out["anchored"]["disimpegno"] == "disimpegni", out["anchored"]
    assert out["anchored"]["corrid"] == "corridoi"
    for tok, term in out["anchored"].items():
        assert term in out["enumeration"]


def test_selection_rejects_fabricated_token():
    # A token absent from Art.1 tagged art1 must RAISE (NO-INVENT analog).
    _expect_gate_raise(lambda: verify_accessory_selection_against_text(("garage",), LAW))
    _expect_gate_raise(lambda: verify_accessory_selection_against_text(("cucina",), LAW))


def test_selection_rejects_truncated_or_extended_token():
    # Proves the match is stem-EQUALITY, not prefix: a truncation ('bag') and a suffix extension
    # ('bagno_decoy') both fail to anchor (a looser prefix rule would pass every other case).
    _expect_gate_raise(lambda: verify_accessory_selection_against_text(("bag",), LAW))
    _expect_gate_raise(lambda: verify_accessory_selection_against_text(("bagno_decoy",), LAW))


def test_selection_rejects_deleted_source():
    # Remove the Art.1 enumeration prose (:9-10) -> anchor unmatched -> no backfill, RAISE.
    deleted = LAW.replace(
        "riducibile a **m 2,40** per i corridoi, i disimpegni in genere, i bagni,", "")
    deleted = deleted.replace("i gabinetti ed i ripostigli", "")   # belt-and-suspenders
    # Assert absence in the CORPUS the gate actually reads — the answer-key :61 retains the token
    # but crosscheck_corpus excludes it, so a missed replace cannot pass silently.
    assert "ripostigli" not in P.crosscheck_corpus(deleted)
    _expect_gate_raise(lambda: verify_accessory_selection_against_text(_ART1_GROUP, deleted))


def test_selection_inherits_answer_key_exclusion():
    # NOT a fresh anti-circularity proof (that is crosscheck_corpus' job, covered by
    # test_answer_key_is_excluded_from_corpus). Just assert the gate re-derives from the
    # answer-key-excluded corpus: the :61 'exclude corridoi/bagni/ripostigli' line is absent while
    # the Art.1 prose anchor is retained.
    corpus = P.crosscheck_corpus(LAW)
    assert "exclude corridoi/bagni/ripostigli" not in corpus
    assert "riducibile" in corpus
    out = verify_accessory_selection_against_text(_ART1_GROUP, LAW)
    assert set(out["anchored"]) == set(_ART1_GROUP)


def test_selection_cross_lingual_is_declared_debt():
    out = verify_accessory_selection_against_text(_ART1_GROUP, LAW, debt_tokens=_DEBT_GROUP)
    assert set(out["debt"]) == set(_DEBT_GROUP), out["debt"]
    # over-claim guard (baseline §7): no debt token is ever reported anchored/statute-verified.
    assert not (set(out["debt"]) & set(out["anchored"]))
    for tok in _DEBT_GROUP:
        assert tok not in out["anchored"]
    # Moving a debt token into the art1 argument RAISES (same non-enumerated path as a fabrication).
    assert "garage" in _DEBT_GROUP
    _expect_gate_raise(lambda: verify_accessory_selection_against_text(("garage",), LAW))


def test_selection_rejects_duplicate_injection():
    # Inject a SECOND, divergent 'riducibile a m 2,40 per …' span (mirror the montani shadow test):
    # re.findall then sees two non-identical term-sets -> ambiguous source -> RAISE.
    injected = LAW.replace(
        "i gabinetti ed i ripostigli.»",
        "i gabinetti ed i ripostigli.»\n> Inoltre riducibile a m 2,40 per i garage e le cantine.»",
        1)
    assert injected != LAW                              # the injection actually landed
    _expect_gate_raise(lambda: verify_accessory_selection_against_text(_ART1_GROUP, injected))


def test_selection_decoys_stay_out():
    # A non-Art.1 surface/room string tagged art1 RAISES via the same non-enumerated-token path as
    # a fabrication. The selection gate touches NO SYSTEM_PROMPT/_SOURCE_ANCHORS/THRESHOLD_KEYS;
    # parser.py:97-101 is the numeric-decoy prompt block, cited as context only — no monostanza
    # number is touched here.
    for decoy in ("montani", "alloggio monostanza", "seismic"):
        _expect_gate_raise(
            lambda d=decoy: verify_accessory_selection_against_text((d,), LAW))


# --- Stage 4 Part 4: the MONOSTANZA surface gate (the 2nd rule) -------------------------
# verify_monostanza_against_text anchors the four monostanza surfaces to the statute prose
# (rules/dm_1975_salva_casa.md:26-28 baseline mq 28/38, :37 Salva-Casa 20/28 m²) with the SAME
# verify-never-trust discipline as the numeric gate: person-count-qualified, unique-value-or-raise
# anchors over the de-marked, answer-key-excluded corpus. These cases keep THAT gate non-vacuous:
# accept the 4 statute surfaces (incl. the shared-28 disambiguation and the line-break-wrapped 2p
# span); prove the qualified anchor is load-bearing (a naive `mq\s*(\d+)` is ambiguous); reject a
# fabricated surface, a decoy-as-surface (montani/seismic height), a deleted source for BOTH person
# counts (non-vacuous), and a person-count swap. The numeric 4-threshold gate stays untouched.

_MONO_EXPECT = {"min_surface_monostanza_1p": 28.0, "min_surface_monostanza_2p": 38.0,
                "min_surface_monostanza_sc_1p": 20.0, "min_surface_monostanza_sc_2p": 28.0}


def _mono_clause(value, unit, text):
    return Clause(kind="requirement", subject="alloggio monostanza", metric="minimum surface",
                  operator=Operator.GE, value=value, unit=unit, text=text)


def _mono_oracle():
    """The four faithful monostanza surface clauses, citing the real statute spans."""
    return [
        _mono_clause(28, "mq", "Un alloggio monostanza, per una persona, deve avere una superficie "
                              "minima, comprensiva dei servizi, non inferiore a mq 28"),
        _mono_clause(38, "mq", "non inferiore a mq 38 se per due persone"),
        _mono_clause(20, "m²", "alloggio monostanza minimum surface (incl. services) 20 m² (1 person)"),
        _mono_clause(28, "m²", "minimum surface 28 m² (2 persons)"),
    ]


def test_monostanza_oracle_accepts():
    # Accept (anchored): the four statute surfaces bind, incl. the shared-28 (1p baseline vs sc 2p)
    # disambiguation and the line-break-wrapped 2p span (collapsed by _demark).
    assert verify_monostanza_against_text(_mono_oracle(), LAW) == _MONO_EXPECT
    # also works when handed a whole Rule (clauses flattened):
    rule = Rule(id="MONO", source="test", description="t", requirement=_mono_oracle())
    assert verify_monostanza_against_text(rule, LAW) == _MONO_EXPECT


def test_monostanza_anchor_is_load_bearing():
    # Unique-or-raise proof: the qualified _1p anchor resolves to the UNIQUE 28, while a naive
    # `mq\s*(\d+)` matches BOTH 28 and 38 (ambiguous) — i.e. the person-count qualifier is what
    # makes the gate sound.
    corpus = P._demark(P.crosscheck_corpus(LAW))
    assert re.findall(P._MONOSTANZA_ANCHORS["min_surface_monostanza_1p"], corpus, re.I) == ["28"]
    assert set(re.findall(r"mq\s*(\d+)", corpus, re.I)) == {"28", "38"}


def test_monostanza_rejects_fabricated_surface():
    # A monostanza clause with a value absent from the statute (30) cannot satisfy its key -> RAISE.
    clauses = _mono_oracle()
    clauses[0] = _mono_clause(30, "mq", "per una persona ... non inferiore a mq 30")
    _expect_gate_raise(lambda: verify_monostanza_against_text(clauses, LAW))


def test_monostanza_rejects_decoy_as_surface():
    # montani 2,55 (a HEIGHT) offered as a monostanza surface: value not in {28,38,20,28} AND a
    # metre unit (not a surface) -> never binds -> the 1p key is unsatisfiable -> RAISE. Proves the
    # height decoys stay OUT of the 2nd rule even after the prompt un-suppresses monostanza.
    montani = _mono_oracle()
    montani[0] = _mono_clause(2.55, "m", "comuni montani ... ridotta a m 2,55, per una persona")
    _expect_gate_raise(lambda: verify_monostanza_against_text(montani, LAW))
    seismic = _mono_oracle()
    seismic[1] = _mono_clause(40, "m", "seismic-zone height 40 m, se per due persone")
    _expect_gate_raise(lambda: verify_monostanza_against_text(seismic, LAW))


def test_monostanza_rejects_deleted_source_both_counts():
    # Non-vacuous: a generic 'deleted -> raise' passes via the already-safe _2p path, so BOTH halves
    # are required. (a) delete `mq 28` -> _1p anchor unmatched -> source is None (NOT 38: the slide
    # is blocked) -> RAISE.
    del28 = LAW.replace("mq 28", "mq XX")
    assert P._monostanza_source_value(P.crosscheck_corpus(del28),
                                      "min_surface_monostanza_1p") is None
    _expect_gate_raise(lambda: verify_monostanza_against_text(_mono_oracle(), del28))
    # (b) delete the `mq 38 ... due persone` span -> _2p anchor unmatched -> RAISE on _2p.
    del38 = LAW.replace("e non inferiore a **mq 38** se per\n> due persone", "")
    assert del38 != LAW
    assert P._monostanza_source_value(P.crosscheck_corpus(del38),
                                      "min_surface_monostanza_2p") is None
    _expect_gate_raise(lambda: verify_monostanza_against_text(_mono_oracle(), del38))


def test_monostanza_rejects_person_count_swap():
    # The 38 value presented AS the 1-person minimum (cited under a _1p discriminator): _1p's source
    # is 28, so a 38-valued clause can never satisfy _1p -> RAISE (the person-count swap is caught
    # by value-equality, not by trusting the clause's self-label).
    clauses = _mono_oracle()
    clauses[0] = _mono_clause(38, "mq", "per una persona ... non inferiore a mq 38")
    _expect_gate_raise(lambda: verify_monostanza_against_text(clauses, LAW))


def test_monostanza_rejects_decoy_shadow_1p():
    # Adversarial-audit regression (decoy-shadowing, the ADR-002 class): a look-alike
    # `non inferiore a mq 99` span injected BEFORE the real `mq 28` must NOT silently win. The _1p
    # anchor's recurring `non inferiore a mq` lead-in makes the injection a SECOND distinct value, so
    # the source is ambiguous -> RAISE (the gate never binds the decoy 99). Mirrors
    # test_shadow_montani_into_habitable_rejected on the numeric gate. (A wider `per una persona…mq`
    # gap silently returned ['99'] — the false-pass this test pins shut.)
    shadow = LAW.replace("non inferiore a **mq 28**",
                         "non inferiore a **mq 99**, e non inferiore a **mq 28**")
    assert shadow != LAW
    # source derivation is ambiguous -> raises
    _expect_gate_raise(lambda: P._monostanza_source_value(
        P.crosscheck_corpus(shadow), "min_surface_monostanza_1p"))
    # and the full gate rejects, even when the LLM clause faithfully cites the injected decoy span
    clauses = _mono_oracle()
    clauses[0] = _mono_clause(99, "mq", "per una persona ... non inferiore a mq 99")
    _expect_gate_raise(lambda: verify_monostanza_against_text(clauses, shadow))


def test_numeric_gate_unchanged_after_monostanza():
    # Regression: the four-threshold numeric gate is untouched by Part 4 — the oracle still accepts
    # and montani 2,55 is still rejected as the habitable height (the height decoy stays a decoy on
    # the numeric path; THRESHOLD_KEYS / verify_rule_against_text unchanged).
    assert verify_rule_against_text(make_rule(), LAW)["min_height_habitable_m"] == 2.70
    _expect_reject(make_rule(hab=2.55), "min_height_habitable_m")
    assert P.THRESHOLD_KEYS == ("min_height_habitable_m", "min_height_accessory_m",
                                "min_height_salva_casa_m", "aero_illuminating_ratio")


# --- Stage 4 Part 4: gate-on-compile SELECTION (Ollama-free) ----------------------------
# gate_verified_selection wires the Part-3 selection gate into the compile path: it reads the art1
# tokens from the declarative table and returns a statute-anchored selection (proven here), so the
# compiled rule's selection:[] can be populated gate-verified rather than left empty. checker.py
# reads only `thresholds` (from_rules_json), so this is verdict-neutral.

def test_compile_selection_is_gate_verified():
    clauses = P.gate_verified_selection(LAW)
    assert clauses, "expected a non-empty gate-verified selection"
    assert all(c.kind == "selection" for c in clauses)
    # every Art.1 enumerated term appears in the emitted selection text
    joined = " ".join(c.text for c in clauses)
    for term in ("corridoi", "disimpegni", "bagni", "gabinetti", "ripostigli"):
        assert term in joined, term
    # one clause per anchored art1 token (4) + one habitable-inclusion clause:
    assert sum(c.subject == "accessory room" for c in clauses) == 4, clauses
    assert sum(c.subject == "habitable room" for c in clauses) == 1, clauses


def test_compile_selection_rejects_fabricated_token():
    # A tampered table with a fabricated art1 token makes the gate RAISE (NO-INVENT) -> no fake
    # 'verified' selection can be produced from an unanchored token.
    import os as _os
    import tempfile
    data = json.loads((Path(__file__).resolve().parents[1] / "rules" / "applicability.json")
                      .read_text(encoding="utf-8"))
    for g in data["occupancy_classes"]["accessory"]["hint_groups"]:
        if g.get("provenance") == "art1":
            g["hints"] = list(g["hints"]) + ["garage"]
    with tempfile.TemporaryDirectory() as d:
        p = _os.path.join(d, "applicability.json")
        Path(p).write_text(json.dumps(data), encoding="utf-8")
        _expect_gate_raise(lambda: P.gate_verified_selection(LAW, applicability_path=p))


# --- helpers ---------------------------------------------------------------------------

def _expect_reject(rule, key_substr, law=LAW):
    try:
        verify_rule_against_text(rule, law)
    except ValidationGateError as e:
        assert key_substr in str(e), f"rejected, but not for {key_substr}: {e}"
        return
    raise AssertionError(f"gate ACCEPTED a rule it should have rejected ({key_substr})")


def _expect_reject_call(fn):
    try:
        fn()
    except ValidationGateError:
        return
    raise AssertionError("expected ValidationGateError")


def _expect_gate_raise(fn):
    """Assert the SELECTION gate RAISES ValidationGateError. Unlike _expect_reject, it does NOT
    look for a numeric THRESHOLD_KEYS substring — the selection-gate error names a token/enumeration,
    not one of the four threshold keys."""
    try:
        fn()
    except ValidationGateError:
        return
    raise AssertionError("expected ValidationGateError from the selection gate")


def _main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_main())
