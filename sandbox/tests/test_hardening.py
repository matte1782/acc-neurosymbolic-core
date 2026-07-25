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

import inspect
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


# ----------------------------------- C-2: length unit RESOLVABILITY fail-closed (C2-F, hardened)
# Presence is NOT enough (the C2-B defect the bias-resistant pilot disqualified): a present-but-
# unresolvable unit (IfcContextDependentUnit) still let calculate_unit_scale fall back to 1.0.
class _FakeUnit:
    def __init__(self, klass, unit_type="LENGTHUNIT", name=None, conv=None):
        self._klass, self.UnitType, self.Name, self.ConversionFactor = klass, unit_type, name, conv

    def is_a(self, k=None):
        return self._klass if k is None else (k == self._klass)


class _MWU:
    def __init__(self, comp):
        self.UnitComponent = comp


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
    si_m = _FakeUnit("IfcSIUnit", name="METRE")
    ctx = _FakeUnit("IfcContextDependentUnit", name="SMOOT")          # present but UNRESOLVABLE
    foot = _FakeUnit("IfcConversionBasedUnit", name="foot",
                     conv=_MWU(_FakeUnit("IfcSIUnit", name="METRE")))
    area = _FakeUnit("IfcSIUnit", unit_type="AREAUNIT", name="SQUARE_METRE")
    # resolvability predicate (the C2-F contract): presence is NOT enough.
    _check("resolvable_si_metre", C._length_unit_resolvable(si_m) is True)
    _check("resolvable_conversion_foot", C._length_unit_resolvable(foot) is True)
    _check("unresolvable_contextdependent", C._length_unit_resolvable(ctx) is False)
    _check("unresolvable_none", C._length_unit_resolvable(None) is False)
    # entity lookup uses projects[0] (matches calculate_unit_scale -> closes multi-project divergence).
    _check("entity_found", C._length_unit_entity(_Model([_Proj(_UIC([area, si_m]))])) is si_m)
    _check("entity_absent_none", C._length_unit_entity(_Model([_Proj(_UIC([area]))])) is None)
    # the C2-F fix: a present-but-UNRESOLVABLE unit RAISES NotCertifiableError (the C2-B hole),
    # as does an absent unit / no project.
    _check("contextdependent_raises", _raises(
        lambda: C.length_scale_to_m(_Model([_Proj(_UIC([area, ctx]))])), C.NotCertifiableError))
    _check("absent_unit_raises", _raises(
        lambda: C.length_scale_to_m(_Model([_Proj(_UIC([area]))])), C.NotCertifiableError))
    _check("no_project_raises", _raises(lambda: C.length_scale_to_m(_Model([])), C.NotCertifiableError))
    _check("not_certifiable_is_valueerror", issubclass(C.NotCertifiableError, ValueError))
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


def test_c2_classified_exit() -> None:
    # C2-C: a not-certifiable model exits with the DISTINCT code 2 + a message, not a raw traceback
    # exiting 1 (indistinguishable from a violations run).
    import os
    import tempfile
    try:
        import ifcopenshell
    except Exception:  # noqa: BLE001
        _skip("c2_classified_exit_code_2", "ifcopenshell absent")
        return
    fx = _SANDBOX / "data" / "AC20-FZK-Haus.ifc"
    if not fx.exists():
        _skip("c2_classified_exit_code_2", "fixture absent")
        return
    m = ifcopenshell.open(str(fx))
    for proj in m.by_type("IfcProject"):
        uic = getattr(proj, "UnitsInContext", None)
        if uic is not None:
            uic.Units = [u for u in uic.Units if getattr(u, "UnitType", None) != "LENGTHUNIT"]
    p = os.path.join(tempfile.mkdtemp(), "nounit.ifc")
    m.write(p)
    rc = C.main([p])
    _check("c2_classified_exit_code_2", rc == 2)


