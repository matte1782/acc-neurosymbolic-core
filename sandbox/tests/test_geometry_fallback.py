#!/usr/bin/env python3
"""Stage 3 Part 3 unit tests.

Task A0 (compliant-completeness, SHIPPED): SpaceFinding.compliant must be occupancy-aware so a
partial result (one applicable check resolved, the other still None) can never silently pass.
  - habitable / unknown require BOTH height_ok and aero_ok (1/8 aero applies);
  - accessory requires only height_ok (aero is N/A);
  - any required check None => compliant is None (undetermined), never True.

Phase-0 geometry decision (recorded, see sandbox/STAGE3_PART3_PROBE.md): geometry-derived
HEIGHT and AREA are NOT defensible NET quantities on the only no-quantity fixture (Revit Duplex)
and window-by-containment cannot reproduce the boundary mapping exactly on the ground-truth
fixtures, so Tasks A/B/C are NOT implemented. The cross-check tests below assert that finding
directly against the live fixtures (skipped if a fixture is absent), so the "geometry is a strict,
ground-truth-validated fallback" invariant is locked in as a regression, not just prose.

100% offline for the A0 cases (no IFC). The geometry cross-checks load the real fixtures and are
SKIPPED (counted, never failed) when a data/*.ifc is missing.

Run either way:
    python test_geometry_fallback.py     # plain asserts, prints PASS/FAIL/SKIP, exit 1 on any failure
    pytest test_geometry_fallback.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_SANDBOX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SANDBOX))  # import sandbox/checker.py

import checker as C  # noqa: E402

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


def _finding(occupancy: str, height_ok, aero_ok) -> C.SpaceFinding:
    """Minimal SpaceFinding to exercise the compliant property only."""
    return C.SpaceFinding(
        global_id="x", name="x", occupancy=occupancy,
        height_m=None, floor_area_m2=None, window_area_m2=0.0, aero_ratio=None,
        height_required_m=2.70, height_ok=height_ok, aero_ok=aero_ok,
    )


# ----------------------------------------------------------------------------- Task A0
def test_a0_compliant_completeness() -> None:
    # habitable: height resolved but aero NOT evaluated => undetermined, NOT a pass.
    _check("habitable_height_only_is_undetermined",
           _finding("habitable", height_ok=True, aero_ok=None).compliant is None)
    # unknown is treated with the habitable-strength rule => same.
    _check("unknown_height_only_is_undetermined",
           _finding("unknown", height_ok=True, aero_ok=None).compliant is None)
    # accessory: aero is N/A, so height alone is sufficient to pass.
    _check("accessory_height_only_is_compliant",
           _finding("accessory", height_ok=True, aero_ok=None).compliant is True)
    # habitable with BOTH checks present and true => compliant.
    _check("habitable_both_true_is_compliant",
           _finding("habitable", height_ok=True, aero_ok=True).compliant is True)
    # habitable with both present, one failing => violation (False), still determinate.
    _check("habitable_aero_fail_is_violation",
           _finding("habitable", height_ok=True, aero_ok=False).compliant is False)
    # accessory with height failing => violation.
    _check("accessory_height_fail_is_violation",
           _finding("accessory", height_ok=False, aero_ok=None).compliant is False)
    # nothing measured => undetermined for every occupancy.
    for occ in ("habitable", "unknown", "accessory"):
        _check(f"all_none_is_undetermined[{occ}]",
               _finding(occ, height_ok=None, aero_ok=None).compliant is None)


# --------------------------------------------------------- Phase-0 geometry findings (locked in)
def _open(fixture: str):
    try:
        import ifcopenshell
        import ifcopenshell.geom  # noqa: F401
    except Exception:  # noqa: BLE001
        return None, None
    path = _SANDBOX / "data" / fixture
    if not path.exists():
        return None, None
    return ifcopenshell.open(str(path)), str(path)


def _shape_all(model):
    """Shape every IfcSpace and extract its geom metrics defensively (mirrors probe_geom.py).
    IMPORTANT: the shape object OWNS the vertex buffer — `create_shape(...).geometry` discards
    the shape and leaves geometry.verts EMPTY, so the shape must stay alive while metrics are
    read. We therefore compute (z, footprint, volume) here, while `shape` is referenced, and
    return plain floats. Spaces whose shape is empty/degenerate are skipped."""
    import ifcopenshell.geom
    import ifcopenshell.util.shape as ushape
    st = ifcopenshell.geom.settings()  # defaults => METRES
    out = []
    for sp in model.by_type("IfcSpace"):
        try:
            shape = ifcopenshell.geom.create_shape(st, sp)  # keep alive for the metric reads
            geom = shape.geometry
            if len(geom.verts) < 9:  # <3 vertices: empty/degenerate triangulation
                continue
            out.append((sp, ushape.get_z(geom), ushape.get_footprint_area(geom),
                        ushape.get_volume(geom)))
        except Exception:  # noqa: BLE001
            pass
    return out


def test_geom_height_is_net_on_ground_truth_but_gross_on_duplex() -> None:
    """The Phase-0 reason Task A (height) was NOT shipped, asserted on the live fixtures:
       on FZK prismatic spaces geom Z-extent == Qto Height (net), but on EVERY shapeable Duplex
       space geom Z-extent lands within a hair of the GROSS PSet Unbounded Height — never the
       100-200 mm below it that a true net clear height would show. So Duplex height is gross."""
    import ifcopenshell.util.element as ue
    import ifcopenshell.util.unit as uu

    fzk, _ = _open("AC20-FZK-Haus.ifc")
    if fzk is None:
        _skip("geom_height_net_on_fzk_prismatic", "fixture/ifcopenshell absent")
    else:
        scale = uu.calculate_unit_scale(fzk)
        ok = checked = 0
        for sp, z, fp, vol in _shape_all(fzk):
            qto_h = C.space_height(sp, scale)
            prism = (vol / fp / z) if (fp and z) else 0.0
            if prism > 0.99 and qto_h:  # prismatic, has Qto height
                checked += 1
                ok += 1 if abs(z - qto_h) < 1e-3 else 0  # geom Z-extent == net Qto height exactly
        _check("geom_height_net_on_fzk_prismatic", checked >= 5 and ok == checked)

    dup, _ = _open("Duplex_A_20110907.ifc")
    if dup is None:
        _skip("geom_height_gross_on_duplex", "fixture/ifcopenshell absent")
    else:
        gross_only = True
        seen = 0
        for sp, z, fp, vol in _shape_all(dup):
            if not fp:  # degenerate (stair/shaft) — skip
                continue
            unb = ue.get_psets(sp).get("PSet_Revit_Dimensions", {}).get("Unbounded Height")
            if unb is None:
                continue
            seen += 1
            # geom Z-extent is the GROSS floor-to-floor: at most a thin finish below Unbounded
            # Height, never the >=0.1 m a net clear height would be (R301: exactly equal).
            gross_only = gross_only and (0.0 <= (float(unb) - z) < 0.05)
        _check("geom_height_gross_on_duplex", seen >= 15 and gross_only)


def test_geom_area_is_gross_not_net_on_ground_truth() -> None:
    """The Phase-0 reason Task B (area) was NOT shipped: geom footprint == GrossFloorArea, not the
       NetFloorArea the rule needs (FZK prismatic: gross/net ~= 1.031, geom matches gross)."""
    import ifcopenshell.util.element as ue

    fzk, _ = _open("AC20-FZK-Haus.ifc")
    if fzk is None:
        _skip("geom_area_equals_gross_not_net", "fixture/ifcopenshell absent")
        return
    matched_gross = checked = 0
    for sp, z, fp, vol in _shape_all(fzk):
        q = ue.get_psets(sp, qtos_only=True).get("BaseQuantities", {})
        net, gross = q.get("NetFloorArea"), q.get("GrossFloorArea")
        prism = (vol / fp / z) if (fp and z) else 0.0
        if prism > 0.99 and net is not None and gross is not None and abs(net - gross) > 0.05:
            checked += 1
            # geom footprint matches GROSS, and is measurably larger than NET => not a net area.
            if abs(fp - gross) < 1e-2 and (fp - net) > 0.05:
                matched_gross += 1
    _check("geom_area_equals_gross_not_net", checked >= 3 and matched_gross == checked)


def main() -> int:
    test_a0_compliant_completeness()
    test_geom_height_is_net_on_ground_truth_but_gross_on_duplex()
    test_geom_area_is_gross_not_net_on_ground_truth()
    print(f"\n{_PASS}/{_PASS + _FAIL} passed, {_SKIP} skipped")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
