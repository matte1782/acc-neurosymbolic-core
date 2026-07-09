#!/usr/bin/env python3
"""ADR-019 unit tests — the FastAPI platform seam (sandbox/api.py).

Pinned contract: the API adds NO legal logic — it routes pack_id to the exact
(ttl_path, Thresholds) pair the orchestrator already consumes, so the SAME synthetic model
flips DM1975 (1/8) violation -> LOMBARDY_MOCK (1/10) compliant purely through the pack, and
the classified engine refusals surface as classified HTTP errors (never a silent pass, never
a traceback). SKIPPED (counted) when fastapi/httpx or ifcopenshell are absent.

Run either way:
    python test_api.py     # prints PASS/FAIL/SKIP, exit 1 on any failure
    pytest test_api.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_SANDBOX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SANDBOX))

_PASS = _FAIL = _SKIP = 0
_TMPROOT = tempfile.TemporaryDirectory(prefix="adr019_")


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


def _try_client():
    try:
        import ifcopenshell  # noqa: F401
        from fastapi.testclient import TestClient
        import api
        return TestClient(api.app), None
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def _synthetic_ifc_bytes(window_width: float = 1.2) -> bytes:
    """The showcase model: one habitable FZK-style space (Qto 3.10 m / 10 m²) + one IfcWindow
    attached via IfcRelSpaceBoundary. width 1.2 -> aero 0.12 (between 1/10 and 1/8)."""
    import ifcopenshell as ifc
    f = ifc.file(schema="IFC4")
    metre = f.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")
    f.create_entity("IfcProject", GlobalId=ifc.guid.new(), Name="api-demo",
                    UnitsInContext=f.create_entity("IfcUnitAssignment", Units=[metre]))
    space = f.create_entity("IfcSpace", GlobalId=ifc.guid.new(), Name="Soggiorno")
    qto = f.create_entity(
        "IfcElementQuantity", GlobalId=ifc.guid.new(), Name="BaseQuantities",
        Quantities=[f.create_entity("IfcQuantityLength", Name="Height", LengthValue=3.10),
                    f.create_entity("IfcQuantityArea", Name="NetFloorArea", AreaValue=10.0)])
    f.create_entity("IfcRelDefinesByProperties", GlobalId=ifc.guid.new(),
                    RelatedObjects=[space], RelatingPropertyDefinition=qto)
    win = f.create_entity("IfcWindow", GlobalId=ifc.guid.new(), Name="W1",
                          OverallHeight=1.0, OverallWidth=window_width)
    f.create_entity("IfcRelSpaceBoundary", GlobalId=ifc.guid.new(), RelatingSpace=space,
                    RelatedBuildingElement=win, PhysicalOrVirtualBoundary="PHYSICAL",
                    InternalOrExternalBoundary="EXTERNAL")
    p = os.path.join(tempfile.mkdtemp(dir=_TMPROOT.name), "demo.ifc")
    f.write(p)
    return open(p, "rb").read()


def test_api_seam() -> None:
    client, why = _try_client()
    if client is None:
        _skip("api_seam", f"fastapi/httpx/ifcopenshell unavailable: {why}")
        return
    r = client.get("/health")
    _check("api_health", r.status_code == 200 and r.json()["status"] == "ok")
    r = client.get("/packs")
    body = r.json()
    _check("api_packs_discoverable",
           r.status_code == 200 and set(body["packs"]) == {"DM1975", "LOMBARDY_MOCK"}
           and body["packs"]["DM1975"]["bars"]["aero_illuminating_ratio"] == 0.125
           and body["packs"]["LOMBARDY_MOCK"]["bars"]["aero_illuminating_ratio"] == 0.1)
    ifc_bytes = _synthetic_ifc_bytes()
    # The same model, two legal frameworks: 0.12 fails 1/8, clears 1/10.
    r_dm = client.post("/evaluate", files={"file": ("demo.ifc", ifc_bytes)},
                       data={"pack_id": "DM1975"})
    r_lo = client.post("/evaluate", files={"file": ("demo.ifc", ifc_bytes)},
                       data={"pack_id": "LOMBARDY_MOCK"})
    ok_dm = r_dm.status_code == 200 and r_dm.json()["verdict"] == "violations" \
        and r_dm.json()["report"]["findings"][0]["aero_ok"] is False
    ok_lo = r_lo.status_code == 200 and r_lo.json()["verdict"] == "compliant" \
        and r_lo.json()["report"]["findings"][0]["aero_ok"] is True
    _check("api_dm1975_violation", ok_dm)
    _check("api_lombardy_pass", ok_lo)
    _check("api_no_temp_path_leak", "model" not in r_dm.json()["report"])
    # Classified errors, never guesses.
    r = client.post("/evaluate", files={"file": ("demo.ifc", ifc_bytes)},
                    data={"pack_id": "VENETO"})
    _check("api_unknown_pack_404",
           r.status_code == 404 and "available" in r.json()["detail"])
    r = client.post("/evaluate", files={"file": ("junk.ifc", b"not an ifc at all")},
                    data={"pack_id": "DM1975"})
    _check("api_non_ifc_422", r.status_code == 422)
    # The engine's NotCertifiable refusal (no resolvable LENGTHUNIT) surfaces classified.
    import ifcopenshell as ifc
    f = ifc.file(schema="IFC4")
    f.create_entity("IfcProject", GlobalId=ifc.guid.new(), Name="unitless")
    f.create_entity("IfcSpace", GlobalId=ifc.guid.new(), Name="Soggiorno")
    p = os.path.join(tempfile.mkdtemp(dir=_TMPROOT.name), "unitless.ifc")
    f.write(p)
    r = client.post("/evaluate", files={"file": ("unitless.ifc", open(p, "rb").read())},
                    data={"pack_id": "DM1975"})
    _check("api_not_certifiable_classified",
           r.status_code == 422 and r.json()["detail"]["error"] == "not certifiable")


def main() -> int:
    test_api_seam()
    print(f"\n{_PASS}/{_PASS + _FAIL} passed, {_SKIP} skipped")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
