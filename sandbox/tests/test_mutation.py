#!/usr/bin/env python3
"""Mutation tests (audit research) — prove the P0 guards have POWER, not just presence. For each
fix we re-inject the original bug (the mutant) and assert the safety property is VIOLATED under the
mutant while it HOLDS under HEAD. A guard whose mutant survives (property still holds) is vacuous
confirmation bias; these tests fail loudly if that ever becomes the case.

  C-1 mutant: pre-fix window_area (`if h and w`) -> negative dims fabricate a positive area.
  C-2 mutant: pre-fix scale (no LENGTHUNIT check) -> a unitless model is NOT refused.
  H-1 mutant: pre-fix exit (`violations or undetermined`) -> a zero-space model exits 0 (compliant).

    python test_mutation.py     # PASS/FAIL/SKIP, exit 1 on failure
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_SANDBOX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SANDBOX))

import checker as C  # noqa: E402

_PASS = _FAIL = _SKIP = 0
_FZK = _SANDBOX / "data" / "AC20-FZK-Haus.ifc"


def _check(n, c):
    global _PASS, _FAIL
    if c:
        _PASS += 1; print(f"PASS {n}")
    else:
        _FAIL += 1; print(f"FAIL {n}")


def _skip(n, why):
    global _SKIP
    _SKIP += 1; print(f"SKIP {n} ({why})")


class _FakeWin:
    def __init__(self, h, w):
        self.OverallHeight, self.OverallWidth = h, w


# --- C-1: the mutant must fabricate area; HEAD must reject it ------------------------------
def _mutant_window_area(win, scale):
    h, w = getattr(win, "OverallHeight", None), getattr(win, "OverallWidth", None)
    if h and w:                                    # pre-fix bug: negatives are truthy
        return float(h) * float(w) * (scale ** 2)
    return None


def test_c1_mutant_killed() -> None:
    # mutant exhibits the bug (proves the property is non-vacuous):
    _check("C1_mutant_fabricates_area", _mutant_window_area(_FakeWin(-2.0, -1.0), 1.0) == 2.0)
    # HEAD kills it: window_area rejects negative dims (no Qto fallback on the fake -> None).
    saved = C.ue.get_psets
    C.ue.get_psets = lambda *a, **k: {}
    try:
        _check("C1_head_rejects_negative", C.window_area(_FakeWin(-2.0, -1.0), 1.0) is None)
    finally:
        C.ue.get_psets = saved


# --- C-2: the mutant must NOT refuse a unitless model; HEAD must refuse --------------------
def test_c2_mutant_killed() -> None:
    try:
        import ifcopenshell
        import ifcopenshell.util.unit as uu
    except Exception:  # noqa: BLE001
        _skip("C2_mutant_killed", "ifcopenshell absent")
        return
    if not _FZK.exists():
        _skip("C2_mutant_killed", "fixture absent")
        return
    m = ifcopenshell.open(str(_FZK))
    for proj in m.by_type("IfcProject"):
        uic = getattr(proj, "UnitsInContext", None)
        if uic is not None:
            uic.Units = [u for u in uic.Units if getattr(u, "UnitType", None) != "LENGTHUNIT"]
    p = os.path.join(tempfile.mkdtemp(), "no_unit.ifc")
    m.write(p)
    m2 = ifcopenshell.open(p)
    # mutant (pre-fix scale: no LENGTHUNIT check) silently returns 1.0 — does NOT refuse:
    _check("C2_mutant_does_not_refuse", uu.calculate_unit_scale(m2) == 1)
    # HEAD kills it: length_scale_to_m raises on a unitless model.
    raised = False
    try:
        C.length_scale_to_m(m2)
    except Exception:  # noqa: BLE001
        raised = True
    _check("C2_head_refuses", raised)


# --- H-1: the mutant must pass a zero-space model; HEAD must not ---------------------------
def test_h1_mutant_killed() -> None:
    zero_report = {"schema": "IFC4", "spaces_evaluated": 0, "violations": 0,
                   "spaces_undetermined": 0, "salva_casa": False, "findings": []}

    def _mutant_exit(rep):
        return 1 if (rep["violations"] or rep["spaces_undetermined"]) else 0   # pre-fix bug

    _check("H1_mutant_exits_0_on_zero_space", _mutant_exit(zero_report) == 0)
    saved = C.run
    C.run = lambda *a, **k: zero_report
    try:
        rc = C.main(["dummy.ifc"])
    finally:
        C.run = saved
    _check("H1_head_exits_nonzero_on_zero_space", rc != 0)


def test_c1b_mutant_killed() -> None:
    # C-1b mutant: the old "sum every window_area (incl. an absurd one) with no upper bound" numerator
    # false-passes the aero check; HEAD (F-C + L-2) routes the target to undetermined instead.
    import os
    import tempfile
    try:
        import ifcopenshell
    except Exception:  # noqa: BLE001
        _skip("C1b_mutant_killed", "ifcopenshell absent")
        return
    if not _FZK.exists():
        _skip("C1b_mutant_killed", "fixture absent")
        return
    m = ifcopenshell.open(str(_FZK))
    scale = C.length_scale_to_m(m)
    # find a habitable aero-violation space with a serving window
    gid = None
    for s in m.by_type("IfcSpace"):
        f = C.check_space(s, scale, False, C.Thresholds())
        sw = C.serving_windows(s)
        if f.compliant is False and f.occupancy != "accessory" and f.height_ok and not f.aero_ok and sw:
            gid = s.GlobalId
            break
    if gid is None:
        _skip("C1b_mutant_killed", "no aero-violation space w/ window")
        return
    sp = next(s for s in m.by_type("IfcSpace") if s.GlobalId == gid)
    wins = C.serving_windows(sp)
    wins[0].OverallHeight, wins[0].OverallWidth = 500.0, 500.0   # 250000 m2
    floor = C.space_floor_area(sp, scale)
    # mutant (no upper bound + laundering): numerator includes the absurd 250000 -> ratio passes.
    mutant_num = sum(C.window_area(w, scale) or 0.0 for w in wins)
    _check("C1b_mutant_old_numerator_false_pass",
           (mutant_num / floor) + 1e-9 >= 0.125 and mutant_num > floor)
    # HEAD kills it: the target is undetermined (not compliant).
    p = os.path.join(tempfile.mkdtemp(), "absurd.ifc")
    m.write(p)
    tgt = next(f for f in C.run(p)["findings"] if f["global_id"] == gid)
    _check("C1b_head_undetermined", tgt["compliant"] is None)


def test_c1b_inflation_mutant_killed() -> None:
    # C-1b inflation mutant (ADR-007c): an attr-preferring numerator over all-trustworthy windows
    # false-passes an inflated bounding box (attr <= floor, clears 1/8) whose real Qto contradicts it;
    # HEAD's CONSERVATIVE min(attr,Qto) numerator keeps it a violation.
    import os
    import tempfile
    try:
        import ifcopenshell
    except Exception:  # noqa: BLE001
        _skip("C1b_inflation_mutant_killed", "ifcopenshell absent")
        return
    if not _FZK.exists():
        _skip("C1b_inflation_mutant_killed", "fixture absent")
        return
    m = ifcopenshell.open(str(_FZK))
    scale = C.length_scale_to_m(m)
    gid = None
    for s in m.by_type("IfcSpace"):
        f = C.check_space(s, scale, False, C.Thresholds())
        if (f.compliant is False and f.occupancy != "accessory" and f.height_ok
                and not f.aero_ok and C.serving_windows(s)):
            gid = s.GlobalId
            break
    if gid is None:
        _skip("C1b_inflation_mutant_killed", "no aero-violation space w/ window")
        return
    sp = next(s for s in m.by_type("IfcSpace") if s.GlobalId == gid)
    floor = C.space_floor_area(sp, scale)
    w = C.serving_windows(sp)[0]
    w.OverallHeight, w.OverallWidth = 9.0, 8.0   # 72 m2 bbox, <= floor; Qto stays ~0.785
    wins = C.serving_windows(sp)
    pref_num = sum(C.window_area(x, scale) or 0.0 for x in wins)            # mutant: attr-preferring
    cons_num = sum(min([v for v in C._window_area_bounds(x, scale) if v is not None], default=0.0)
                   for x in wins)                                           # HEAD: conservative
    _check("C1b_mutant_attr_numerator_false_passes", (pref_num / floor) + 1e-9 >= 0.125)
    _check("C1b_conservative_numerator_fails", (cons_num / floor) + 1e-9 < 0.125)
    p = os.path.join(tempfile.mkdtemp(), "inflated.ifc")
    m.write(p)
    tgt = next(f for f in C.run(p)["findings"] if f["global_id"] == gid)
    _check("C1b_head_inflated_not_compliant", tgt["compliant"] is not True)


def main() -> int:
    test_c1_mutant_killed()
    test_c2_mutant_killed()
    test_h1_mutant_killed()
    test_c1b_mutant_killed()
    test_c1b_inflation_mutant_killed()
    print(f"\n{_PASS}/{_PASS + _FAIL} passed, {_SKIP} skipped")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
