#!/usr/bin/env python3
"""ADR-018 unit tests — the 'dirty BIM' spatial fallback (audit M-8).

Contract pinned here (see ADR-018 and the Phase-0 probe it records):
  GATE      — the fallback exists ONLY for a model that omits IfcRelSpaceBoundary entirely.
              A boundary-bearing model (all three fixtures) never reaches the geometry pass;
              Institute 402/403 carry a COMPLETE 21-rel BoundedBy set asserting no windows —
              their violations are the model's own testimony and stay frozen.
  SUPERSET  — bbox-proximity candidates must be a SUPERSET of the true IfcRelSpaceBoundary
              serving set per space on the ground-truth fixtures (0 DROPS at the shipped eps;
              ADDS are tolerated by design). This is what makes the candidate sum a valid
              UPPER bound of the true aero numerator.
  SEMANTICS — the upper bound can do exactly two things: CONFIRM a violation (even the most
              generous reading fails the bar) or DEMOTE a would-be violation-by-zero to
              UNDETERMINED. It can NEVER mint a pass. Unshapeable/unmeasurable inputs push
              toward UNDETERMINED (fail-closed), never toward violation-kept or pass.

Run either way:
    python test_spatial_fallback.py     # prints PASS/FAIL/SKIP, exit 1 on any failure
    pytest test_spatial_fallback.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_SANDBOX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SANDBOX))

import checker as C          # noqa: E402

_PASS = _FAIL = _SKIP = 0
_FZK = _SANDBOX / "data" / "AC20-FZK-Haus.ifc"
_INSTITUTE = _SANDBOX / "data" / "AC20-Institute-Var-2.ifc"
_DUPLEX = _SANDBOX / "data" / "Duplex_A_20110907.ifc"
_TMPROOT = tempfile.TemporaryDirectory(prefix="adr018_")


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


def _ifc():
    try:
        import ifcopenshell
        import ifcopenshell.geom  # noqa: F401
        return ifcopenshell
    except Exception:  # noqa: BLE001
        return None


def _new_model(ifc, space_name="Soggiorno"):
    f = ifc.file(schema="IFC4")
    metre = f.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")
    ua = f.create_entity("IfcUnitAssignment", Units=[metre])
    f.create_entity("IfcProject", GlobalId=ifc.guid.new(), Name="ADR018-synthetic",
                    UnitsInContext=ua)
    space = f.create_entity("IfcSpace", GlobalId=ifc.guid.new(), Name=space_name)
    qto = f.create_entity(
        "IfcElementQuantity", GlobalId=ifc.guid.new(), Name="BaseQuantities",
        Quantities=[
            f.create_entity("IfcQuantityLength", Name="Height", LengthValue=3.10),
            f.create_entity("IfcQuantityArea", Name="NetFloorArea", AreaValue=10.0),
        ])
    f.create_entity("IfcRelDefinesByProperties", GlobalId=ifc.guid.new(),
                    RelatedObjects=[space], RelatingPropertyDefinition=qto)
    return f, space


def _run_tmp(f, name="m.ifc"):
    d = tempfile.mkdtemp(dir=_TMPROOT.name)
    p = os.path.join(d, name)
    f.write(p)
    return C.run(p)


def _truth_map(m):
    """{space GlobalId: set of window GlobalIds} via the real boundary rels."""
    out = {}
    for s in m.by_type("IfcSpace"):
        out[s.GlobalId] = {w.GlobalId for w, _rels in C.serving_window_boundaries(s)}
    return out


# ------------------------------------------------------------------ 1. the model-level gate
def test_gate_inert_on_boundary_bearing_models() -> None:
    ifc = _ifc()
    if ifc is None:
        _skip("gate_inert_on_boundary_bearing_models", "ifcopenshell absent")
        return
    # A boundary-BEARING synthetic model must never consult the geometry pass at all.
    f, space = _new_model(ifc)
    win = f.create_entity("IfcWindow", GlobalId=ifc.guid.new(), Name="W1",
                          OverallHeight=1.0, OverallWidth=1.2)
    f.create_entity("IfcRelSpaceBoundary", GlobalId=ifc.guid.new(), RelatingSpace=space,
                    RelatedBuildingElement=win, PhysicalOrVirtualBoundary="PHYSICAL",
                    InternalOrExternalBoundary="EXTERNAL")
    original = C.spatial_window_candidates

    def _must_not_run(*_a, **_k):
        raise AssertionError("spatial_window_candidates consulted on a boundary-bearing model")

    C.spatial_window_candidates = _must_not_run
    try:
        rep = _run_tmp(f)
    finally:
        C.spatial_window_candidates = original
    tgt = rep["findings"][0]
    _check("gate_geometry_pass_not_consulted", tgt["aero_ok"] is False)   # ADR-017 path intact
    _check("gate_no_adr018_notes", not any("ADR-018" in n for n in tgt["notes"]))


def test_institute_402_403_untouched() -> None:
    """The user-facing step-3 verification, with the premise CORRECTED by the Phase-0 probe:
    402/403 do NOT have missing boundaries — each carries a complete BoundedBy set (21 rels,
    walls+slabs, no broken rels) asserting zero windows. The gated fallback therefore leaves
    them exactly as the frozen controls pin: the model's own honest violations."""
    ifc = _ifc()
    if ifc is None or not _INSTITUTE.exists():
        _skip("institute_402_403_untouched", "ifcopenshell/fixture absent")
        return
    m = ifc.open(str(_INSTITUTE))
    _check("institute_is_boundary_bearing", len(m.by_type("IfcRelSpaceBoundary")) == 1000)
    for name in ("402", "403"):
        sp = next(s for s in m.by_type("IfcSpace") if s.Name == name)
        rels = list(sp.BoundedBy or [])
        broken = [r for r in rels if getattr(r, "RelatedBuildingElement", None) is None]
        wins = C.serving_windows(sp)
        _check(f"institute_{name}_boundaries_complete_no_windows",
               len(rels) == 21 and not broken and not wins)
    rep = C.run(str(_INSTITUTE))
    viol = {f["global_id"] for f in rep["findings"] if f["compliant"] is False}
    _check("institute_frozen_violations_held",
           viol == {"0jbV$RErb7o9P7rp7ALEd$", "3txvJd9V1BPhyU$48F$mnF"})
    _check("institute_no_adr018_notes",
           not any("ADR-018" in n for f in rep["findings"] for n in f["notes"]))


