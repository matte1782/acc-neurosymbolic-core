#!/usr/bin/env python3
"""T0 report renderer tests (sandbox/report_html.py) — offline, pure stdlib.

Pinned contract:
  * ESCAPING — IFC space names and engine notes are untrusted; a hostile string must never
    reach the HTML unescaped (no stored-XSS in a file a professional forwards by email).
  * SELF-CONTAINED — zero external requests: no http(s) URLs, no src=, no @import
    (local-first posture + print reliability).
  * TERNARY FIRST-CLASS — pass/violation/undetermined each render a distinct badge; the
    accessory aero column renders n/a, never a fake verdict.
  * VERDICT WORD — mirrors the engine semantics incl. H-1 (0 spaces -> NON CERTIFICABILE)
    and undetermined-never-compliant.
  * DETERMINISTIC — same JSON, byte-identical HTML.
  * Accepts both the checker report JSON and the API /evaluate envelope.

Run either way:
    python test_report_html.py     # prints PASS/FAIL/SKIP, exit 1 on any failure
    pytest test_report_html.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SANDBOX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SANDBOX))

import report_html as R     # noqa: E402  (pure stdlib — safe to import unconditionally)

_PASS = _FAIL = _SKIP = 0
_FZK_REPORT = _SANDBOX / "data" / "AC20-FZK-Haus_report.json"


def _check(name: str, cond: bool) -> None:
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"PASS {name}")
    else:
        _FAIL += 1
        print(f"FAIL {name}")
        if "pytest" in sys.modules:
            raise AssertionError(f"check failed: {name}")


def _skip(name: str, why: str) -> None:
    global _SKIP
    _SKIP += 1
    print(f"SKIP {name} ({why})")


def _finding(name, occ, comp, height_ok, aero_ok, notes=()):
    return {"global_id": f"gid-{name}", "name": name, "occupancy": occ, "height_m": 2.8,
            "floor_area_m2": 10.0, "window_area_m2": 1.5, "aero_ratio": 0.15,
            "height_required_m": 2.7, "height_ok": height_ok, "aero_ok": aero_ok,
            "compliant": comp, "notes": list(notes)}


def _report(findings, violations, undetermined, spaces=None):
    return {"model": "synthetic.ifc", "schema": "IFC4", "salva_casa": False,
            "thresholds": {"min_height_habitable_m": 2.7, "min_height_accessory_m": 2.4,
                           "min_height_salva_casa_m": 2.4, "aero_illuminating_ratio": 0.125},
            "spaces_evaluated": len(findings) if spaces is None else spaces,
            "violations": violations, "spaces_undetermined": undetermined,
            "monostanza": {"applicable": None, "status": "undetermined", "reason": "no fixture"},
            "findings": findings}


def test_escaping_and_self_containment() -> None:
    hostile = '<script>alert(1)</script>'
    rep = _report([_finding(hostile, "habitable", False, True, False,
                            notes=[f'note with {hostile} & "quotes"'])], 1, 0)
    out = R.render_report(rep)
    _check("renderer_escapes_hostile_name_and_notes",
           "<script>" not in out and "&lt;script&gt;" in out)
    low = out.lower()
    _check("renderer_output_self_contained",
           "http://" not in low and "https://" not in low
           and "src=" not in low and "@import" not in low)
    _check("renderer_deterministic", R.render_report(rep) == out)


def test_ternary_badges_and_verdict_words() -> None:
    rep = _report([
        _finding("ok", "habitable", True, True, True),
        _finding("bad", "habitable", False, True, False),
        _finding("unk", "habitable", None, True, None),
        _finding("bagno", "accessory", True, True, None),
    ], 1, 1)
    out = R.render_report(rep)
    _check("badge_pass_present", 'class="badge pass"' in out)
    _check("badge_fail_present", 'class="badge fail"' in out)
    _check("badge_undet_present", 'class="badge undet"' in out)
    _check("badge_accessory_aero_is_na", 'class="badge na"' in out)
    _check("verdict_violations", ">VIOLAZIONE<" in out)
    out2 = R.render_report(_report([_finding("unk", "habitable", None, True, None)], 0, 1))
    _check("verdict_undetermined_never_compliant",
           ">NON DETERMINABILE<" in out2 and ">CONFORME<" not in out2)
    out3 = R.render_report(_report([_finding("ok", "habitable", True, True, True)], 0, 0))
    _check("verdict_compliant", ">CONFORME<" in out3)
    out4 = R.render_report(_report([], 0, 0, spaces=0))
    _check("verdict_no_spaces_not_certifiable", ">NON CERTIFICABILE<" in out4)


def test_practitioner_language_from_interviews() -> None:
    """R1/R3 findings (interviews #1-#2): fractions are the practitioner's native language;
    the giustificazione column and the declared epoca metadata come verbatim from interview #2."""
    # exact reciprocal bars render as clean fractions
    _check("frac_exact_eighth", R._frac(0.125) == "1/8")
    _check("frac_exact_tenth", R._frac(0.1) == "1/10")
    # a measured 0.12 must NOT be beautified to 1/8 (it would suggest compliance): 1/8,3
    _check("frac_never_beautified", R._frac(0.12) == "1/8,3")
    _check("frac_zero_empty", R._frac(0.0) == "" and R._frac(None) == "")
    rep = _report([_finding("ok", "habitable", True, True, True)], 0, 0)
    out = R.render_report(rep)
    _check("bar_shown_as_fraction", "1/8" in out)
    _check("giustificazione_column_present",
           "Giustificazione del tecnico" in out and 'class="giust"' in out)
    # epoca: declared metadata, only when passed, never evaluated
    out_epoca = R.render_report(rep, epoca="ante 1975")
    _check("epoca_line_rendered",
           "ante 1975" in out_epoca and "dichiarata" in out_epoca)
    _check("epoca_absent_by_default", "Epoca di realizzazione" not in out)
    _check("epoca_escaped", "<script>" not in R.render_report(rep, epoca="<script>x</script>"))


def test_italian_engine_notes() -> None:
    """Adversarial finding post-interviste: un report IT-first non mostra note inglesi.
    Le note note del motore si traducono via _note_it; una nota sconosciuta passa INVARIATA."""
    f = _finding("bad", "habitable", False, True, False,
                 notes=["SHACL: aero-illuminating ratio below 1/8 of floor area (DM 1975 art.5)",
                        "SHACL: height below the 2.70 m habitable minimum (DM 1975 art.1)",
                        "una nota sconosciuta resta com'e'"])
    out = R.render_report(_report([f], 1, 0))
    _check("note_it_aero", "rapporto aeroilluminante sotto 1/8 della superficie" in out)
    _check("note_it_height", "altezza sotto il minimo abitabile di 2.70 m" in out)
    _check("note_it_no_english_shacl",
           "below 1/8 of floor area" not in out and "height below the" not in out)
    _check("note_it_unknown_passthrough", "una nota sconosciuta resta com&#x27;e&#x27;" in out
           or "una nota sconosciuta resta com'e'" in out)
    _check("note_it_accessory_na",
           "non applicabile ai locali accessori"
           in R._note_it("aero ratio N/A for accessory room (separate ventilation rules)"))


def test_conformity_deltas() -> None:
    """Interview #2 (art. 36-bis): a failing check shows HOW FAR from conformity — indicative,
    never on passing rooms."""
    bad = _finding("salotto", "habitable", False, False, False)
    bad["height_m"] = 2.5
    bad["aero_ratio"] = 0.1
    bad["window_area_m2"] = 1.0        # floor 10.0, bar 0.125 -> serve 1.25 -> mancano 0.25
    out = R.render_report(_report([bad], 1, 0))
    _check("delta_aero_missing_m2", "mancano ~0,25 m² di superficie finestrata" in out)
    _check("delta_aero_names_the_bar", "per il 1/8" in out)
    _check("delta_height_gap", "altezza sotto il minimo di 0,20 m" in out)
    ok = _finding("studio", "habitable", True, True, True)
    out2 = R.render_report(_report([ok], 0, 0))
    _check("delta_absent_on_passing_room", "mancano" not in out2 and "sotto il minimo" not in out2)
    und = _finding("cantina", "habitable", None, True, None)
    out3 = R.render_report(_report([und], 0, 1))
    _check("delta_absent_on_undetermined", "mancano" not in out3)


def test_envelope_accepted() -> None:
    rep = _report([_finding("ok", "habitable", True, True, True)], 0, 0)
    envelope = {"verdict": "compliant",
                "pack": {"id": "LOMBARDY_MOCK", "description": "mock regional (not law)"},
                "model": {"filename": "upload.ifc", "schema": "IFC4"}, "report": rep}
    out = R.render_report(envelope)
    _check("envelope_pack_id_rendered", "LOMBARDY_MOCK" in out)
    _check("envelope_filename_rendered", "upload.ifc" in out)


def test_renders_real_fzk_report() -> None:
    if not _FZK_REPORT.exists():
        _skip("renders_real_fzk_report", "fixture report absent — regenerate via checker.py")
        return
    data = json.loads(_FZK_REPORT.read_text(encoding="utf-8"))
    out = R.render_report(data, title="FZK-Haus — verifica DM 1975")
    _check("fzk_report_renders_all_spaces",
           out.count("<tr>") == data["spaces_evaluated"] + 1)   # +1 header row
    _check("fzk_report_verdict_matches_engine",
           (">VIOLAZIONE<" in out) == bool(data["violations"]))
    _check("fzk_report_carries_engine_notes", "SHACL:" in out)


def main() -> int:
    test_escaping_and_self_containment()
    test_ternary_badges_and_verdict_words()
    test_practitioner_language_from_interviews()
    test_italian_engine_notes()
    test_conformity_deltas()
    test_envelope_accepted()
    test_renders_real_fzk_report()
    print(f"\n{_PASS}/{_PASS + _FAIL} passed, {_SKIP} skipped")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
