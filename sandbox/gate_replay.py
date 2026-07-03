#!/usr/bin/env python3
"""37-pin replay: test_gate.py's historical verification pins through the span-quote protocol.

Strategy §3.2.5 step 4 names the 37 `test_gate.py` pins as the recall floor of the
span-quote gate. This harness extracts every pin into a structured fixture and replays
it against gate_spike's four-layer protocol:

  - 27 pins are PROTOCOL-MAPPABLE: 16 numeric-gate, 3 end-to-end wiring (mocked
    extractor), 7 monostanza, 1 regression. Each maps to one or more claim-level
    sub-cases with an expected ACCEPT/REJECT (or a structural/completeness assertion).
  - 10 pins are STRUCTURALLY OUT-OF-SCOPE — 8 selection-vocabulary pins (the
    applicability-class gate, strategy §3.2.4 type 6) and 2 compile-emission pins
    (Stage 4-6 emitters). They are carried in the fixture with their reason, never
    silently dropped, and they do NOT count toward the replay denominator.
  - 3 pins carry RE-MECHANIZED sub-cases per the §3.2.5 quotation-layer resolution:
    2 paraphrase accepts (aero, habitable — their literal clause text is never verbatim
    in the corpus and must stay REJECTED at L1; the same fact is accepted through a
    verbatim gloss span, the paraphrase demoted to never-load-bearing gloss) and 1
    non-contiguous monostanza span (sc_2p literal text skips corpus words; the tight
    verbatim span binds via the host-sentence direction). All halves are asserted.

Run:
    python gate_replay.py                # deterministic replay (no LLM)
    python gate_replay.py --live         # + one Ollama extraction per distinct pin corpus
    python gate_replay.py --live --report replay_report.json
Exit 0 iff every mapped pin MATCHES and (if --live) zero false accepts occurred.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable, List, Optional

_SANDBOX = Path(__file__).resolve().parent
sys.path.insert(0, str(_SANDBOX))

import gate_spike as G  # noqa: E402  (spike-side import; production code untouched)

LAW = (_SANDBOX / "rules" / "dm_1975_salva_casa.md").read_text(encoding="utf-8")

# Verbatim spans exactly as test_gate.py:47-50 defines them.
_HAB = "L'altezza minima interna utile dei locali adibiti ad abitazione è fissata in **m 2,70**"
_ACC = "riducibile a **m 2,40** per i corridoi, i disimpegni in genere, i bagni, i gabinetti ed i ripostigli"
_SC = "minimum internal height **2,40 m** (derogating the 2,70 m baseline)"
_AERO = "la superficie finestrata apribile non potrà essere inferiore a **1/8 della superficie del pavimento**"

# --- pin corpora: the EXACT mutations test_gate.py applies -----------------------------
CORPORA = {
    "C0": LAW,
    "C_edit273": LAW.replace("m 2,70", "m 2,73"),                               # :115
    "C_del_hab": LAW.replace("è fissata\n> in **m 2,70**", "è fissata\n> in **m ___**")
                    .replace("**m 2,70**", "**m ___**"),                        # :123-124
    "C_mont_salva": LAW.replace(
        "- minimum internal height **2,40 m** (derogating the 2,70 m baseline);",
        "- for comuni montani: minimum internal height **2,55 m** (local typology);\n"
        "- minimum internal height **2,40 m** (derogating the 2,70 m baseline);"),   # :139-142
    "C_mont_hab": LAW.replace(
        "L'altezza minima interna utile",
        "Per i comuni montani l'altezza è fissata in m 2,55. L'altezza minima interna utile", 1),  # :149-151
    "C_frac_aero": LAW.replace(
        "1/8 della superficie del pavimento",
        "1/20 della superficie del pavimento e 1/8 della superficie del pavimento"),  # :158-159
    "C_del28": LAW.replace("mq 28", "mq XX"),                                   # :391
    "C_del38": LAW.replace("e non inferiore a **mq 38** se per\n> due persone", ""),  # :396
    "C_mq99": LAW.replace("non inferiore a **mq 28**",
                          "non inferiore a **mq 99**, e non inferiore a **mq 28**"),  # :419-420
}
for _k, _v in CORPORA.items():
    assert _k == "C0" or _v != LAW, f"corpus mutation {_k} did not land"

_NUMERIC_KEYS = ("min_height_habitable_m", "min_height_accessory_m",
                 "min_height_salva_casa_m", "aero_illuminating_ratio")


def _c(value, operator, unit, span, metric="pin") -> G.SpanClaim:
    return G.SpanClaim(metric=metric, value=value, operator=operator, unit=unit, span=span)


def _oracle_claims() -> List[G.SpanClaim]:
    return [
        _c(2.70, ">=", "m", _HAB, "habitable"),
        _c(2.40, ">=", "m", _ACC, "accessory"),
        _c(0.125, ">=", "ratio", _AERO, "aero"),
        _c(2.40, ">=", "m", _SC, "salva casa"),
    ]


# --- pin fixture ------------------------------------------------------------------------
# Each pin: name, category, mode, and mode-specific payload.
#   mode "claims": cases = [(corpus_key, claim, expected 'ACCEPT'|'REJECT', note)]
#   mode "completeness" / "structural" / "wiring": a check function returning (ok, note)
#   mode "out-of-scope": reason
PINS: List[dict] = []


def pin(name, category, mode, **kw):
    PINS.append({"name": name, "category": category, "mode": mode, **kw})


# --- numeric gate (16) --------------------------------------------------------------
pin("test_oracle_accepts", "numeric", "claims", cases=[
    ("C0", _oracle_claims()[0], "ACCEPT", ""),
    ("C0", _oracle_claims()[1], "ACCEPT", ""),
    ("C0", _oracle_claims()[2], "ACCEPT", ""),
    ("C0", _oracle_claims()[3], "ACCEPT", ""),
])
pin("test_fabricated_2_65_rejected", "numeric", "claims", cases=[
    ("C0", _c(2.65, ">=", "m", _HAB), "REJECT", "fabricated value on faithful span"),
])
pin("test_montani_decoy_value_rejected", "numeric", "claims", cases=[
    ("C0", _c(2.55, ">=", "m", _HAB), "REJECT", "montani value on habitable span"),
])
pin("test_decoy_span_rejected_even_with_right_number", "numeric", "claims", cases=[
    ("C0", _c(2.70, ">=", "m",
              "per i comuni montani al di sopra dei 1000 m la minima può essere ridotta a m 2,55"),
     "REJECT", "right number, wrong (fabricated montani) span"),
])
pin("test_partial_rule_rejected", "numeric", "completeness",
    check=lambda: _completeness_check())
pin("test_wrong_operator_rejected", "numeric", "claims", cases=[
    ("C0", _c(2.70, "<=", "m", _HAB), "REJECT", "LE operator on a minimum"),
])
pin("test_aero_rounding_rejected", "numeric", "claims", cases=[
    ("C0", _c(0.13, ">=", "ratio", _AERO), "REJECT", "rounded 0.13 vs 1/8"),
])
pin("test_track_edit_flows_through", "numeric", "claims", cases=[
    ("C_edit273", _c(2.73, ">=", "m", _HAB.replace("2,70", "2,73")), "ACCEPT", "edited source tracks"),
    ("C_edit273", _c(2.70, ">=", "m", _HAB), "REJECT", "stale value after source edit"),
])
pin("test_deleted_source_rejected", "numeric", "claims", cases=[
    ("C_del_hab", _oracle_claims()[0], "REJECT", "deleted source, no backfill"),
])
pin("test_answer_key_is_excluded_from_corpus", "numeric", "structural",
    check=lambda: _answer_key_check())
pin("test_shadow_montani_into_salva_rejected", "numeric", "claims", cases=[
    ("C_mont_salva", _c(2.55, ">=", "m", "minimum internal height 2,55 m (Salva Casa, esistente)"),
     "REJECT", "pin's literal (non-verbatim) decoy claim"),
    ("C_mont_salva", _c(2.55, ">=", "m",
                        "for comuni montani: minimum internal height **2,55 m** (local typology)"),
     "REJECT", "verbatim injected decoy span -> corpus-ambiguous"),
    ("C_mont_salva", _oracle_claims()[3], "REJECT", "even the honest value: ambiguous source"),
])
pin("test_shadow_montani_into_habitable_rejected", "numeric", "claims", cases=[
    ("C_mont_hab", _c(2.55, ">=", "m", "l'altezza è fissata in m 2,55 interna utile"),
     "REJECT", "pin's literal (reordered) decoy claim"),
    ("C_mont_hab", _oracle_claims()[0], "REJECT", "honest value: ambiguous source"),
])
pin("test_shadow_fraction_into_aero_rejected", "numeric", "claims", cases=[
    ("C_frac_aero", _oracle_claims()[2], "REJECT", "1/20 injected beside 1/8"),
])
pin("test_accept_accessory_english_gloss", "numeric", "claims", cases=[
    ("C0", _c(2.40, ">=", "m",
              "reducible to 2,40 m for corridors, circulation, bathrooms, WCs and store rooms"),
     "ACCEPT", "verbatim gloss span (gloss-anchor tier)"),
])
pin("test_accept_aero_english_paraphrase", "numeric", "claims", remech=True, cases=[
    ("C0", _c(0.125, ">=", "ratio", "openable window area not less than 0.125 of the floor area"),
     "REJECT", "literal pin text is a PARAPHRASE -> stays rejected at L1"),
    ("C0", _c(0.125, ">=", "ratio", "Openable window area must be ≥ 1/8 of the floor area"),
     "ACCEPT", "RE-MECHANIZED: same fact via verbatim gloss span; paraphrase demoted to gloss"),
])
pin("test_accept_habitable_english_paraphrase", "numeric", "claims", remech=True, cases=[
    ("C0", _c(2.70, ">=", "m", "habitable rooms minimum internal height 2,70 m"),
     "REJECT", "literal pin text is a PARAPHRASE -> stays rejected at L1"),
    ("C0", _c(2.70, ">=", "m", "Habitable rooms: min net internal height 2.70 m"),
     "ACCEPT", "RE-MECHANIZED: same fact via verbatim gloss span"),
])

# --- end-to-end wiring (3) ----------------------------------------------------------
pin("test_parse_rule_mocked_oracle_accepts", "wiring", "wiring",
    check=lambda: _wiring_oracle())
pin("test_parse_rule_mocked_fabrication_rejects", "wiring", "wiring",
    check=lambda: _wiring_fabrication())
pin("test_parse_rule_no_fallthrough_on_llm_error", "wiring", "wiring",
    check=lambda: _wiring_error_propagates())

# --- selection gate (8): OUT OF SCOPE ------------------------------------------------
_SEL_REASON = ("selection-VOCABULARY gate (statute-term anchoring of occupancy tokens); the "
               "span-quote protocol carries no vocabulary layer — this is the "
               "applicability-class gate, strategy §3.2.4 type 6, future spike scope")
for _n in ("test_selection_accepts_art1_tokens", "test_selection_rejects_fabricated_token",
           "test_selection_rejects_truncated_or_extended_token",
           "test_selection_rejects_deleted_source", "test_selection_inherits_answer_key_exclusion",
           "test_selection_cross_lingual_is_declared_debt"):
    pin(_n, "selection", "out-of-scope", reason=_SEL_REASON)
pin("test_selection_rejects_duplicate_injection", "selection", "out-of-scope",
    reason=_SEL_REASON + " — NOTE: the injected duplicate carries the SAME value (2,40), so the "
                         "numeric protocol correctly still accepts the accessory threshold on that "
                         "corpus; only the vocabulary layer can see the term-set divergence")
pin("test_selection_decoys_stay_out", "selection", "out-of-scope", reason=_SEL_REASON)

# --- monostanza gate (7) --------------------------------------------------------------
pin("test_monostanza_oracle_accepts", "monostanza", "claims", remech=True, cases=[
    ("C0", _c(28, ">=", "mq", "Un alloggio monostanza, per una persona, deve avere una superficie "
                              "minima, comprensiva dei servizi, non inferiore a mq 28"), "ACCEPT", ""),
    ("C0", _c(38, ">=", "mq", "non inferiore a mq 38 se per due persone"), "ACCEPT", ""),
    ("C0", _c(20, ">=", "m²", "alloggio monostanza minimum surface (incl. services) 20 m² (1 person)"),
     "ACCEPT", ""),
    ("C0", _c(28, ">=", "m²", "minimum surface 28 m² (2 persons)"),
     "REJECT", "pin's literal sc_2p text is NON-CONTIGUOUS in the corpus -> L1 rejects"),
    ("C0", _c(28, ">=", "m²", "28 m² (2 persons)"),
     "ACCEPT", "RE-MECHANIZED: tight verbatim span; direction from the host statute sentence"),
])
pin("test_monostanza_anchor_is_load_bearing", "monostanza", "structural",
    check=lambda: _mono_anchor_check())
pin("test_monostanza_rejects_fabricated_surface", "monostanza", "claims", cases=[
    ("C0", _c(30, ">=", "mq", "per una persona ... non inferiore a mq 30"), "REJECT", ""),
])
pin("test_monostanza_rejects_decoy_as_surface", "monostanza", "claims", cases=[
    ("C0", _c(2.55, ">=", "m", "comuni montani ... ridotta a m 2,55, per una persona"), "REJECT", ""),
    ("C0", _c(40, ">=", "m", "seismic-zone height 40 m, se per due persone"), "REJECT", ""),
])
pin("test_monostanza_rejects_deleted_source_both_counts", "monostanza", "claims", cases=[
    ("C_del28", _c(28, ">=", "mq", "Un alloggio monostanza, per una persona, deve avere una superficie "
                                   "minima, comprensiva dei servizi, non inferiore a mq 28"),
     "REJECT", "mq 28 deleted"),
    ("C_del38", _c(38, ">=", "mq", "non inferiore a mq 38 se per due persone"), "REJECT", "mq 38 deleted"),
])
pin("test_monostanza_rejects_person_count_swap", "monostanza", "claims", cases=[
    ("C0", _c(38, ">=", "mq", "per una persona ... non inferiore a mq 38"), "REJECT", ""),
])
pin("test_monostanza_rejects_decoy_shadow_1p", "monostanza", "claims", cases=[
    ("C_mq99", _c(99, ">=", "mq", "per una persona ... non inferiore a mq 99"),
     "REJECT", "pin's literal (non-verbatim) decoy claim"),
    ("C_mq99", _c(99, ">=", "mq", "non inferiore a **mq 99**"),
     "REJECT", "verbatim injected decoy -> 1p anchor corpus-ambiguous {99, 28}"),
    ("C_mq99", _c(28, ">=", "mq", "Un alloggio monostanza, per una persona, deve avere una superficie "
                                  "minima, comprensiva dei servizi, non inferiore a mq 28"),
     "REJECT", "honest value under shadow: ambiguous source"),
])

# --- regression (1) --------------------------------------------------------------------
pin("test_numeric_gate_unchanged_after_monostanza", "regression", "claims", cases=[
    ("C0", _oracle_claims()[0], "ACCEPT", "oracle still accepts"),
    ("C0", _c(2.55, ">=", "m", _HAB), "REJECT", "montani 2,55 still rejected"),
])

# --- compile pins (2): OUT OF SCOPE ---------------------------------------------------
_CMP_REASON = ("compile-path emission (gate_verified_selection -> Rule clauses); the span-quote "
               "protocol validates claims, it does not emit rule artifacts — Stage 4-6 scope")
pin("test_compile_selection_is_gate_verified", "compile", "out-of-scope", reason=_CMP_REASON)
pin("test_compile_selection_rejects_fabricated_token", "compile", "out-of-scope", reason=_CMP_REASON)

assert len(PINS) == 37, f"pin fixture must carry all 37 pins, has {len(PINS)}"


# --- mode implementations ----------------------------------------------------------------
def _completeness_check():
    """test_partial_rule_rejected: all four numeric keys must resolve; drop the sc claim and
    the coverage check must flag exactly min_height_salva_casa_m as unresolved."""
    claims = _oracle_claims()[:3]      # habitable, accessory, aero — NO salva-casa clause
    accepted_keys = set()
    for cl in claims:
        v = G.validate_claim(cl, CORPORA["C0"])
        if v.accepted:
            accepted_keys.add(v.anchor_key)
    missing = set(_NUMERIC_KEYS) - accepted_keys
    ok = missing == {"min_height_salva_casa_m"} and len(accepted_keys) == 3
    return ok, f"accepted={sorted(accepted_keys)}, missing={sorted(missing)}"


def _answer_key_check():
    corpus = G.crosscheck_corpus(LAW)
    ok = ("Target rule (RASE decomposition)" not in corpus
          and "Citations:" not in corpus
          and "altezza minima interna utile" in corpus)
    return ok, "answer key + citations excluded; statute prose retained"


def _mono_anchor_check():
    import re
    corpus = G._demark(G.crosscheck_corpus(LAW))
    qualified = re.findall(G.ANCHORS["min_surface_monostanza_1p"], corpus, re.I)
    naive = set(re.findall(r"mq\s*(\d+)", corpus, re.I))
    ok = qualified == ["28"] and naive == {"28", "38"}
    return ok, f"qualified={qualified}, naive={sorted(naive)}"


def _run_claims_through(extractor: Callable, corpus: str):
    """The live-loop shape with an injectable extractor — NO exception handling around the
    extractor: an extractor error must propagate (test_parse_rule_no_fallthrough_on_llm_error)."""
    claims = extractor(corpus).claims
    return [(cl, G.validate_claim(cl, corpus)) for cl in claims]


def _wiring_oracle():
    results = _run_claims_through(lambda _t: G.SpanClaims(claims=_oracle_claims()), CORPORA["C0"])
    accepts = [v for _c2, v in results if v.accepted]
    ok = len(accepts) == 4 and {v.anchor_key for v in accepts} == set(_NUMERIC_KEYS)
    return ok, f"{len(accepts)}/4 oracle claims accepted end-to-end"


def _wiring_fabrication():
    results = _run_claims_through(
        lambda _t: G.SpanClaims(claims=[_c(2.65, ">=", "m", _HAB)]), CORPORA["C0"])
    ok = all(not v.accepted for _c2, v in results)
    return ok, "fabricated 2.65 claim not accepted end-to-end"


def _wiring_error_propagates():
    def broken(_t):
        raise RuntimeError("ollama down")
    try:
        _run_claims_through(broken, CORPORA["C0"])
    except RuntimeError:
        return True, "extractor error propagated; no silent fallback"
    return False, "extractor error was swallowed — launderer risk"


# --- deterministic replay ----------------------------------------------------------------
def run_replay():
    rows, mapped, matched, oos = [], 0, 0, 0
    accepts_expected = accepts_got = false_accepts = 0
    for p in PINS:
        if p["mode"] == "out-of-scope":
            oos += 1
            rows.append({"pin": p["name"], "category": p["category"], "result": "OUT-OF-SCOPE",
                         "detail": p["reason"]})
            continue
        mapped += 1
        if p["mode"] in ("structural", "completeness", "wiring"):
            ok, note = p["check"]()
            matched += 1 if ok else 0
            rows.append({"pin": p["name"], "category": p["category"],
                         "result": "MATCH" if ok else "MISMATCH", "detail": note})
            continue
        sub, sub_ok = [], True
        for corpus_key, claim, expected, note in p["cases"]:
            v = G.validate_claim(claim, CORPORA[corpus_key])
            got = "ACCEPT" if v.accepted else "REJECT"
            case_ok = got == expected
            sub_ok &= case_ok
            if expected == "ACCEPT":
                accepts_expected += 1
                accepts_got += 1 if v.accepted else 0
            if v.accepted and expected == "REJECT":
                false_accepts += 1
            sub.append(f"[{corpus_key}] {expected}->{got} ({v.reason})"
                       + (f" {note}" if note else "") + ("" if case_ok else "  << MISMATCH"))
        matched += 1 if sub_ok else 0
        label = "MATCH-REMECHANIZED" if (sub_ok and p.get("remech")) else \
                ("MATCH" if sub_ok else "MISMATCH")
        rows.append({"pin": p["name"], "category": p["category"], "result": label,
                     "detail": "; ".join(sub)})
    return {"rows": rows, "mapped": mapped, "matched": matched, "out_of_scope": oos,
            "accepts_expected": accepts_expected, "accepts_got": accepts_got,
            "false_accepts": false_accepts}


# --- live loop over the pin corpora --------------------------------------------------------
_BASE_TRUTH = {("min_height_habitable_m", 2.70), ("min_height_accessory_m", 2.40),
               ("min_height_salva_casa_m", 2.40), ("aero_illuminating_ratio", 0.125),
               ("min_surface_monostanza_1p", 28.0), ("min_surface_monostanza_2p", 38.0),
               ("min_surface_monostanza_sc_1p", 20.0), ("min_surface_monostanza_sc_2p", 28.0)}


def _truth_without(*keys):
    return {p for p in _BASE_TRUTH if p[0] not in keys}


LIVE_TRUTH = {
    "C0": _BASE_TRUTH,
    "C_edit273": _truth_without("min_height_habitable_m") | {("min_height_habitable_m", 2.73)},
    "C_del_hab": _truth_without("min_height_habitable_m"),
    "C_mont_salva": _truth_without("min_height_salva_casa_m"),
    "C_mont_hab": _truth_without("min_height_habitable_m"),
    "C_frac_aero": _truth_without("aero_illuminating_ratio"),
    "C_del28": _truth_without("min_surface_monostanza_1p"),
    "C_del38": _truth_without("min_surface_monostanza_2p"),
    "C_mq99": _truth_without("min_surface_monostanza_1p"),
}


def run_live(model: str):
    rows, n_claims, n_accepts, n_false = [], 0, 0, 0
    per_corpus = {}
    for ckey, corpus in CORPORA.items():
        claims = G.ollama_extract(corpus, model).claims
        truth = LIVE_TRUTH[ckey]
        c_accepts, c_recalled = 0, set()
        for cl in claims:
            n_claims += 1
            v = G.validate_claim(cl, corpus)
            fa = False
            if v.accepted:
                n_accepts += 1
                c_accepts += 1
                pair_ok = any(k == v.anchor_key and abs(cl.value - val) <= G._EQ_TOL
                              for k, val in truth)
                if pair_ok:
                    c_recalled.add(v.anchor_key)
                else:
                    fa = True
                    n_false += 1
            rows.append({"corpus": ckey, "value": cl.value, "operator": cl.operator,
                         "unit": cl.unit, "span": cl.span[:90],
                         "got": "ACCEPT" if v.accepted else "REJECT", "reason": v.reason,
                         "anchor": v.anchor_key, "false_accept": fa})
        per_corpus[ckey] = {"claims": len(claims), "accepts": c_accepts,
                            "recall": f"{len(c_recalled)}/{len(truth)}"}
    return {"model": model, "claims": n_claims, "accepts": n_accepts,
            "false_accepts": n_false, "per_corpus": per_corpus, "rows": rows}


def main(argv=None) -> int:
    G._enforce_policy_anchor()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="37-pin replay through the span-quote protocol")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--model", default="llama3.1:8b")
    ap.add_argument("--report", type=Path, default=None)
    args = ap.parse_args(argv)

    rep = run_replay()
    print(f"== 37-PIN REPLAY (deterministic) — {rep['mapped']} mapped, "
          f"{rep['out_of_scope']} structurally out-of-scope ==")
    for r in rep["rows"]:
        mark = {"MATCH": "ok ", "MATCH-REMECHANIZED": "ok*", "OUT-OF-SCOPE": "-- "}.get(
            r["result"], "XX ")
        print(f"{mark} [{r['category']:<10}] {r['pin']}: {r['result']}")
        if mark == "XX ":
            print(f"      {r['detail']}")
    print(f"-- mapped pins matched: {rep['matched']}/{rep['mapped']} "
          f"(ok* = re-mechanized per §3.2.5 quotation layer)")
    print(f"-- accept sub-cases recalled: {rep['accepts_got']}/{rep['accepts_expected']}; "
          f"FALSE ACCEPTS: {rep['false_accepts']}")
    exit_code = 0 if (rep["matched"] == rep["mapped"] and rep["false_accepts"] == 0) else 1

    live = None
    if args.live and exit_code == 0:
        print(f"\n== LIVE LOOP over the {len(CORPORA)} pin corpora "
              f"(Ollama {args.model}, temperature 0, seed 0) ==")
        live = run_live(args.model)
        for ckey, s in live["per_corpus"].items():
            print(f"  {ckey:<14} claims={s['claims']:>2} accepts={s['accepts']:>2} "
                  f"recall={s['recall']}")
        for r in live["rows"]:
            if r["false_accept"]:
                print(f"  FALSE-ACCEPT [{r['corpus']}] {r['value']} {r['unit']} "
                      f"anchor={r['anchor']} span={r['span']!r}")
        precision = 1.0 if live["accepts"] == 0 else \
            (live["accepts"] - live["false_accepts"]) / live["accepts"]
        print(f"-- live: {live['claims']} claims, {live['accepts']} accepts, "
              f"{live['false_accepts']} FALSE ACCEPTS; precision {precision:.3f}")
        if live["false_accepts"]:
            exit_code = 1

    if args.report:
        args.report.write_text(json.dumps({"replay": rep, "live": live}, indent=2,
                                          ensure_ascii=False, default=str), encoding="utf-8")
        print(f"report written: {args.report}")
    print(f"\nRESULT: {'PASS' if exit_code == 0 else 'FAIL'}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