# ------------------------------------------------------------------ 2. the superset contract
def test_superset_contract_on_ground_truth() -> None:
    """The load-bearing premise: at the shipped eps, bbox candidates ⊇ the true boundary
    mapping (0 DROPS) on every ground-truth fixture. One drop invalidates the upper bound."""
    ifc = _ifc()
    for fixture, label in ((_FZK, "fzk"), (_DUPLEX, "duplex")):
        if ifc is None or not fixture.exists():
            _skip(f"superset_holds_{label}", "ifcopenshell/fixture absent")
            continue
        m = ifc.open(str(fixture))
        truth = _truth_map(m)
        scale = C.length_scale_to_m(m)
        cands = C.spatial_window_candidates(m, scale)
        drops = sum(len(truth[gid] - set(cands.get(gid, ((), 0.0))[0])) for gid in truth)
        _check(f"superset_holds_{label}", drops == 0)


# ------------------------------------------------------------------ 3. stripped-FZK end-to-end
def test_stripped_fzk_semantics() -> None:
    """Strip every IfcRelSpaceBoundary from FZK (the M-8 model class, with known geometry) and
    assert the full ternary contract: no minted pass, no fabricated violation, the provable
    aero violation stands, would-be violations-by-zero demote to undetermined."""
    ifc = _ifc()
    if ifc is None or not _FZK.exists():
        _skip("stripped_fzk_semantics", "ifcopenshell/fixture absent")
        return
    base = C.run(str(_FZK))
    base_by_gid = {f["global_id"]: f for f in base["findings"]}
    m = ifc.open(str(_FZK))
    for r in list(m.by_type("IfcRelSpaceBoundary")):
        m.remove(r)
    d = tempfile.mkdtemp(dir=_TMPROOT.name)
    p = os.path.join(d, "fzk_stripped.ifc")
    m.write(p)
    rep = C.run(p)
    by_gid = {f["global_id"]: f for f in rep["findings"]}
    _check("stripped_all_spaces_still_evaluated", len(by_gid) == len(base_by_gid) == 7)
    # SAFETY: no space may become compliant that was not compliant in the boundary-rich truth.
    minted = [g for g, f in by_gid.items()
              if f["compliant"] is True and base_by_gid[g]["compliant"] is not True]
    _check("stripped_no_minted_pass", not minted)
    # No fabricated violation either: stripped violations ⊆ baseline violations.
    base_viol = {g for g, f in base_by_gid.items() if f["compliant"] is False}
    got_viol = {g for g, f in by_gid.items() if f["compliant"] is False}
    _check("stripped_no_fabricated_violation", got_viol <= base_viol)
    # The provable aero violation (baseline: height ok, aero fail — the big hall whose two
    # windows even at the generous upper bound stay far below 1/8) STANDS, with the note.
    hall = next(g for g, f in base_by_gid.items()
                if f["height_ok"] is True and f["aero_ok"] is False)
    _check("stripped_provable_violation_stands", by_gid[hall]["compliant"] is False)
    _check("stripped_violation_stands_note",
           any("violation stands (ADR-018)" in n for n in by_gid[hall]["notes"]))
    # At least one baseline habitable space demotes to undetermined with the unbounded note
    # (candidates present, upper bound clears the bar -> association unproven).
    demoted = [g for g, f in by_gid.items()
               if f["compliant"] is None and any("ADR-018" in n for n in f["notes"])]
    _check("stripped_demotions_are_undetermined_with_note", len(demoted) >= 4)
    # Accessory spaces (aero N/A) are untouched by the fallback: same verdict as baseline.
    acc_same = all(by_gid[g]["compliant"] == f["compliant"]
                   for g, f in base_by_gid.items() if f["occupancy"] == "accessory")
    _check("stripped_accessory_untouched", acc_same)


