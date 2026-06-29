#!/usr/bin/env python3
"""Generate the C-1 / C-2 adversarial IFC corpus by SURGICAL mutation of the conformant fixtures.

Bias-resistance: each fixture introduces exactly ONE pathology into a known-good real file; the
EXPECTED verdict is derived from the IFC schema + statute (see PREREG_C1/C2), NOT from running the
checker, and is pinned in expected_verdicts.json. The corpus is regenerable (gitignored .ifc),
mirroring the data/*.ifc convention.

Run from the repo root:  python research/corpus/gen_adversarial.py
Outputs: research/corpus/adversarial/*.ifc  +  research/corpus/expected_verdicts.json
"""
from __future__ import annotations

import json
import math
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SANDBOX = os.path.join(_REPO, "sandbox")
_DATA = os.path.join(_SANDBOX, "data")
_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "adversarial")
sys.path.insert(0, _SANDBOX)

import ifcopenshell  # noqa: E402
import checker as C  # noqa: E402

_FZK = os.path.join(_DATA, "AC20-FZK-Haus.ifc")


def _serving_windows(model, space):
    out = []
    for rel in (space.BoundedBy or []):
        el = getattr(rel, "RelatedBuildingElement", None)
        if el is not None and el.is_a("IfcWindow"):
            out.append(el)
    return out


def _find_aero_violation_space(path):
    """A habitable space that is a VIOLATION on aero (height ok, aero NOT ok) and has >=1 serving
    window — the discriminating target for C-1 (fabricated window area would flip it to compliant)."""
    m = ifcopenshell.open(path)
    scale = C.length_scale_to_m(m)
    for s in m.by_type("IfcSpace"):
        f = C.check_space(s, scale, False, C.Thresholds())
        if (f.compliant is False and f.occupancy != "accessory"
                and f.height_ok is True and f.aero_ok is False and _serving_windows(m, s)):
            return s.GlobalId, f
    return None, None


def _length_unit(model):
    for proj in model.by_type("IfcProject"):
        uic = getattr(proj, "UnitsInContext", None)
        if uic is None:
            continue
        for u in (getattr(uic, "Units", None) or []):
            if getattr(u, "UnitType", None) == "LENGTHUNIT":
                return proj, uic, u
    return None, None, None


