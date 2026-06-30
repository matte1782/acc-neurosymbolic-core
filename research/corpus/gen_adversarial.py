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
        # c1_absurd_pos_window (C-1b GATE-S, the REACHABLE false-pass): set the target's first serving
        # window to a huge POSITIVE 500x500 -> 250000 m2. C1-B (positivity) PASSES it (positive +
        # finite), so the fabricated area flips the target (a frozen FZK violation) to COMPLIANT
        # (FZK 5->4). Spec truth: 250000 m2 on a 74.5 m2 floor is non-physical -> untrustworthy ->
        # aero unbounded -> the space is undetermined (FZK viol=4, undet=1); the target NEVER compliant.
        m9 = ifcopenshell.open(_FZK)
        sp9 = next(s for s in m9.by_type("IfcSpace") if s.GlobalId == gid)
        w9 = _serving_windows(m9, sp9)[0]
        w9.OverallHeight = 500.0
        w9.OverallWidth = 500.0
        p9 = os.path.join(_OUT, "c1_absurd_pos_window.ifc")
        m9.write(p9)
        expected["c1_absurd_pos_window.ifc"] = {
            "pathology": "serving window OverallHeight/Width set to 500/500 (250000 m2, >> 74.5 floor)",
            "target_gid": gid,
            "expected_total_violations": 4,
            "target_must_not_be_compliant": True,
            "target_expected_undetermined": True,
            "spec_rationale": "a 250000 m2 window on a 74.5 m2 floor is non-physical -> untrustworthy "
                              "-> aero unbounded -> space undetermined (FZK viol 5->4, undet 0->1); "
                              "target NEVER compliant (and specifically undetermined, not dropped).",
            "prefix_defect_expected": "pre-fix AND C1-B both return 250000 (positive) -> target "
                                      "compliant -> FZK 4 (false pass C1-B does not catch).",
        }
        # c1_inflated_window (C-1b GATE-S, the adversarial-verify bypass, ADR-007c): inflate the
        # target window's bounding-box attr to 72 m2 — still <= the 74.5 m2 floor, so F-C's ">floor"
        # test deems it TRUSTWORTHY — while its real Qto net glazing stays 0.785 m2. If the aero
        # numerator preferred attr (the reopened bug) the target would false-pass (72/74.5=0.97); the
        # CONSERVATIVE min(attr,Qto) numerator uses 0.785 -> target stays a VIOLATION. Guards against
        # reverting to the attr-preferring all-trustworthy branch.
        m10 = ifcopenshell.open(_FZK)
        sp10 = next(s for s in m10.by_type("IfcSpace") if s.GlobalId == gid)
        w10 = _serving_windows(m10, sp10)[0]
        w10.OverallHeight = 9.0
        w10.OverallWidth = 8.0   # 72 m2 <= floor; Qto Area untouched (~0.785)
        p10 = os.path.join(_OUT, "c1_inflated_window.ifc")
        m10.write(p10)
        expected["c1_inflated_window.ifc"] = {
            "pathology": "target window bounding-box attr inflated to 72 m2 (<= 74.5 floor) while Qto stays ~0.785",
            "target_gid": gid,
            "expected_total_violations": 5,
            "target_must_not_be_compliant": True,
            "spec_rationale": "an inflated attr <= floor evades F-C ('>floor'); the conservative "
                              "min(attr,Qto) numerator uses the real 0.785 net glazing -> aero fails "
                              "-> target stays a VIOLATION (FZK 5). Never compliant.",
            "prefix_defect_expected": "attr-preferring all-trustworthy numerator -> 72/74.5 passes -> "
                                      "target compliant -> FZK 4 (false pass the conservative numerator closes).",
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

    # c2_contextdependent_unit (GATE-S, present-but-UNRESOLVABLE): replace the SI metre with an
    # IfcContextDependentUnit (a custom 'SMOOT', UnitType=LENGTHUNIT) — schema-valid but with NO
    # defined SI relationship, so calculate_unit_scale silently falls back to 1.0. Spec truth:
    # unresolvable -> not-certifiable. This is the class the bias-resistant pilot used to DISQUALIFY
    # the presence-only C2-B (research/DECISION_MATRIX.md C-2).
    m7 = ifcopenshell.open(_FZK)
    _, uic7, _ = _length_unit(m7)
    if uic7 is not None:
        dims7 = m7.create_entity("IfcDimensionalExponents", 1, 0, 0, 0, 0, 0, 0)
        cdu = m7.create_entity("IfcContextDependentUnit", Dimensions=dims7, UnitType="LENGTHUNIT",
                               Name="SMOOT")
        uic7.Units = [u for u in uic7.Units if getattr(u, "UnitType", None) != "LENGTHUNIT"] + [cdu]
    p7 = os.path.join(_OUT, "c2_contextdependent_unit.ifc")
    m7.write(p7)
    expected["c2_contextdependent_unit.ifc"] = {
        "pathology": "SI metre replaced by IfcContextDependentUnit (custom 'SMOOT', LENGTHUNIT)",
        "expected": "not_certifiable",
        "spec_rationale": "an IfcContextDependentUnit has no defined SI relationship -> scale "
                          "unresolvable -> calculate_unit_scale silently returns 1.0 -> must REFUSE.",
        "prefix_defect_expected": "pre-fix AND the presence-only C2-B BOTH proceed at scale 1.0 "
                                  "(the hole that disqualified C2-B; C2-F resolvability check refuses).",
    }
    # c2_foot (GATE-N over-reject control for CONVERSION units): replace the SI metre with an
    # IfcConversionBasedUnit 'foot' whose ConversionFactor chains to SI metre (0.3048). Spec truth:
    # resolvable -> PROCESSES at scale 0.3048; the C2-F check must NOT refuse a declared conversion unit.
    m8 = ifcopenshell.open(_FZK)
    _, uic8, _ = _length_unit(m8)
    if uic8 is not None:
        si_m = m8.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")
        dims8 = m8.create_entity("IfcDimensionalExponents", 1, 0, 0, 0, 0, 0, 0)
        mwu = m8.create_entity("IfcMeasureWithUnit",
                               ValueComponent=m8.create_entity("IfcLengthMeasure", 0.3048),
                               UnitComponent=si_m)
        foot = m8.create_entity("IfcConversionBasedUnit", Dimensions=dims8, UnitType="LENGTHUNIT",
                                Name="foot", ConversionFactor=mwu)
        uic8.Units = [u for u in uic8.Units if getattr(u, "UnitType", None) != "LENGTHUNIT"] + [foot]
    p8 = os.path.join(_OUT, "c2_foot.ifc")
    m8.write(p8)
    expected["c2_foot.ifc"] = {
        "pathology": "SI metre replaced by IfcConversionBasedUnit 'foot' (ConversionFactor 0.3048->SI)",
        "expected": "processes",
        "spec_rationale": "a conversion unit chaining to SI is resolvable (scale 0.3048) -> the "
                          "checker must PROCESS it, not refuse (GATE-N over-reject guard).",
        "prefix_defect_expected": "n/a (control): both process; the C2-F fix must keep processing it.",
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
