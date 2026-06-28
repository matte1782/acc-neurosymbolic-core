#!/usr/bin/env python3
"""Stage 4 Part 2, Task 2 — externalized applicability/selection table (rules/applicability.json).

Verdict-neutral structural refactor: classify() + the check_space height-bar/aero branches now read
a declarative table instead of hardcoded Python tuples + ifs. These tests pin the contract:

  1. EQUIVALENCE (binding): the per-GlobalId projection (occupancy, height_required_m, aero_applies,
     height_ok, aero_ok, compliant) over all 3 fixtures BOTH modes equals tests/equiv_oracle.json
     (captured from the pre-refactor Python) — all 220 rows identical, or it's a regression.
  2. Hint byte-equality incl. codepoints: the table's hint sets are set-equal to the frozen
     _ACCESSORY_HINTS/_HABITABLE_HINTS tuples; U+00FC present in 'küche', absent from 'kuche'.
  3. 'unknown' = strict complement: a name matching no hint -> unknown; no entry stores 'unknown'.
  4. Accessory-first precedence: a name matching BOTH (e.g. 'Badezimmer' -> bad + zimmer) -> accessory.
  5. FAIL-CLOSED: a missing / empty / structurally-invalid table RAISES, never a silent pass.

The equivalence cases load the real fixtures (SKIPPED, counted, never failed, if a data/*.ifc is
absent). The structural cases are 100% offline.

Run either way:
    python test_applicability_table.py     # plain asserts, prints PASS/FAIL/SKIP, exit 1 on failure
    pytest test_applicability_table.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_SANDBOX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SANDBOX))  # import sandbox/checker.py

import checker as C  # noqa: E402

_PASS = 0
_FAIL = 0
_SKIP = 0

_ORACLE = _SANDBOX / "tests" / "equiv_oracle.json"
_FIXTURES = ["data/AC20-FZK-Haus.ifc", "data/AC20-Institute-Var-2.ifc",
             "data/Duplex_A_20110907.ifc"]


def _check(name: str, cond: bool) -> None:
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"PASS {name}")
    else:
        _FAIL += 1
        print(f"FAIL {name}")


def _skip(name: str, why: str) -> None:
    global _SKIP
    _SKIP += 1
    print(f"SKIP {name} ({why})")


def _raises(fn) -> bool:
    try:
        fn()
    except Exception:  # noqa: BLE001 — fail-closed: ANY raise is acceptable here
        return True
    return False


class _FakeSpace:
    """Minimal stand-in: classify() only reads .Name / .LongName."""
    def __init__(self, name, long_name=None):
        self.Name = name
        self.LongName = long_name


# ----------------------------------------------------------------- (1) binding equivalence
def test_equivalence_oracle() -> None:
    try:
        import ifcopenshell
        import ifcopenshell.util.unit as uu
    except Exception:  # noqa: BLE001
        _skip("equivalence_220_rows", "ifcopenshell absent")
        return
    if not _ORACLE.exists():
        _check("equivalence_oracle_present", False)
        return
    oracle = json.loads(_ORACLE.read_text(encoding="utf-8"))

    rows = diffs = present = 0
    for fx in _FIXTURES:
        path = _SANDBOX / fx
        if not path.exists():
            _skip(f"equivalence[{fx}]", "fixture absent")
            continue
        present += 1
        m = ifcopenshell.open(str(path))
        scale = uu.calculate_unit_scale(m)
        for sc in (False, True):
            for s in m.by_type("IfcSpace"):
                f = C.check_space(s, scale, sc, C.Thresholds())
                now = [f.occupancy, f.height_required_m, (f.occupancy != "accessory"),
                       f.height_ok, f.aero_ok, f.compliant]
                key = f"{fx}|{sc}|{f.global_id}"
                rows += 1
                if oracle.get(key) != now:
                    diffs += 1
                    print(f"  DRIFT {key}: {oracle.get(key)} -> {now}")
    _check("equivalence_no_drift", rows > 0 and diffs == 0)
    if present == len(_FIXTURES):
        _check("equivalence_row_count_220", rows == 220)
    else:
        _skip("equivalence_row_count_220", "not all fixtures present")


# --------------------------------------------------- (2) hint byte-equality incl. codepoints
def test_hint_set_equality() -> None:
    t = C.load_applicability()
    _check("accessory_hints_set_equal", set(t.accessory_hints) == set(C._ACCESSORY_HINTS))
    _check("habitable_hints_set_equal", set(t.habitable_hints) == set(C._HABITABLE_HINTS))
    # The load-bearing codepoint pair: both the ASCII and the U+00FC umlaut form must be present.
    _check("kuche_ascii_present", "kuche" in t.habitable_hints)
    _check("kueche_umlaut_present", "küche" in t.habitable_hints)
    _check("umlaut_is_u00fc", "ü" in "küche" and "ü" not in "kuche")
    _check("kuche_distinct_from_kueche", "kuche" != "küche")
    # Art.1 provenance subset is exactly the 4 enumerated Italian accessory tokens (Part 3 anchor).
    data = json.loads((_SANDBOX / "rules" / "applicability.json").read_text(encoding="utf-8"))
    art1 = {h for g in data["occupancy_classes"]["accessory"]["hint_groups"]
            if g["provenance"] == "art1" for h in g["hints"]}
    _check("art1_subset_exact", art1 == set(C._ART1_ACCESSORY_TOKENS))


# ----------------------------------------------------- (3) unknown = strict complement
def test_unknown_strict_complement() -> None:
    _check("no_hint_match_is_unknown", C.classify(_FakeSpace("Zzqxv-no-hint", "12345")) == "unknown")
    t = C.load_applicability()
    _check("unknown_not_a_stored_class", "unknown" not in t.classes)
    data = json.loads((_SANDBOX / "rules" / "applicability.json").read_text(encoding="utf-8"))
    _check("unknown_not_in_json", "unknown" not in data["occupancy_classes"])


# ----------------------------------------------------- (4) accessory-first precedence
def test_accessory_precedence() -> None:
    # 'Badezimmer' contains 'bad' (accessory) AND 'zimmer' (habitable) -> accessory wins.
    _check("badezimmer_is_accessory", C.classify(_FakeSpace("Badezimmer")) == "accessory")
    # sanity: a pure-habitable name still classifies habitable.
    _check("wohnzimmer_is_habitable", C.classify(_FakeSpace("Wohnzimmer")) == "habitable")


# ----------------------------------------------------- (5) fail-closed
def test_fail_closed() -> None:
    _check("missing_file_raises",
           _raises(lambda: C.load_applicability(str(_SANDBOX / "rules" / "_does_not_exist.json"))))
    with tempfile.TemporaryDirectory() as d:
        empty = Path(d) / "empty.json"
        empty.write_text("{}", encoding="utf-8")
        _check("empty_table_raises", _raises(lambda: C.load_applicability(str(empty))))
        # a table missing the habitable class must also raise (no partial fallthrough).
        partial = Path(d) / "partial.json"
        partial.write_text(json.dumps({"occupancy_classes": {"accessory": {}}}), encoding="utf-8")
        _check("partial_table_raises", _raises(lambda: C.load_applicability(str(partial))))
        # storing 'unknown' as a class violates the strict-complement invariant -> raise.
        bad = Path(d) / "bad.json"
        bad.write_text(json.dumps({"occupancy_classes": {
            "accessory": {}, "habitable": {}, "unknown": {}}}), encoding="utf-8")
        _check("stored_unknown_raises", _raises(lambda: C.load_applicability(str(bad))))


def main() -> int:
    test_equivalence_oracle()
    test_hint_set_equality()
    test_unknown_strict_complement()
    test_accessory_precedence()
    test_fail_closed()
    print(f"\n{_PASS}/{_PASS + _FAIL} passed, {_SKIP} skipped")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