# ------------------------------------------------------------------ 4. fail-closed synthetics
def test_fail_closed_unshapeable_and_edge_cases() -> None:
    ifc = _ifc()
    if ifc is None:
        _skip("fail_closed_unshapeable", "ifcopenshell absent")
        return
    # (a) boundary-less model, unshapeable UNMEASURABLE window (no attr/Qto/geometry): the
    # window could serve the space -> unbounded -> UNDETERMINED, never a kept violation.
    f, _space = _new_model(ifc)
    f.create_entity("IfcWindow", GlobalId=ifc.guid.new(), Name="W-ghost")
    rep = _run_tmp(f)
    tgt = rep["findings"][0]
    _check("failclosed_unmeasurable_candidate_undetermined",
           tgt["aero_ok"] is None and tgt["compliant"] is None
           and any("ADR-018" in n for n in tgt["notes"]))
    # (b) boundary-less model, unshapeable but MEASURABLE window whose generous upper bound
    # still fails 1/8 (1.2/10 = 0.12): the violation is provable and stands.
    f2, _space2 = _new_model(ifc)
    f2.create_entity("IfcWindow", GlobalId=ifc.guid.new(), Name="W-small",
                     OverallHeight=1.0, OverallWidth=1.2)
    rep2 = _run_tmp(f2)
    tgt2 = rep2["findings"][0]
    _check("failclosed_upper_below_bar_violation_stands",
           tgt2["aero_ok"] is False and tgt2["compliant"] is False
           and any("violation stands (ADR-018)" in n for n in tgt2["notes"]))
    # (c) same, but the upper bound clears the bar (2.0/10 = 0.2 >= 0.125): association is
    # unproven -> UNDETERMINED, never a pass.
    f3, _space3 = _new_model(ifc)
    f3.create_entity("IfcWindow", GlobalId=ifc.guid.new(), Name="W-big",
                     OverallHeight=1.0, OverallWidth=2.0)
    rep3 = _run_tmp(f3)
    tgt3 = rep3["findings"][0]
    _check("failclosed_upper_clears_bar_never_a_pass",
           tgt3["aero_ok"] is None and tgt3["compliant"] is None)
    # (d) boundary-less model with NO windows at all: nothing to associate — the honest
    # violation-by-zero of the boundary-rich engine is unchanged, no crash.
    f4, _space4 = _new_model(ifc)
    rep4 = _run_tmp(f4)
    tgt4 = rep4["findings"][0]
    _check("failclosed_no_windows_no_crash_violation_stands", tgt4["aero_ok"] is False)


def main() -> int:
    test_gate_inert_on_boundary_bearing_models()
    test_institute_402_403_untouched()
    test_superset_contract_on_ground_truth()
    test_stripped_fzk_semantics()
    test_fail_closed_unshapeable_and_edge_cases()
    print(f"\n{_PASS}/{_PASS + _FAIL} passed, {_SKIP} skipped")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
