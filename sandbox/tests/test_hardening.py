#!/usr/bin/env python3
"""P0 stabilization shield (code-audit remediation) — fail-closed hardening of the geometry/unit/
empty-model paths so a malformed or non-conformant IFC can never launder a silent COMPLIANT pass.

Covers (audit findings):
  C-1  window_area rejects non-positive / non-numeric dims (negatives no longer fabricate +area).
  M-5  space_floor_area / _qty reject non-positive + non-finite quantities.
  C-2  length_scale_to_m RAISES when no project LENGTHUNIT resolves (no silent 1.0 = 1000x misread).
  H-1  main() treats spaces_evaluated == 0 as not-certifiable (non-zero exit, no vacuous pass).

Run either way:
    python test_hardening.py     # plain asserts, prints PASS/FAIL/SKIP, exit 1 on failure
    pytest test_hardening.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_SANDBOX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SANDBOX))

import checker as C  # noqa: E402  (env has ifcopenshell; START CONTROLS run the checker)

_PASS = 0
_FAIL = 0
_SKIP = 0


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


def _raises(fn, exc=Exception) -> bool:
    try:
        fn()
    except exc:
        return True
    except Exception:  # noqa: BLE001
        return False
    return False


class _FakeWin:
    def __init__(self, h, w):
        self.OverallHeight = h
        self.OverallWidth = w


class _FakeSpace:
    pass


# ------------------------------------------------------------- C-1: window_area positivity
def test_window_area_positivity() -> None:
    # no Qto fallback for the fake objects -> isolate the attribute path.
    saved = C.ue.get_psets
    C.ue.get_psets = lambda *a, **k: {}
    try:
        _check("window_positive_ok", C.window_area(_FakeWin(2.0, 1.5), 1.0) == 3.0)
        # the C-1 bug: two negatives must NOT fabricate +2.0 area.
        _check("window_both_negative_rejected", C.window_area(_FakeWin(-2.0, -1.0), 1.0) is None)
        _check("window_one_negative_rejected", C.window_area(_FakeWin(2.0, -1.0), 1.0) is None)
        _check("window_zero_rejected", C.window_area(_FakeWin(0.0, 1.5), 1.0) is None)
        # M-3: a non-numeric vendor dim must not crash the report -> None (fall-through), no exception.
        _check("window_nonnumeric_no_crash", C.window_area(_FakeWin("oops", 1.5), 1.0) is None)
        # scale is applied (mm-window with scale 0.001).
        _check("window_scale_applied", abs(C.window_area(_FakeWin(1000.0, 1000.0), 0.001) - 1.0) < 1e-9)
    finally:
        C.ue.get_psets = saved


# ------------------------------------------------------- M-5: area / _qty positivity + finiteness
def test_quantity_positivity() -> None:
    qname = list(C._SPACE_QTO)[0]

    def _with(area):
        saved = C.ue.get_psets
        C.ue.get_psets = lambda *a, **k: {qname: {"NetFloorArea": area}}
        try:
            return C.space_floor_area(_FakeSpace(), 1.0)
        finally:
            C.ue.get_psets = saved

    _check("area_positive_ok", _with(12.0) == 12.0)
    _check("area_negative_rejected", _with(-5.0) is None)
    _check("area_zero_rejected", _with(0.0) is None)
    _check("area_nan_rejected", _with(float("nan")) is None)
    _check("area_inf_rejected", _with(float("inf")) is None)
    # _qty itself rejects a non-positive height (covers space_height too).
    saved = C.ue.get_psets
    C.ue.get_psets = lambda *a, **k: {list(C._SPACE_QTO)[0]: {"Height": -2.8}}
    try:
        _check("qty_negative_height_rejected", C.space_height(_FakeSpace(), 1.0) is None)
    finally:
        C.ue.get_psets = saved


# ------------------------------------------------------- C-2: length unit fail-closed
class _U:
    def __init__(self, t):
        self.UnitType = t


class _UIC:
    def __init__(self, units):
        self.Units = units


class _Proj:
    def __init__(self, uic):
        self.UnitsInContext = uic


class _Model:
    def __init__(self, projs):
        self._projs = projs

    def by_type(self, t):
        return self._projs if t == "IfcProject" else []


def test_length_unit_fail_closed() -> None:
    with_len = _Model([_Proj(_UIC([_U("AREAUNIT"), _U("LENGTHUNIT")]))])
    without = _Model([_Proj(_UIC([_U("AREAUNIT"), _U("TIMEUNIT")]))])
    no_proj = _Model([])
    _check("has_length_unit_true", C._has_length_unit(with_len) is True)
    _check("has_length_unit_false", C._has_length_unit(without) is False)
    _check("no_project_false", C._has_length_unit(no_proj) is False)
    # the C-2 fix: no LENGTHUNIT -> RAISE (refuse the silent 1.0), not a guessed scale.
    _check("missing_length_unit_raises", _raises(lambda: C.length_scale_to_m(without), ValueError))
    _check("no_project_raises", _raises(lambda: C.length_scale_to_m(no_proj), ValueError))
    # a real fixture (declares METRE) must resolve normally (scale 1.0), not raise.
    try:
        import ifcopenshell
    except Exception:  # noqa: BLE001
        _skip("real_fixture_resolves", "ifcopenshell absent")
        return
    fx = _SANDBOX / "data" / "AC20-FZK-Haus.ifc"
    if not fx.exists():
        _skip("real_fixture_resolves", "fixture absent")
        return
    m = ifcopenshell.open(str(fx))
    _check("real_fixture_resolves", abs(C.length_scale_to_m(m) - 1.0) < 1e-9)


# ------------------------------------------------------- H-1: zero-IfcSpace not-certifiable
def test_zero_space_not_certifiable() -> None:
    fake_report = {
        "schema": "IFC4", "spaces_evaluated": 0, "violations": 0, "spaces_undetermined": 0,
        "salva_casa": False, "findings": [],
    }
    saved = C.run
    C.run = lambda *a, **k: fake_report
    try:
        rc = C.main(["dummy.ifc"])
    finally:
        C.run = saved
    # a model with no IfcSpace is uncheckable, NOT compliant -> non-zero exit (was a vacuous 0).
    _check("zero_space_exits_nonzero", rc != 0)


def main() -> int:
    test_window_area_positivity()
    test_quantity_positivity()
    test_length_unit_fail_closed()
    test_zero_space_not_certifiable()
    print(f"\n{_PASS}/{_PASS + _FAIL} passed, {_SKIP} skipped")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