# ----------------------------------- Stage 5 (ADR-008/008a): SHACL verdict-path fail-closed
def test_shacl_fail_closed() -> None:
    import re
    import tempfile
    thr = C.Thresholds()
    # (1) exact-at-bar datatype parity (ADR-008a): a room at EXACTLY the bar passes — float(2.4)
    # materialized as xsd:double compared below Decimal('2.4') and flipped PASS->VIOLATION; the
    # Decimal(str(v)) materialization restores the old at-the-bar semantics.
    _check("shacl_exact_240_accessory_passes",
           C._shacl_verdict("accessory", False, 2.40, None, False, thr)[0] is True)
    _check("shacl_exact_270_habitable_passes",
           C._shacl_verdict("habitable", False, 2.70, 0.140, False, thr)[0] is True)
    _check("shacl_exact_0125_aero_passes",
           C._shacl_verdict("habitable", False, 2.80, 0.125, False, thr)[1] is True)
    _check("shacl_below_bar_still_violates",
           C._shacl_verdict("habitable", False, 2.69, 0.140, False, thr)[0] is False)
    # (2) minCount loader guard (ADR-008a): a shapes file stripped of sh:minCount would demote an
    # ABSENT measurement from UNDETERMINED to a vacuous PASS — the loader must REFUSE it.
    ttl = Path(C._SHACL_PATH).read_text(encoding="utf-8")
    mutated = re.sub(r"\s*sh:minCount 1 ;.*\n", "\n", ttl)
    p = Path(tempfile.mkdtemp()) / "no_mincount.ttl"
    p.write_text(mutated, encoding="utf-8")
    _check("shacl_mincount_stripped_ttl_refused",
           _raises(lambda: C.load_shacl_shapes(thr, path=str(p)), ValueError))
    # also: a shapes file missing a targeted class must refuse (anti-vacuous-conformance).
    mutated2 = ttl.replace("sh:targetClass acc:AccessorySpace", "sh:targetClass acc:SomethingElse")
    p2 = Path(tempfile.mkdtemp()) / "untargeted.ttl"
    p2.write_text(mutated2, encoding="utf-8")
    _check("shacl_untargeted_class_refused",
           _raises(lambda: C.load_shacl_shapes(thr, path=str(p2)), ValueError))
    # (3) defense-in-depth: a non-finite measurement reaching materialization RAISES (the post-pass
    # maps no-result -> True, so an uncomparable literal would otherwise fail OPEN).
    _check("shacl_nonfinite_height_raises",
           _raises(lambda: C._shacl_verdict("habitable", False, float("inf"), 0.140, False, thr),
                   ValueError))
    _check("shacl_nonfinite_ratio_raises",
           _raises(lambda: C._shacl_verdict("habitable", False, 2.8, float("nan"), False, thr),
                   ValueError))
    # ternary keystone through SHACL: absent measurements stay UNDETERMINED, never a pass.
    _check("shacl_missing_height_undetermined",
           C._shacl_verdict("habitable", False, None, 0.140, False, thr)[0] is None)
    _check("shacl_missing_ratio_undetermined",
           C._shacl_verdict("habitable", False, 2.8, None, False, thr)[1] is None)


# ------------------------------------------- truth-in-labelling: the declared conventions
def test_measurement_conventions_declared() -> None:
    """The engine must SAY which measurement convention it chose (ADR-021 proposal §2).

    DM 1975 art. 5 defines no convention, so the gross reading is an engine decision. These checks
    pin (a) the block's presence and shape, (b) that it names the functions that actually implement
    it — so moving the convention without moving the text fails here rather than misleading a
    practitioner, and (c) that it is inert: declarative prose, never read back by a verdict."""
    conv = C.MEASUREMENT_CONVENTIONS
    _check("conv_keys_pinned",
           set(conv) == {"aero_numeratore", "aero_denominatore", "altezza", "ambito"})
    _check("conv_values_are_prose", all(isinstance(v, str) and len(v) > 40 for v in conv.values()))
    # (b) the citations must name real callables, so the text cannot silently outlive the code.
    for fn in ("_window_area_bounds", "_serving_window_data", "_aero_trust", "space_floor_area",
               "space_height"):
        _check(f"conv_cites_real_symbol_{fn}", callable(getattr(C, fn, None)))
    _check("conv_cites_numerator_impl", "_window_area_bounds" in conv["aero_numeratore"])
    _check("conv_cites_denominator_impl", "space_floor_area" in conv["aero_denominatore"])
    _check("conv_cites_height_impl", "space_height" in conv["altezza"])
    # (c) the two facts a reader most needs, stated in the engine's own words.
    _check("conv_says_gross", "LORDO" in conv["aero_numeratore"])
    _check("conv_says_no_national_source", "non ha una fonte nazionale" in conv["aero_numeratore"])
    _check("conv_says_height_not_a_mean", "NON e' " in conv["altezza"]
           and "media ponderata" in conv["altezza"])
    _check("conv_says_scope_is_national", "non lo deduce dal modello" in conv["ambito"])
    # INERTNESS: no verdict path may consume this block. If a future edit routes a decision through
    # it, the frozen controls could move behind a 'documentation' change — forbid it here.
    src = inspect.getsource(C)
    reads = [ln for ln in src.splitlines() if "MEASUREMENT_CONVENTIONS" in ln]
    _check("conv_is_inert",
           len(reads) == 2 and any("MEASUREMENT_CONVENTIONS = {" in ln for ln in reads))


def main() -> int:
    test_window_area_positivity()
    test_quantity_positivity()
    test_length_unit_fail_closed()
    test_zero_space_not_certifiable()
    test_c2_classified_exit()
    test_shacl_fail_closed()
    test_measurement_conventions_declared()
    print(f"\n{_PASS}/{_PASS + _FAIL} passed, {_SKIP} skipped")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
