#!/usr/bin/env python3
"""Deterministic compliance checker — Slice A: Italian habitability (DM 5/7/1975 + Salva Casa).

This is the *symbolic* / zero-hallucination half of the neuro-symbolic bridge. It reads
geometry and quantities straight from an IFC model with IfcOpenShell and evaluates the rule
with plain Python arithmetic — no LLM, fully reproducible.

Rule under test (see rules/dm_1975_salva_casa.md):
    R1   habitable room net height        >= 2.70 m   (accessory rooms >= 2.40 m)
    R1'  Salva Casa exception (existing building, recupero, asseverazione) -> 2.40 m
    R2   rapporto aeroilluminante: openable window area >= 1/8 of room floor area

Usage:
    python checker.py model.ifc                  # baseline DM 1975
    python checker.py model.ifc --salva-casa     # apply the 2.40 m conditional exception
    python checker.py model.ifc --json out.json  # also write the full report
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from typing import List, Optional

try:
    import ifcopenshell
    import ifcopenshell.util.element as ue
    import ifcopenshell.util.unit as uu
except ImportError as exc:  # pragma: no cover - environment guard
    sys.exit(
        "IfcOpenShell is required for the deterministic checker.\n"
        "  pip install ifcopenshell   (needs a wheel for your Python version; if none is\n"
        "  available, use conda-forge `ifcopenshell` or a Python 3.11/3.12 venv)\n"
        f"  import error: {exc}"
    )

# --- Verified thresholds (rules/dm_1975_salva_casa.md) ---------------------------------
MIN_HEIGHT_HABITABLE_M = 2.70   # DM 5/7/1975 art. 1
MIN_HEIGHT_ACCESSORY_M = 2.40   # corridoi, disimpegni, bagni, ripostigli
MIN_HEIGHT_SALVA_CASA_M = 2.40  # DL 69/2024 conv. L 105/2024 — conditional, existing buildings
AEROILLUM_RATIO = 1.0 / 8.0     # superficie finestrata apribile / superficie pavimento

# Heuristic classification of an IfcSpace by name (Name / LongName).
_HABITABLE_HINTS = ("living", "soggiorno", "bed", "letto", "camera", "kitchen", "cucina",
                    "dining", "pranzo", "studio", "room", "stanza",
                    # German (KIT/FZK fixtures)
                    "wohn", "schlaf", "kuche", "küche", "kind", "ess", "zimmer", "galerie",
                    "buro", "büro")
_ACCESSORY_HINTS = ("corrid", "disimpegno", "bagno", "wc", "toilet", "bath", "closet",
                    "ripostiglio", "hall", "ingresso", "storage", "lavanderia", "laundry",
                    # German
                    "flur", "diele", "bad", "abstell", "keller", "treppe", "gaste", "gäste",
                    "speis", "technik", "hwr", "garage")


@dataclass
class SpaceFinding:
    global_id: str
    name: str
    occupancy: str                       # habitable | accessory | unknown
    height_m: Optional[float]
    floor_area_m2: Optional[float]
    window_area_m2: float
    aero_ratio: Optional[float]
    height_required_m: float
    height_ok: Optional[bool]
    aero_ok: Optional[bool]
    notes: List[str] = field(default_factory=list)

    @property
    def compliant(self) -> Optional[bool]:
        checks = [c for c in (self.height_ok, self.aero_ok) if c is not None]
        return all(checks) if checks else None


# Candidate quantity-set names. ArchiCAD/KIT files (incl. AC20-FZK-Haus) name the set
# literally "BaseQuantities", not "Qto_SpaceBaseQuantities" — verified empirically with
# IfcOpenShell 0.8.5, so both names must be tried.
_SPACE_QTO = ("Qto_SpaceBaseQuantities", "BaseQuantities")
_WINDOW_QTO = ("Qto_WindowBaseQuantities", "BaseQuantities")


def _qty(element, scale: float, pset_names, key: str, power: int = 1) -> Optional[float]:
    """Read a quantity from the first matching (Q)set name, converting length**power to metres."""
    qtos = ue.get_psets(element, qtos_only=True)  # 'id'/'type' helper keys are ignored by .get(key)
    for name in pset_names:
        raw = qtos.get(name, {}).get(key)
        if raw is not None:
            try:
                return float(raw) * (scale ** power)
            except (TypeError, ValueError):
                return None
    return None


def space_height(space, scale: float) -> Optional[float]:
    return _qty(space, scale, _SPACE_QTO, "Height", power=1)


def space_floor_area(space, scale: float) -> Optional[float]:
    for key in ("NetFloorArea", "GrossFloorArea"):
        val = _qty(space, scale, _SPACE_QTO, key, power=2)
        if val:
            return val
    return None


def window_area(win, scale: float) -> Optional[float]:
    # Prefer the direct OverallHeight x OverallWidth attributes: vendor-independent and
    # populated 100% across all tested models, whereas Qto_WindowBaseQuantities is often absent.
    h, w = getattr(win, "OverallHeight", None), getattr(win, "OverallWidth", None)
    if h and w:
        return float(h) * float(w) * (scale ** 2)
    return _qty(win, scale, _WINDOW_QTO, "Area", power=2)


def classify(space) -> str:
    label = " ".join(str(x or "").lower() for x in (space.Name, space.LongName))
    if any(hint in label for hint in _ACCESSORY_HINTS):
        return "accessory"
    if any(hint in label for hint in _HABITABLE_HINTS):
        return "habitable"
    return "unknown"


def windows_serving(space, scale: float) -> float:
    """Sum window areas via IfcRelSpaceBoundary (``space.BoundedBy``). Returns 0.0 if none.

    TODO: fallback when a model lacks space boundaries — associate windows by storey
    containment / exterior-wall hosting. Many architectural exports omit IfcRelSpaceBoundary.
    """
    total = 0.0
    for rel in (space.BoundedBy or []):
        elem = getattr(rel, "RelatedBuildingElement", None)
        if elem is not None and elem.is_a("IfcWindow"):
            total += window_area(elem, scale) or 0.0
    return total


def check_space(space, scale: float, salva_casa: bool) -> SpaceFinding:
    occ = classify(space)
    h = space_height(space, scale)
    area = space_floor_area(space, scale)
    win = windows_serving(space, scale)

    required = MIN_HEIGHT_ACCESSORY_M if occ == "accessory" else MIN_HEIGHT_HABITABLE_M
    if salva_casa and occ != "accessory":
        required = MIN_HEIGHT_SALVA_CASA_M

    finding = SpaceFinding(
        global_id=space.GlobalId,
        name=space.Name or space.LongName or "(unnamed)",
        occupancy=occ,
        height_m=round(h, 3) if h is not None else None,
        floor_area_m2=round(area, 3) if area is not None else None,
        window_area_m2=round(win, 3),
        aero_ratio=round(win / area, 4) if area else None,
        height_required_m=required,
        height_ok=None,
        aero_ok=None,
    )

    if h is not None:
        finding.height_ok = h + 1e-6 >= required
    else:
        finding.notes.append("no Qto_SpaceBaseQuantities.Height — geometry fallback needed")

    # The 1/8 aero-illuminating ratio (DM 1975 art. 5) applies to habitable rooms; accessory
    # spaces (bagni, ripostigli, corridoi) follow separate ventilation rules — skip R2 there.
    if occ == "accessory":
        finding.notes.append("aero ratio N/A for accessory room (separate ventilation rules)")
    elif area:
        finding.aero_ok = (win / area) + 1e-9 >= AEROILLUM_RATIO
        if win == 0.0:
            finding.notes.append("no window via IfcRelSpaceBoundary — aero ratio may be understated")
    else:
        finding.notes.append("no NetFloorArea — cannot evaluate aero ratio")

    return finding


def run(path: str, salva_casa: bool = False) -> dict:
    model = ifcopenshell.open(path)
    scale = uu.calculate_unit_scale(model)  # project length unit -> metres
    findings = [check_space(s, scale, salva_casa) for s in model.by_type("IfcSpace")]
    serialized = []
    for f in findings:
        record = asdict(f)
        record["compliant"] = f.compliant  # property is not captured by asdict()
        serialized.append(record)
    violations = [d for d in serialized if d["compliant"] is False]
    return {
        "model": path,
        "schema": model.schema,
        "length_unit_scale_to_m": scale,
        "salva_casa": salva_casa,
        "spaces_evaluated": len(serialized),
        "violations": len(violations),
        "findings": serialized,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Deterministic ACC checker — Slice A (IT habitability)")
    ap.add_argument("ifc", help="path to the .ifc model")
    ap.add_argument("--salva-casa", action="store_true",
                    help="apply the conditional 2.40 m exception (existing buildings)")
    ap.add_argument("--json", metavar="FILE", help="write the full report as JSON")
    args = ap.parse_args(argv)

    report = run(args.ifc, args.salva_casa)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False)

    print(f"{report['schema']} | {report['spaces_evaluated']} IfcSpace | "
          f"{report['violations']} violation(s) | salva_casa={report['salva_casa']}")
    for f in report["findings"]:
        if f["compliant"] is False:
            print(f"  [X] {f['name']} [{f['occupancy']}] "
                  f"h={f['height_m']}m (>= {f['height_required_m']}) "
                  f"aero={f['aero_ratio']} (>= {round(AEROILLUM_RATIO, 3)}) {f['notes']}")
    return 1 if report["violations"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
