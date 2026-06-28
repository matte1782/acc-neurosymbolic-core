#!/usr/bin/env python3
"""Stage 4 Part 2, Task 1 — record-backed requirement model + backward-compatible accessor.

Verdict-neutral structural refactor: the rigid 4-float `Thresholds` dataclass is now an accessor
*view* over a small list of `Requirement` records. These tests pin the contract the refactor must
not move:
  - the 4 frozen numbers resolve BYTE-IDENTICALLY through the legacy accessors (2.70/2.40/2.40/0.125);
  - `from_rules_json` reads today's compiled JSON to the same 4 floats, and round-trips via
    `to_legacy_dict()` to the exact thresholds block (same keys/order/values);
  - FAIL-CLOSED: resolving an absent metric (the 5th-metric / monostanza case) RAISES — it never
    silently returns a default;
  - extra thresholds-block keys are PRESERVED (not dropped, not defaulted) for a future rule.
  - Stage 4 Part 4: the monostanza metric resolves per person count (28/38, Salva-Casa 20/28)
    WITHOUT perturbing the legacy block; a still-absent metric still RAISES.

Offline for the model contract; one OPTIONAL checker-level check runs C.run on the Duplex fixture
only if present (skipped otherwise — checker already requires ifcopenshell to import).

Run either way:
    python test_requirement_model.py     # plain asserts, prints PASS/FAIL, exit 1 on any failure
    pytest test_requirement_model.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SANDBOX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SANDBOX))  # import sandbox/checker.py

import checker as C  # noqa: E402

_PASS = 0
_FAIL = 0

_COMPILED = _SANDBOX / "rules" / "compiled" / "dm_1975_salva_casa.json"


def _check(name: str, cond: bool) -> None:
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"PASS {name}")
    else:
        _FAIL += 1
        print(f"FAIL {name}")


def _raises(fn) -> bool:
    try:
        fn()
    except C.RequirementLookupError:
        return True
    except Exception:  # noqa: BLE001 — any other exception is the wrong failure mode
        return False
    return False


def main() -> int:
    # 1. The four frozen numbers resolve byte-identically through the legacy accessors.
    thr = C.Thresholds()
    _check("default_habitable_2.70", thr.min_height_habitable_m == 2.70)
    _check("default_accessory_2.40", thr.min_height_accessory_m == 2.40)
    _check("default_salva_casa_2.40", thr.min_height_salva_casa_m == 2.40)
    _check("default_aero_0.125", thr.aero_illuminating_ratio == 0.125)

    # 2. The legacy thresholds block is byte-identical to the pre-refactor asdict(Thresholds()):
    #    exact keys, order and float values (this is what the report `thresholds` block emits).
    _check("to_legacy_dict_exact",
           list(thr.to_legacy_dict().items()) == [
               ("min_height_habitable_m", 2.7), ("min_height_accessory_m", 2.4),
               ("min_height_salva_casa_m", 2.4), ("aero_illuminating_ratio", 0.125)])

    # 3. from_rules_json reads today's compiled JSON to the SAME 4 floats (no drift, no default).
    if _COMPILED.exists():
        loaded = C.Thresholds.from_rules_json(str(_COMPILED))
        _check("from_json_habitable", loaded.min_height_habitable_m == 2.70)
        _check("from_json_accessory", loaded.min_height_accessory_m == 2.40)
        _check("from_json_salva_casa", loaded.min_height_salva_casa_m == 2.40)
        _check("from_json_aero", loaded.aero_illuminating_ratio == 0.125)
        # And it round-trips byte-identically to the JSON's own thresholds block.
        block = json.loads(_COMPILED.read_text(encoding="utf-8")).get("thresholds")
        _check("from_json_roundtrip_block", loaded.to_legacy_dict() == block)
    else:
        _check("compiled_json_present", False)  # the compiled rule must exist for the pipeline

    # 4. FAIL-CLOSED — resolving an absent metric/applicability RAISES (the 5th-metric case that
    #    used to AttributeError); it must never silently default to a value that could pass.
    _check("unknown_metric_raises",
           _raises(lambda: thr.resolve("min_surface_monostanza_3p", "monolocale")))
    _check("unknown_applicability_raises",
           _raises(lambda: thr.resolve("min_height", "garden")))
    # accessory has no Salva-Casa derogation (the swap is non-accessory only) -> raises, not default.
    _check("accessory_salva_casa_raises",
           _raises(lambda: thr.resolve("min_height", "accessory", salva_casa=True)))

    # 5. Extra thresholds-block keys are PRESERVED (not dropped) and do NOT perturb the 4 legacy
    #    values; and an extra key is NOT resolvable as a default (still fail-closed).
    extra = C.Thresholds(extras={"min_surface_monostanza_1p": 28.0})
    _check("extras_preserved", extra.extras.get("min_surface_monostanza_1p") == 28.0)
    _check("extras_do_not_shift_legacy", extra.to_legacy_dict() == thr.to_legacy_dict())
    _check("extras_not_resolvable_as_default",
           _raises(lambda: extra.resolve("min_surface_monostanza_3p", "monolocale")))

    # 6. Stage 4 Part 4 — the monostanza metric is now IN the requirement model (2 records, each
    #    carrying its Salva-Casa derogation as salva_casa_value), resolvable per person count; the
    #    legacy block stays byte-identical (monolocale is a disjoint metric/applicability, so the
    #    existing min_surface_monostanza_1p absent-metric exemplars above were re-pointed to _3p).
    _check("monostanza_1p_baseline_28",
           thr.resolve("min_surface_monostanza_1p", "monolocale") == 28.0)
    _check("monostanza_1p_salva_casa_20",
           thr.resolve("min_surface_monostanza_1p", "monolocale", salva_casa=True) == 20.0)
    _check("monostanza_2p_baseline_38",
           thr.resolve("min_surface_monostanza_2p", "monolocale") == 38.0)
    _check("monostanza_2p_salva_casa_28",
           thr.resolve("min_surface_monostanza_2p", "monolocale", salva_casa=True) == 28.0)
    _check("monostanza_did_not_perturb_legacy",
           list(thr.to_legacy_dict().items()) == [
               ("min_height_habitable_m", 2.7), ("min_height_accessory_m", 2.4),
               ("min_height_salva_casa_m", 2.4), ("aero_illuminating_ratio", 0.125)])
    _check("still_absent_monostanza_metric_raises",
           _raises(lambda: thr.resolve("min_surface_monostanza_3p", "monolocale")))

    # 7. OPTIONAL checker-level channel check (mirrors test_applicability_table's skip pattern):
    #    report['monostanza'] is 'undetermined'/applicable:null on a real fixture — proving the
    #    unit-level channel is wired AND verdict-neutral (per-space violations/undetermined frozen).
    #    Skipped if the Duplex IFC is absent (checker already requires ifcopenshell to import).
    duplex = _SANDBOX / "data" / "Duplex_A_20110907.ifc"
    if duplex.exists():
        report = C.run(str(duplex))
        _check("monostanza_channel_undetermined", report["monostanza"]["status"] == "undetermined")
        _check("monostanza_channel_applicable_null", report["monostanza"]["applicable"] is None)
        _check("monostanza_channel_not_in_counts",
               report["violations"] == 0 and report["spaces_undetermined"] == 21)
    else:
        print("SKIP monostanza_channel (Duplex IFC absent)")

    print(f"\n{_PASS}/{_PASS + _FAIL} passed")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
