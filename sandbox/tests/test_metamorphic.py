#!/usr/bin/env python3
"""Metamorphic tests (audit research) — ORACLE-FREE invariants that need no ground-truth verdict,
only a relation that must hold between an input and a transformed input. These catch C-1/C-2 class
defects that the circular control oracle (outputs of the current code) structurally cannot.

  MR1 (C-1): injecting a NON-physical (negative-dim) serving window can only move a verdict toward
             stricter (more/equal violations) — invalid geometry can NEVER manufacture compliance.
  MR2 (C-2): REMOVING the project length unit must turn a verdict into a REFUSAL (scale unknowable),
             never a normal verdict at an assumed 1.0.
  MR3 (C-2): a model that DECLARES a non-metre unit (mm) must still resolve (be processed), not be
             refused — the safety raise must not over-reject declared units.

Self-contained: mutates FZK-Haus in memory -> temp file -> run(). SKIPS (counted) if absent.

    python test_metamorphic.py     # PASS/FAIL/SKIP, exit 1 on failure
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


def _ifc():
    try:
        import ifcopenshell
        return ifcopenshell
    except Exception:  # noqa: BLE001
        return None


def _serving_windows(space):
    return [getattr(r, "RelatedBuildingElement", None) for r in (space.BoundedBy or [])
            if getattr(r, "RelatedBuildingElement", None) is not None
            and getattr(r, "RelatedBuildingElement").is_a("IfcWindow")]


def _aero_violation_space(ifc, path):
    m = ifc.open(str(path))
    scale = C.length_scale_to_m(m)
    for s in m.by_type("IfcSpace"):
        f = C.check_space(s, scale, False, C.Thresholds())
        if (f.compliant is False and f.occupancy != "accessory"
                and f.height_ok is True and f.aero_ok is False and _serving_windows(s)):
            return s.GlobalId
    return None


def _run_tmp(ifc, model):
    d = tempfile.mkdtemp()
    p = os.path.join(d, "mr.ifc")
    model.write(p)
    return C.run(p)


def test_mr1_invalid_geometry_cannot_help() -> None:
    ifc = _ifc()
    if ifc is None or not _FZK.exists():
        _skip("MR1_invalid_window_cannot_reduce_violations", "ifcopenshell/fixture absent")
        return
    base = C.run(str(_FZK))["violations"]
    gid = _aero_violation_space(ifc, _FZK)
    if gid is None:
        _skip("MR1_invalid_window_cannot_reduce_violations", "no aero-violation space w/ window")
        return
    m = ifc.open(str(_FZK))
    sp = next(s for s in m.by_type("IfcSpace") if s.GlobalId == gid)
    w = _serving_windows(sp)[0]
    w.OverallHeight, w.OverallWidth = -50.0, -50.0   # fabricated +2500 m2 under the old guard
    rep = _run_tmp(ifc, m)
    # metamorphic: garbage geometry must NOT reduce violations, and the target stays non-compliant.
    _check("MR1_violations_not_reduced", rep["violations"] >= base)
    tgt = next(f for f in rep["findings"] if f["global_id"] == gid)
    _check("MR1_target_not_compliant", tgt["compliant"] is not True)


def test_mr2_no_unit_becomes_refusal() -> None:
    ifc = _ifc()
    if ifc is None or not _FZK.exists():
        _skip("MR2_no_unit_refused", "ifcopenshell/fixture absent")
        return
    m = ifc.open(str(_FZK))
    for proj in m.by_type("IfcProject"):
        uic = getattr(proj, "UnitsInContext", None)
        if uic is not None:
            uic.Units = [u for u in uic.Units if getattr(u, "UnitType", None) != "LENGTHUNIT"]
    raised = False
    try:
        _run_tmp(ifc, m)
    except Exception:  # noqa: BLE001
        raised = True
    _check("MR2_no_unit_refused", raised)


def test_mr3_declared_mm_still_processes() -> None:
    ifc = _ifc()
    if ifc is None or not _FZK.exists():
        _skip("MR3_declared_mm_processes", "ifcopenshell/fixture absent")
        return
    m = ifc.open(str(_FZK))
    for proj in m.by_type("IfcProject"):
        uic = getattr(proj, "UnitsInContext", None)
        for u in (getattr(uic, "Units", None) or []):
            if getattr(u, "UnitType", None) == "LENGTHUNIT" and u.is_a("IfcSIUnit"):
                u.Prefix = "MILLI"
    ran = False
    try:
        _run_tmp(ifc, m)
        ran = True
    except Exception:  # noqa: BLE001
        ran = False
    _check("MR3_declared_mm_processes", ran)


def main() -> int:
    test_mr1_invalid_geometry_cannot_help()
    test_mr2_no_unit_becomes_refusal()
    test_mr3_declared_mm_still_processes()
    print(f"\n{_PASS}/{_PASS + _FAIL} passed, {_SKIP} skipped")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