def main() -> int:
    if not os.path.exists(_FZK):
        print(f"SKIP: fixture absent ({_FZK}); corpus is regenerable when fixtures are present.")
        return 0
    os.makedirs(_OUT, exist_ok=True)
    expected = {}

    # ---- C-1: non-physical window geometry ------------------------------------------------
    gid, base = _find_aero_violation_space(_FZK)
    if gid is None:
        print("WARN: no habitable aero-violation space with a serving window found in FZK; "
              "c1_neg_window cannot be made discriminating. Investigate before judging C-1.")
    else:
        # c1_neg_window: set one serving window of that space to LARGE negative dims. Under the
        # pre-fix `if h and w`, (-50)*(-50)=+2500 m^2 fabricated area -> aero passes -> false pass
        # (FZK 5 -> 4). Spec truth: schema-invalid dims contribute no area -> space stays a violation.
        m = ifcopenshell.open(_FZK)
        sp = next(s for s in m.by_type("IfcSpace") if s.GlobalId == gid)
        win = _serving_windows(m, sp)[0]
        win.OverallHeight = -50.0
        win.OverallWidth = -50.0
        p = os.path.join(_OUT, "c1_neg_window.ifc")
        m.write(p)
        expected["c1_neg_window.ifc"] = {
            "pathology": "serving window OverallHeight/Width set to -50/-50 (schema-invalid "
                         "IfcPositiveLengthMeasure) on a habitable aero-violation space",
            "target_gid": gid,
            "expected_total_violations": 5,
            "target_must_not_be_compliant": True,
            "spec_rationale": "IfcPositiveLengthMeasure must be > 0; a non-positive dim yields no "
                              "valid area (DM1975 art.5 numerator = valid windows only) -> the space "
                              "remains the aero violation it already is; FZK total stays 5.",
            "prefix_defect_expected": "pre-fix fabricates +2500 m2 -> space compliant -> FZK 4 "
                                      "(false pass)",
        }
        # c1_zero_window: zero dims (boundary of the old truthiness guard). No fabricated area; the
        # space's real aero is unchanged -> still a violation; FZK stays 5 in BOTH old and new
        # (0 is falsy, so even pre-fix fell through). Included as a no-effect/no-crash control.
        m2 = ifcopenshell.open(_FZK)
        sp2 = next(s for s in m2.by_type("IfcSpace") if s.GlobalId == gid)
        w2 = _serving_windows(m2, sp2)[0]
        w2.OverallHeight = 0.0
        w2.OverallWidth = 0.0
        p2 = os.path.join(_OUT, "c1_zero_window.ifc")
        m2.write(p2)
        expected["c1_zero_window.ifc"] = {
            "pathology": "serving window dims set to 0/0",
            "target_gid": gid,
            "expected_total_violations": 5,
            "target_must_not_be_compliant": True,
            "spec_rationale": "zero area is not a valid window; space stays a violation; FZK 5.",
            "prefix_defect_expected": "none (0 is falsy; pre-fix also fell through) — no-crash control",
        }
        # NOTE: NaN/inf window dims are UNREPRESENTABLE in a written IFC — ifcopenshell raises
        # "Only finite values are allowed" on setArgumentAsDouble. So the IFC-FILE attack surface for
        # OverallHeight/Width is limited to finite negative/zero; NaN/inf can only arise from
        # computation, not a stored attribute. Those paths are covered at FUNCTION level in
        # test_hardening.py (window_area/_qty reject NaN/inf), not by a corpus file.

    # ---- C-2: absent / unresolved length unit ---------------------------------------------
    # c2_no_unit: drop the LENGTHUNIT entry. Spec truth: scale is unknowable -> not-certifiable.
    m4 = ifcopenshell.open(_FZK)
    proj, uic, lu = _length_unit(m4)
    if lu is not None:
        uic.Units = [u for u in uic.Units if getattr(u, "UnitType", None) != "LENGTHUNIT"]
    p4 = os.path.join(_OUT, "c2_no_unit.ifc")
    m4.write(p4)
    expected["c2_no_unit.ifc"] = {
        "pathology": "LENGTHUNIT removed from IfcProject.UnitsInContext",
        "expected": "not_certifiable",
        "spec_rationale": "no declared length unit -> scale undefined -> model cannot be measured "
                          "-> must be REFUSED (not assumed metres).",
        "prefix_defect_expected": "pre-fix: calculate_unit_scale silently returns 1.0 -> proceeds "
                                  "and emits a normal verdict (the defect).",
    }
    # c2_no_project_units: UnitsInContext present but Units emptied -> not-certifiable.
    m5 = ifcopenshell.open(_FZK)
    proj5, uic5, _ = _length_unit(m5)
    if uic5 is not None:
        uic5.Units = []
    p5 = os.path.join(_OUT, "c2_empty_units.ifc")
    m5.write(p5)
    expected["c2_empty_units.ifc"] = {
        "pathology": "IfcUnitAssignment.Units emptied",
        "expected": "not_certifiable",
        "spec_rationale": "no resolvable LENGTHUNIT -> refuse.",
        "prefix_defect_expected": "pre-fix proceeds at scale 1.0.",
    }
    # c2_mm_declared (negative control vs over-rejection): set the SI length unit prefix to MILLI so
    # the file DECLARES millimetres. Spec truth: a declared unit is resolvable -> the model PROCESSES
    # (scale 0.001), it must NOT be refused. (Quantities left as-is: this is the 'declared-unit
    # present' control for GATE-N; magnitude correctness is covered by the metamorphic test.)
    m6 = ifcopenshell.open(_FZK)
    proj6, uic6, lu6 = _length_unit(m6)
    if lu6 is not None and lu6.is_a("IfcSIUnit"):
        lu6.Prefix = "MILLI"
    p6 = os.path.join(_OUT, "c2_mm_declared.ifc")
    m6.write(p6)
    expected["c2_mm_declared.ifc"] = {
        "pathology": "SI length unit prefix set to MILLI (declared millimetres)",
        "expected": "processes",
        "spec_rationale": "a declared length unit is resolvable -> scale 0.001 -> the checker runs "
                          "(it must NOT refuse a file that declares its unit). GATE-N over-reject "
                          "guard.",
        "prefix_defect_expected": "n/a (control): both pre-fix and fix process it.",
    }

    with open(os.path.join(os.path.dirname(_OUT), "expected_verdicts.json"), "w",
              encoding="utf-8") as fh:
        json.dump(expected, fh, indent=2, ensure_ascii=False)
    print(f"generated {len(expected)} adversarial fixtures in {_OUT}")
    for k in expected:
        print("  -", k)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
