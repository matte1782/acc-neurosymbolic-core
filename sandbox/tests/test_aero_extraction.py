#!/usr/bin/env python3
"""ADR-017 unit tests — relational geometric extraction (IfcRelSpaceBoundary -> acc:aeroRatio).

What ADR-017 shipped, pinned here:
  1. TRAVERSAL — serving_window_boundaries: IfcSpace -> IfcRelSpaceBoundary -> IfcWindow,
     DEDUPLICATED by window GlobalId (duplicate (space, window) boundary records are real on
     Revit Duplex and the old flat rel list double-counted the window into the aero numerator —
     a false-pass direction).
  2. BOUNDARY-GEOMETRY AREA (probe-validated lower bound) — window_boundary_area: last-resort
     window area from the boundary's IfcCurveBoundedPlane polygon (Newell, attribute-level, no
     create_shape). IfcSurfaceOfLinearExtrusion is REFUSED (probed 0.007x-2.99x on Duplex — not
     a lower bound). Verdict semantics: >= bar proves a pass; < bar on a rough source remaps to
     UNDETERMINED (L-2), never a fabricated verdict.
  3. MEASUREMENT REGISTRY — checker.MEASUREMENT_EXTRACTORS (extractor side) mirrors
     orchestrator.SUPPORTED_MEASUREMENT_PATHS (rules side); the loader refuses a pack binding an
     unregistered sh:path; orchestrator.required_measurement_paths identifies what a target
     legal specification requires.
  4. LOMBARDY E2E — the ADR-016 mock regional pack (1/10 aero) emitted by gate_spike.emit_shacl
     runs through the FULL pipeline (ComplianceOrchestrator) on a synthetic FZK-style space with
     an IfcWindow attached via IfcRelSpaceBoundary, and the SAME model flips verdict between the
     DM-1975 pack (1/8) and the regional pack (1/10) purely through the rule packs.

Synthetic IFC4 models are built in-memory with ifcopenshell.file() and written to a temp .ifc so
the FULL pipeline (parse -> extract -> materialize -> pyshacl) is exercised, not a mock.
SKIPPED (counted, never failed) when ifcopenshell is absent; the FZK ground-truth cross-check is
additionally skipped when the fixture .ifc is absent.

Run either way:
    python test_aero_extraction.py     # prints PASS/FAIL/SKIP, exit 1 on any failure
    pytest test_aero_extraction.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_SANDBOX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SANDBOX))

import checker as C          # noqa: E402
import graph as G            # noqa: E402
import orchestrator as O     # noqa: E402

_PASS = _FAIL = _SKIP = 0
_FZK = _SANDBOX / "data" / "AC20-FZK-Haus.ifc"
_INSTITUTE = _SANDBOX / "data" / "AC20-Institute-Var-2.ifc"
# One self-cleaning temp root for every scratch .ifc/.ttl this suite writes (round-6 TQ-6).
_TMPROOT = tempfile.TemporaryDirectory(prefix="adr017_")


def _tmpdir() -> str:
    return tempfile.mkdtemp(dir=_TMPROOT.name)


def _check(name: str, cond: bool) -> None:
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"PASS {name}")
    else:
        _FAIL += 1
        print(f"FAIL {name}")
        # Under pytest the print alone would be swallowed and the node would stay green
        # (round-6 TQ-3): fail the collected test function too. Script mode is unaffected.
        if "pytest" in sys.modules:
            raise AssertionError(f"check failed: {name}")


def _skip(name: str, why: str) -> None:
    global _SKIP
    _SKIP += 1
    print(f"SKIP {name} ({why})")


def _ifc():
    try:
        import ifcopenshell
        return ifcopenshell
    except Exception:  # noqa: BLE001
        return None


# ------------------------------------------------------------------ synthetic model builders
def _new_model(ifc):
    """Minimal IFC4 file that satisfies the fail-closed unit guard (SI METRE) and carries one
    FZK-style habitable IfcSpace with Qto BaseQuantities (Height 3.10 m, NetFloorArea 10 m²)."""
    f = ifc.file(schema="IFC4")
    metre = f.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")
    sqm = f.create_entity("IfcSIUnit", UnitType="AREAUNIT", Name="SQUARE_METRE")
    ua = f.create_entity("IfcUnitAssignment", Units=[metre, sqm])
    f.create_entity("IfcProject", GlobalId=ifc.guid.new(), Name="ADR017-synthetic",
                    UnitsInContext=ua)
    space = f.create_entity("IfcSpace", GlobalId=ifc.guid.new(), Name="Soggiorno",
                            LongName="Soggiorno di prova")
    qto = f.create_entity(
        "IfcElementQuantity", GlobalId=ifc.guid.new(), Name="BaseQuantities",
        Quantities=[
            f.create_entity("IfcQuantityLength", Name="Height", LengthValue=3.10),
            f.create_entity("IfcQuantityArea", Name="NetFloorArea", AreaValue=10.0),
        ])
    f.create_entity("IfcRelDefinesByProperties", GlobalId=ifc.guid.new(),
                    RelatedObjects=[space], RelatingPropertyDefinition=qto)
    return f, space


def _add_window(ifc, f, space, name, h=None, w=None, n_rels=1, boundary_surface=None):
    """An IfcWindow bound to `space` via `n_rels` IfcRelSpaceBoundary records (duplicates model
    the Revit Duplex double-record shape), optionally carrying a ConnectionGeometry surface."""
    win = f.create_entity("IfcWindow", GlobalId=ifc.guid.new(), Name=name,
                          OverallHeight=h, OverallWidth=w)
    rels = []
    for _ in range(n_rels):
        cg = None
        if boundary_surface is not None:
            cg = f.create_entity("IfcConnectionSurfaceGeometry",
                                 SurfaceOnRelatingElement=boundary_surface)
        rels.append(f.create_entity(
            "IfcRelSpaceBoundary", GlobalId=ifc.guid.new(), RelatingSpace=space,
            RelatedBuildingElement=win, ConnectionGeometry=cg,
            PhysicalOrVirtualBoundary="PHYSICAL", InternalOrExternalBoundary="EXTERNAL"))
    return win, rels


def _rect_curve_bounded_plane(f, width, height):
    """An IfcCurveBoundedPlane whose outer boundary is a width x height rectangle (3D polyline in
    the XZ plane — the shape ArchiCAD emits for window space boundaries, modulo composite)."""
    pts = [(0.0, 0.0, 1.0), (width, 0.0, 1.0), (width, 0.0, 1.0 + height),
           (0.0, 0.0, 1.0 + height), (0.0, 0.0, 1.0)]
    poly = f.create_entity(
        "IfcPolyline", Points=[f.create_entity("IfcCartesianPoint", Coordinates=p) for p in pts])
    plane = f.create_entity("IfcPlane", Position=f.create_entity(
        "IfcAxis2Placement3D",
        Location=f.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0))))
    return f.create_entity("IfcCurveBoundedPlane", BasisSurface=plane, OuterBoundary=poly,
                           InnerBoundaries=[])


def _extrusion_surface(f, length, depth):
    """An IfcSurfaceOfLinearExtrusion boundary surface (the Revit Duplex shape) — the fallback
    must REFUSE it (probed non-lower-bound)."""
    curve = f.create_entity(
        "IfcPolyline", Points=[f.create_entity("IfcCartesianPoint", Coordinates=p)
                               for p in [(0.0, 0.0), (length, 0.0)]])
    prof = f.create_entity("IfcArbitraryOpenProfileDef", ProfileType="CURVE", Curve=curve)
    pos = f.create_entity("IfcAxis2Placement3D", Location=f.create_entity(
        "IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0)))
    direction = f.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0))
    return f.create_entity("IfcSurfaceOfLinearExtrusion", SweptCurve=prof, Position=pos,
                           ExtrudedDirection=direction, Depth=depth)


def _run_tmp(f, salva_casa=False, thr=None, ttl_path=None):
    d = _tmpdir()
    p = os.path.join(d, "adr017.ifc")
    f.write(p)
    return C.run(p, salva_casa, thr, ttl_path=ttl_path), p


def _lombardy_ttl_and_thr():
    """Emit the ADR-016 mock regional pack (bars 3.00/2.55/2.55, aero 1/10) to a temp .ttl and
    build the matching Thresholds. Returns (ttl_path, thr) or (None, reason)."""
    try:
        import gate_spike as GS
    except Exception as exc:  # noqa: BLE001
        return None, f"gate_spike unimportable: {exc}"
    try:
        ttl = GS.emit_shacl(GS._LOMBARDY_MOCK_VERIFIED, None, GS._LOMBARDY_MOCK_CORPUS,
                            spec=GS.LOMBARDY_MOCK_SPEC)
        GS.verify_emitted_shapes(ttl, GS._LOMBARDY_MOCK_VERIFIED, spec=GS.LOMBARDY_MOCK_SPEC)
    except Exception as exc:  # noqa: BLE001
        return None, f"emission failed: {exc}"
    d = _tmpdir()
    p = os.path.join(d, "lombardy_mock.ttl")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(ttl)
    thr = C.Thresholds(requirements=C._dm1975_requirements(3.00, 2.55, 2.55, 0.1))
    return p, thr


# ------------------------------------------------------------------ 1. traversal + dedup
def test_traversal_dedup_kills_double_count() -> None:
    ifc = _ifc()
    if ifc is None:
        _skip("traversal_dedup_kills_double_count", "ifcopenshell absent")
        return
    f, space = _new_model(ifc)
    # ONE window (1.2 m²) recorded through TWO boundary rels — the Duplex duplicate shape.
    _add_window(ifc, f, space, "W-dup", h=1.0, w=1.2, n_rels=2)
    _check("dedup_traversal_one_window", len(C.serving_windows(space)) == 1)
    swb = C.serving_window_boundaries(space)
    _check("dedup_traversal_keeps_both_rels", len(swb) == 1 and len(swb[0][1]) == 2)
    rep, _ = _run_tmp(f)
    tgt = rep["findings"][0]
    # 1.2/10 = 0.12 < 0.125 -> DM-1975 aero VIOLATION. The pre-ADR-017 flat rel list summed the
    # window per rel (2.4/10 = 0.24 >= 0.125) -> a fabricated compliant pass.
    _check("dedup_window_area_counted_once", abs(tgt["window_area_m2"] - 1.2) < 1e-6)
    _check("dedup_aero_ratio_not_doubled", abs(tgt["aero_ratio"] - 0.12) < 1e-9)
    _check("dedup_false_pass_killed", tgt["aero_ok"] is False and tgt["compliant"] is False)


def test_traversal_aggregates_distinct_windows() -> None:
    ifc = _ifc()
    if ifc is None:
        _skip("traversal_aggregates_distinct_windows", "ifcopenshell absent")
        return
    f, space = _new_model(ifc)
    _add_window(ifc, f, space, "W1", h=1.0, w=1.2)   # 1.2 m²
    _add_window(ifc, f, space, "W2", h=1.0, w=0.8)   # 0.8 m²
    _check("aggregate_two_windows_traversed", len(C.serving_windows(space)) == 2)
    rep, _ = _run_tmp(f)
    tgt = rep["findings"][0]
    _check("aggregate_window_area_summed", abs(tgt["window_area_m2"] - 2.0) < 1e-6)
    # 2.0/10 = 0.20 >= 0.125 and height 3.10 >= 2.70 -> compliant under DM-1975.
    _check("aggregate_dm_compliant", tgt["aero_ok"] is True and tgt["compliant"] is True)


# ------------------------------------------------------------------ 2. boundary-geometry area
def test_boundary_geometry_lower_bound() -> None:
    ifc = _ifc()
    if ifc is None:
        _skip("boundary_geometry_lower_bound", "ifcopenshell absent")
        return
    f, space = _new_model(ifc)
    surf = _rect_curve_bounded_plane(f, width=1.2, height=1.0)
    _win, rels = _add_window(ifc, f, space, "W-bnd", boundary_surface=surf)  # NO attr, NO Qto
    _check("bgeo_curveboundedplane_newell_area",
           abs(C.window_boundary_area(rels, 1.0) - 1.2) < 1e-9)
    # attr/Qto present -> the rough source must NOT be consulted (lazy last resort).
    f2, space2 = _new_model(_ifc())
    surf2 = _rect_curve_bounded_plane(f2, width=5.0, height=1.0)   # decoy 5 m² boundary
    _add_window(_ifc(), f2, space2, "W-attr", h=1.0, w=1.2, boundary_surface=surf2)
    wdata2, rough2 = C._serving_window_data(space2, 1.0)
    _check("bgeo_not_consulted_when_attr_present",
           rough2 is False and abs(wdata2[0][0] - 1.2) < 1e-9)


def test_boundary_geometry_refusals() -> None:
    ifc = _ifc()
    if ifc is None:
        _skip("boundary_geometry_refusals", "ifcopenshell absent")
        return
    f, space = _new_model(ifc)
    # Extrusion surface (the Duplex shape, probed NON-lower-bound) -> refused.
    ext = _extrusion_surface(f, length=1.2, depth=1.0)
    _w1, rels_ext = _add_window(ifc, f, space, "W-ext", boundary_surface=ext)
    _check("bgeo_extrusion_refused", C.window_boundary_area(rels_ext, 1.0) is None)
    # Degenerate polygon (2 distinct points) -> refused.
    pts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 0.0)]
    poly = f.create_entity(
        "IfcPolyline", Points=[f.create_entity("IfcCartesianPoint", Coordinates=p) for p in pts])
    plane = f.create_entity("IfcPlane", Position=f.create_entity(
        "IfcAxis2Placement3D",
        Location=f.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0))))
    degen = f.create_entity("IfcCurveBoundedPlane", BasisSurface=plane, OuterBoundary=poly,
                            InnerBoundaries=[])
    _w2, rels_deg = _add_window(ifc, f, space, "W-degen", boundary_surface=degen)
    _check("bgeo_degenerate_polygon_refused", C.window_boundary_area(rels_deg, 1.0) is None)
    # Inner boundaries (holes) -> refused (subtracting unvalidated holes could overstate).
    holed = _rect_curve_bounded_plane(f, width=1.2, height=1.0)
    inner = f.create_entity(
        "IfcPolyline", Points=[f.create_entity("IfcCartesianPoint", Coordinates=p)
                               for p in [(0.2, 0.0, 1.2), (0.4, 0.0, 1.2), (0.4, 0.0, 1.4),
                                         (0.2, 0.0, 1.2)]])
    holed.InnerBoundaries = [inner]
    _w3, rels_hole = _add_window(ifc, f, space, "W-holed", boundary_surface=holed)
    _check("bgeo_inner_boundaries_refused", C.window_boundary_area(rels_hole, 1.0) is None)
    # No ConnectionGeometry at all -> refused.
    _w4, rels_none = _add_window(ifc, f, space, "W-nocg")
    _check("bgeo_missing_geometry_refused", C.window_boundary_area(rels_none, 1.0) is None)


def test_boundary_geometry_verdict_semantics() -> None:
    """The L-2 remap on a rough source: >= bar proves a pass; < bar is UNDETERMINED, never a
    fabricated violation — the same synthetic model flips undetermined(DM 1/8) / pass(mock 1/10)."""
    ifc = _ifc()
    if ifc is None:
        _skip("boundary_geometry_verdict_semantics", "ifcopenshell absent")
        return
    f, space = _new_model(ifc)
    surf = _rect_curve_bounded_plane(f, width=1.2, height=1.0)   # 1.2 m² lower bound
    _add_window(ifc, f, space, "W-rough", boundary_surface=surf)  # NO attr, NO Qto
    rep, ifc_path = _run_tmp(f)
    tgt = rep["findings"][0]
    # DM-1975: 0.12 < 0.125 on a LOWER BOUND -> undetermined (the real area may be larger).
    _check("bgeo_dm_below_bar_undetermined",
           tgt["aero_ok"] is None and tgt["compliant"] is None)
    _check("bgeo_dm_note_says_rough",
           any("ADR-017" in n and "lower bound" in n for n in tgt["notes"]))
    ttl, thr = _lombardy_ttl_and_thr()
    if ttl is None:
        _skip("bgeo_lombardy_lower_bound_pass", str(thr))
        return
    rep2 = O.ComplianceOrchestrator(ifc_path, ttl_path=ttl, thr=thr).run()
    tgt2 = rep2["findings"][0]
    # Mock regional 1/10: 0.12 >= 0.10 on a lower bound PROVES the pass; height 3.10 >= 3.00.
    _check("bgeo_lombardy_lower_bound_pass",
           tgt2["aero_ok"] is True and tgt2["compliant"] is True and rep2["violations"] == 0)
    _check("bgeo_lombardy_pass_note_present",
           any("boundary-geometry lower bound" in n for n in tgt2["notes"]))


# ------------------------------------------------------------------ 3. measurement registry
def test_measurement_registry() -> None:
    ifc = _ifc()
    if ifc is None:
        _skip("measurement_registry", "ifcopenshell absent")
        return
    _check("registry_sides_pinned_equal",
           set(C.MEASUREMENT_EXTRACTORS) == set(O.SUPPORTED_MEASUREMENT_PATHS))
    _check("registry_carries_canonical_paths",
           set(C.MEASUREMENT_EXTRACTORS) == {G.ACC.heightM, G.ACC.aeroRatio})
    # The default pack requires exactly the two registered measurements.
    req = O.required_measurement_paths(C.Thresholds())
    _check("registry_default_pack_requirements",
           req == frozenset({G.ACC.heightM, G.ACC.aeroRatio}))
    # The registry extractors produce the canonical values on a synthetic space.
    f, space = _new_model(ifc)
    _add_window(ifc, f, space, "W1", h=1.0, w=1.2)
    _check("registry_height_extractor",
           abs(C.MEASUREMENT_EXTRACTORS[G.ACC.heightM](space, 1.0) - 3.10) < 1e-9)
    _check("registry_aero_extractor",
           abs(C.MEASUREMENT_EXTRACTORS[G.ACC.aeroRatio](space, 1.0) - 0.12) < 1e-9)
    # A pack binding an UNREGISTERED measurement path is refused at load (fail-closed).
    with open(O.DEFAULT_SHACL_PATH, encoding="utf-8") as fh:
        ttl = fh.read()
    ttl += ("\nlegal:FireRating_PS a sh:PropertyShape ;\n"
            "    sh:path acc:fireRating ;\n"
            "    sh:minCount 1 ;\n"
            "    sh:maxCount 1 ;\n"
            "    sh:minInclusive 1 ;\n"
            '    sh:message "fire rating below 1" .\n\n'
            "legal:HabitableBaselineShape sh:property legal:FireRating_PS .\n")
    d = _tmpdir()
    p = os.path.join(d, "rogue_path.ttl")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(ttl)
    refused = False
    try:
        O.load_shacl_shapes(C.Thresholds(), path=p)
    except ValueError as exc:
        refused = "fireRating" in str(exc)
    _check("registry_unregistered_path_refused", refused)


# ------------------------------------------------------------------ 4. Lombardy E2E flip
def test_lombardy_full_pipeline_flip() -> None:
    """LOMBARDY_MOCK_SPEC (1/10 aero) through the FULL pipeline: the same synthetic IFC — a
    habitable space whose window ratio (0.12) sits BETWEEN 1/10 and 1/8 — flips verdict purely
    through the rule pack. acc:aeroRatio is evaluated and the SHACL verdict routed both times."""
    ifc = _ifc()
    if ifc is None:
        _skip("lombardy_full_pipeline_flip", "ifcopenshell absent")
        return
    ttl, thr = _lombardy_ttl_and_thr()
    if ttl is None:
        _skip("lombardy_full_pipeline_flip", str(thr))
        return
    f, space = _new_model(ifc)
    _add_window(ifc, f, space, "W1", h=1.0, w=1.2)   # exact attr area: 1.2 m² -> ratio 0.12
    d = _tmpdir()
    ifc_path = os.path.join(d, "flip.ifc")
    f.write(ifc_path)
    dm = O.ComplianceOrchestrator(ifc_path).run()                        # DM-1975 defaults, 1/8
    lom = O.ComplianceOrchestrator(ifc_path, ttl_path=ttl, thr=thr).run()  # mock regional, 1/10
    t_dm, t_lom = dm["findings"][0], lom["findings"][0]
    _check("flip_dm_aero_violation",
           t_dm["aero_ok"] is False and t_dm["compliant"] is False and dm["violations"] == 1)
    _check("flip_lombardy_aero_pass",
           t_lom["aero_ok"] is True and t_lom["compliant"] is True and lom["violations"] == 0)
    _check("flip_same_extraction_both_packs",
           abs(t_dm["aero_ratio"] - 0.12) < 1e-9 and abs(t_lom["aero_ratio"] - 0.12) < 1e-9)
    # A below-bar regional run must report the REGIONAL pack's own message provenance, not the
    # DM-1975 template text (ADR-008 wrong-message class; ADR-017 loader fix).
    f2, space2 = _new_model(ifc)
    _add_window(ifc, f2, space2, "W-small", h=1.0, w=0.9)   # 0.09 < 1/10
    ifc2 = os.path.join(d, "below.ifc")
    f2.write(ifc2)
    low = O.ComplianceOrchestrator(ifc2, ttl_path=ttl, thr=thr).run()
    t_low = low["findings"][0]
    aero_notes = [n for n in t_low["notes"] if n.startswith("SHACL: aero")]
    _check("flip_lombardy_below_bar_violation", t_low["aero_ok"] is False)
    _check("flip_lombardy_message_provenance",
           len(aero_notes) == 1 and "mock" in aero_notes[0] and "DM 1975" not in aero_notes[0])


# ------------------------------------------------------------------ 5. round-6 red-team pins
def test_redteam_round6_dedup_and_geometry() -> None:
    """Adversarial round 6 (ADR-017): every confirmed extractor attack, pinned as a regression."""
    ifc = _ifc()
    if ifc is None:
        _skip("redteam_round6_dedup_and_geometry", "ifcopenshell absent")
        return
    # F1 — a window whose GlobalId resolves to None must still dedup: ifcopenshell returns a
    # FRESH wrapper per attribute access, so a Python-id fallback resurrects the double count.
    f, space = _new_model(ifc)
    win = f.create_entity("IfcWindow", Name="W-nogid", OverallHeight=1.0, OverallWidth=1.4)
    for _ in range(2):
        f.create_entity("IfcRelSpaceBoundary", GlobalId=ifc.guid.new(), RelatingSpace=space,
                        RelatedBuildingElement=win, PhysicalOrVirtualBoundary="PHYSICAL",
                        InternalOrExternalBoundary="EXTERNAL")
    _check("r6_f1_none_globalid_still_dedups", len(C.serving_windows(space)) == 1)
    rep, _ = _run_tmp(f)
    tgt = rep["findings"][0]
    # honest single count: 1.4/10 = 0.14 >= 0.125 -> pass is legitimate; the DEFECT was the
    # doubled 2.8/10; pin the ratio itself so any double count is visible.
    _check("r6_f1_ratio_counted_once", abs(tgt["aero_ratio"] - 0.14) < 1e-9)
    # F2 — a boundary loop traversing the same rectangle TWICE reads 2x under raw Newell
    # (winding multiplicity): must be REFUSED, never consumed as a doubled 'lower bound'.
    f2, space2 = _new_model(ifc)
    loop = [(0.0, 0.0, 1.0), (0.8, 0.0, 1.0), (0.8, 0.0, 1.8), (0.0, 0.0, 1.8)]
    pts = loop + loop + [loop[0]]
    poly = f2.create_entity(
        "IfcPolyline", Points=[f2.create_entity("IfcCartesianPoint", Coordinates=p) for p in pts])
    plane = f2.create_entity("IfcPlane", Position=f2.create_entity(
        "IfcAxis2Placement3D",
        Location=f2.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0))))
    wound = f2.create_entity("IfcCurveBoundedPlane", BasisSurface=plane, OuterBoundary=poly,
                             InnerBoundaries=[])
    _w2, rels_wound = _add_window(ifc, f2, space2, "W-wound", boundary_surface=wound)
    _check("r6_f2_double_wound_loop_refused", C.window_boundary_area(rels_wound, 1.0) is None)
    # F3 — IfcIndexedPolyCurve: the Segments attribute defines the curve; a curve selecting one
    # edge of a 2x2 CoordList rectangle encloses NOTHING and must refuse, not read 4 m².
    f3, space3 = _new_model(ifc)
    plist = f3.create_entity("IfcCartesianPointList3D", CoordList=[
        (0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 0.0, 2.0), (0.0, 0.0, 2.0)])
    one_edge = f3.create_entity("IfcIndexedPolyCurve", Points=plist,
                                Segments=[f3.create_entity("IfcLineIndex", (1, 2))])
    plane3 = f3.create_entity("IfcPlane", Position=f3.create_entity(
        "IfcAxis2Placement3D",
        Location=f3.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0))))
    cbp3 = f3.create_entity("IfcCurveBoundedPlane", BasisSurface=plane3, OuterBoundary=one_edge,
                            InnerBoundaries=[])
    _w3, rels_edge = _add_window(ifc, f3, space3, "W-edge", boundary_surface=cbp3)
    _check("r6_f3_segments_honored_one_edge_refused",
           C.window_boundary_area(rels_edge, 1.0) is None)
    # ...while a genuinely closed indexed rectangle still measures (positive control).
    plist_ok = f3.create_entity("IfcCartesianPointList3D", CoordList=[
        (0.0, 0.0, 1.0), (1.2, 0.0, 1.0), (1.2, 0.0, 2.0), (0.0, 0.0, 2.0)])
    closed = f3.create_entity("IfcIndexedPolyCurve", Points=plist_ok,
                              Segments=[f3.create_entity("IfcLineIndex", (1, 2, 3, 4, 1))])
    cbp_ok = f3.create_entity("IfcCurveBoundedPlane", BasisSurface=plane3, OuterBoundary=closed,
                              InnerBoundaries=[])
    _w3b, rels_ok = _add_window(ifc, f3, space3, "W-idx-ok", boundary_surface=cbp_ok)
    _check("r6_f3_closed_indexed_rectangle_measures",
           abs(C.window_boundary_area(rels_ok, 1.0) - 1.2) < 1e-9)
    # F4 — two patches for the SAME window that materially disagree: the CONSERVATIVE one wins
    # (min, mirroring ADR-007c's min(attr, Qto)); a single inflated <=floor patch must not
    # become the 'proven' lower bound.
    f4, space4 = _new_model(ifc)
    win4 = f4.create_entity("IfcWindow", GlobalId=ifc.guid.new(), Name="W-2patch")
    rels4 = []
    for wdt in (0.2, 1.3):
        surf = _rect_curve_bounded_plane(f4, width=wdt, height=1.0)
        cg = f4.create_entity("IfcConnectionSurfaceGeometry", SurfaceOnRelatingElement=surf)
        rels4.append(f4.create_entity(
            "IfcRelSpaceBoundary", GlobalId=ifc.guid.new(), RelatingSpace=space4,
            RelatedBuildingElement=win4, ConnectionGeometry=cg,
            PhysicalOrVirtualBoundary="PHYSICAL", InternalOrExternalBoundary="EXTERNAL"))
    _check("r6_f4_disagreeing_patches_conservative",
           abs(C.window_boundary_area(tuple(rels4), 1.0) - 0.2) < 1e-9)
    rep4, _ = _run_tmp(f4)
    tgt4 = rep4["findings"][0]
    _check("r6_f4_inflated_patch_cannot_prove_pass",
           tgt4["aero_ok"] is None and tgt4["compliant"] is None)


def test_redteam_round6_loader_guards() -> None:
    ifc = _ifc()
    if ifc is None:
        _skip("redteam_round6_loader_guards", "ifcopenshell absent")
        return
    with open(O.DEFAULT_SHACL_PATH, encoding="utf-8") as fh:
        base_ttl = fh.read()
    d = _tmpdir()
    # Multi-message survival: a second sh:message on a PS must NOT ride through message
    # preservation into the report — the loader regenerates to exactly one message.
    p1 = os.path.join(d, "multi_msg.ttl")
    with open(p1, "w", encoding="utf-8") as fh:
        fh.write(base_ttl + '\nlegal:MinAeroRatio_PS sh:message "SECOND hidden message" .\n')
    g = O.load_shacl_shapes(C.Thresholds(), path=p1)
    msgs = list(g.objects(O.LEGAL["MinAeroRatio_PS"], O.SH.message))
    _check("r6_loader_multi_message_collapsed",
           len(msgs) == 1 and "SECOND" not in str(msgs[0]))
    # sh:sparql constraints carry no sh:path and cannot be routed to a verdict slot: the load
    # guard must refuse them classified, not let the runtime crash unrouted.
    p2 = os.path.join(d, "sparql.ttl")
    with open(p2, "w", encoding="utf-8") as fh:
        fh.write(base_ttl + '\nlegal:HabitableBaselineShape sh:sparql [ a sh:SPARQLConstraint ;'
                            ' sh:message "x" ; sh:select "SELECT ?this WHERE { }" ] .\n')
    refused = False
    try:
        O.load_shacl_shapes(C.Thresholds(), path=p2)
    except ValueError as exc:
        refused = "sparql" in str(exc).lower()
    _check("r6_loader_sparql_constraint_refused", refused)
    # run()'s own registry cross-check (mutation TQ-2): with an extractor missing, run() must
    # refuse NotCertifiable, never return a normal report.
    f, _space = _new_model(ifc)
    ifc_path = os.path.join(d, "regcheck.ifc")
    f.write(ifc_path)
    removed = C.MEASUREMENT_EXTRACTORS.pop(G.ACC.aeroRatio)
    try:
        raised = False
        try:
            C.run(ifc_path)
        except C.NotCertifiableError:
            raised = True
    finally:
        C.MEASUREMENT_EXTRACTORS[G.ACC.aeroRatio] = removed
    _check("r6_run_registry_cross_check_raises", raised)


# ------------------------------------------------------------------ 6. fixture ground-truth pins
def _boundary_ground_truth(ifc, path):
    """(windows, rels, measured, exact, lower_bound_ok) over every serving window of a fixture."""
    m = ifc.open(str(path))
    scale = C.length_scale_to_m(m)
    windows = rels_n = exact = measured = 0
    lower_bound_ok = True
    for sp in m.by_type("IfcSpace"):
        for w, rels in C.serving_window_boundaries(sp):
            windows += 1
            rels_n += len(rels)
            attr, _qto = C._window_area_bounds(w, scale)
            for rel in rels:
                bnd = C._boundary_patch_area(rel, scale)
                if bnd is None or attr is None:
                    continue
                measured += 1
                if bnd > attr + 1e-6:
                    lower_bound_ok = False
                if abs(bnd - attr) < 1e-6:
                    exact += 1
    return windows, rels_n, measured, exact, lower_bound_ok


def test_fixture_ground_truth() -> None:
    """Live-fixture regression: (a) dedup is a NO-OP on FZK/Institute (no duplicate pairs — the
    frozen controls cannot move); (b) the boundary-geometry patch area is a true LOWER BOUND of
    the attr area on every measured ArchiCAD window boundary (217 total: exact ratio 1.000 on
    215, understated on the 2 sloped FZK roof windows, overstated on none)."""
    ifc = _ifc()
    if ifc is None or not _FZK.exists():
        _skip("fzk_ground_truth", "ifcopenshell/fixture absent")
    else:
        windows, rels_n, measured, exact, lb_ok = _boundary_ground_truth(ifc, _FZK)
        _check("fzk_dedup_noop", windows == rels_n == 11)
        _check("fzk_boundary_area_is_lower_bound", measured == 11 and lb_ok)
        _check("fzk_boundary_area_exact_on_facade_windows", exact == 9)
    if ifc is None or not _INSTITUTE.exists():
        _skip("institute_ground_truth", "ifcopenshell/fixture absent")
    else:
        windows, rels_n, measured, exact, lb_ok = _boundary_ground_truth(ifc, _INSTITUTE)
        _check("institute_dedup_noop", windows == rels_n == 206)
        _check("institute_boundary_area_lower_bound_and_exact",
               measured == 206 and exact == 206 and lb_ok)


def main() -> int:
    test_traversal_dedup_kills_double_count()
    test_traversal_aggregates_distinct_windows()
    test_boundary_geometry_lower_bound()
    test_boundary_geometry_refusals()
    test_boundary_geometry_verdict_semantics()
    test_measurement_registry()
    test_lombardy_full_pipeline_flip()
    test_redteam_round6_dedup_and_geometry()
    test_redteam_round6_loader_guards()
    test_fixture_ground_truth()
    print(f"\n{_PASS}/{_PASS + _FAIL} passed, {_SKIP} skipped")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
