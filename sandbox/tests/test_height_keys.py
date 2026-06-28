#!/usr/bin/env python3
"""Focused unit test for checker.space_height multi-key Qto lookup (Stage 3 Part 2, Task 2).

100% offline, no IFC file: we mock ifcopenshell's get_psets so space_height sees a synthetic
quantity set, and assert (a) "Height" wins when present and (b) ClearHeight / the other
net-height variants resolve when "Height" is absent — i.e. "Height"-first precedence is
preserved (so the FZK / Institute fixtures, which carry "Height", are untouched) while a
vendor file that names the quantity differently still resolves a height.

Run either way:
    python test_height_keys.py     # plain asserts, prints PASS/FAIL, exit 1 on any failure
    pytest test_height_keys.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # import sandbox/checker.py

import checker as C  # noqa: E402

_PASS = 0
_FAIL = 0


def _check(name: str, cond: bool) -> None:
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"PASS {name}")
    else:
        _FAIL += 1
        print(f"FAIL {name}")


def _height(qtos: dict, scale: float = 1.0):
    """space_height() with get_psets mocked to return `qtos` ({qset_name: {key: value}})."""
    with patch.object(C.ue, "get_psets", return_value=qtos):
        return C.space_height(object(), scale)


def main() -> int:
    # 1. ClearHeight resolves when "Height" is absent (the future-vendor case Task 2 targets).
    _check("clearheight_resolves_when_no_height",
           _height({"BaseQuantities": {"ClearHeight": 2.55}}) == 2.55)

    # 2. "Height" still wins when both are present — precedence preserved, so FZK/Institute
    #    (which carry "Height") keep their exact prior result. This is the control-safety guard.
    _check("height_wins_when_both_present",
           _height({"BaseQuantities": {"Height": 2.70, "ClearHeight": 2.55}}) == 2.70)

    # 3. The remaining net-height variants resolve as fallbacks (both qset names accepted).
    _check("finishceilingheight_fallback",
           _height({"BaseQuantities": {"FinishCeilingHeight": 2.48}}) == 2.48)
    _check("netheight_fallback",
           _height({"Qto_SpaceBaseQuantities": {"NetHeight": 2.61}}) == 2.61)
    _check("altezzanetta_fallback",
           _height({"BaseQuantities": {"AltezzaNetta": 2.39}}) == 2.39)

    # 4. Tuple order decides among fallbacks: ClearHeight (earlier) beats FinishCeilingHeight.
    _check("clearheight_beats_finishceiling",
           _height({"BaseQuantities": {"ClearHeight": 2.55, "FinishCeilingHeight": 2.48}}) == 2.55)

    # 5. No height-like key at all -> None (space stays undetermined; never a silent pass).
    _check("none_when_only_unrelated_keys",
           _height({"BaseQuantities": {"NetFloorArea": 18.0}}) is None)
    _check("none_when_empty",
           _height({}) is None)

    # 6. The project unit scale is applied (raw * scale**1) regardless of which key matched.
    _check("scale_applied_to_fallback_key",
           abs(_height({"BaseQuantities": {"ClearHeight": 2.55}}, scale=2.0) - 5.10) < 1e-9)

    print(f"\n{_PASS}/{_PASS + _FAIL} passed")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
