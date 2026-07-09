#!/usr/bin/env python3
"""ADR-019 — the platform seam: a minimal FastAPI wrapper over the compliance engine.

Design contract (deliberately thin — the ENGINE is the product, the API is a seam):
  * POST /evaluate: multipart IFC upload + a pack_id -> the standard checker report as JSON,
    wrapped in a small envelope whose FIRST field answers the human question ("verdict").
  * GET /packs: discoverable rule-pack registry (never make the caller guess magic strings).
  * GET /health: liveness.

The API adds NO legal logic: pack routing resolves to exactly the (ttl_path, Thresholds) pair
the CLI/orchestrator already consume, so every ADR-008..018 guarantee (fail-closed loading,
ternary verdicts, frozen extraction math) flows through unchanged. Error taxonomy mirrors the
CLI's classified exits: unknown pack -> 404; unreadable/non-IFC payload -> 422; a
NotCertifiableError REFUSAL -> 422 with the engine's own reason (never a silent pass);
oversized upload -> 413. Tracebacks never reach the client.

Run:    uvicorn api:app --port 8000        (from sandbox/)
Try:    curl -s http://localhost:8000/packs
        curl -s -F "file=@data/AC20-FZK-Haus.ifc" -F "pack_id=DM1975" \\
             http://localhost:8000/evaluate | python -m json.tool
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import Optional

_SANDBOX = Path(__file__).resolve().parent
sys.path.insert(0, str(_SANDBOX))

from fastapi import FastAPI, File, Form, HTTPException, UploadFile  # noqa: E402

import orchestrator  # noqa: E402

MAX_UPLOAD_BYTES = 200 * 1024 * 1024   # generous for IFC; refuse beyond (413)

app = FastAPI(
    title="ACC Neurosymbolic Compliance Engine",
    description="Deterministic Italian building-compliance verdicts from IFC models. "
                "Zero-hallucination: every legal bar is statute-gate-verified SHACL.",
    version="0.1.0",
)

# --- rule-pack registry --------------------------------------------------------------------
# Each pack resolves to the exact (ttl_path, Thresholds) pair the engine already consumes.
# LOMBARDY_MOCK is emitted lazily ONCE through the ADR-016 gate-verified emitter and cached;
# emission failure is a server-side 500 at request time, never a wrong verdict.
_LOMBARDY_CACHE: dict = {}


def _dm1975():
    import checker
    return None, checker.Thresholds(), "DM 5/7/1975 + Salva Casa (national baseline, aero 1/8)"


def _lombardy_mock():
    import checker
    import gate_spike as gs
    if "ttl" not in _LOMBARDY_CACHE:
        ttl_text = gs.emit_shacl(gs._LOMBARDY_MOCK_VERIFIED, None, gs._LOMBARDY_MOCK_CORPUS,
                                 spec=gs.LOMBARDY_MOCK_SPEC)
        gs.verify_emitted_shapes(ttl_text, gs._LOMBARDY_MOCK_VERIFIED,
                                 spec=gs.LOMBARDY_MOCK_SPEC)
        fd, path = tempfile.mkstemp(suffix=".ttl", prefix="lombardy_mock_")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(ttl_text)
        _LOMBARDY_CACHE["ttl"] = path
    thr = checker.Thresholds(requirements=checker._dm1975_requirements(3.00, 2.55, 2.55, 0.1))
    return _LOMBARDY_CACHE["ttl"], thr, \
        "Legge Regionale Lombardia MOCK (test fixture, not law; aero 1/10)"


PACKS = {
    "DM1975": _dm1975,
    "LOMBARDY_MOCK": _lombardy_mock,
}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/packs")
def packs() -> dict:
    """Discoverable pack registry — callers never guess magic strings."""
    out = {}
    for pack_id, loader in PACKS.items():
        try:
            _ttl, thr, desc = loader()
            out[pack_id] = {
                "description": desc,
                "bars": thr.to_legacy_dict(),
            }
        except Exception:  # noqa: BLE001 — a broken pack is reported, not hidden
            out[pack_id] = {"description": "UNAVAILABLE (pack failed to load)", "bars": None}
    return {"packs": out}


def _verdict_word(report: dict) -> str:
    if report["spaces_evaluated"] == 0:
        return "not_certifiable"           # H-1: a space-less model is uncheckable, not compliant
    if report["violations"]:
        return "violations"
    if report["spaces_undetermined"]:
        return "undetermined"              # honest: unmeasurable, never silently compliant
    return "compliant"


@app.post("/evaluate")
async def evaluate(file: UploadFile = File(...), pack_id: str = Form(...),
                   salva_casa: bool = Form(False)) -> dict:
    """Evaluate one IFC model against one rule pack. The envelope leads with the answer."""
    loader = PACKS.get(pack_id)
    if loader is None:
        raise HTTPException(status_code=404,
                            detail={"error": f"unknown pack_id {pack_id!r}",
                                    "available": sorted(PACKS)})
    try:
        ttl_path, thr, desc = loader()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500,
                            detail={"error": f"pack {pack_id!r} failed to load",
                                    "reason": str(exc)[:300]})
    payload = await file.read()
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail={"error": "upload exceeds 200 MB"})
    if not payload.lstrip()[:20].startswith(b"ISO-10303-21"):
        raise HTTPException(status_code=422,
                            detail={"error": "not a STEP/IFC file (missing ISO-10303-21 header)"})
    tmp: Optional[str] = None
    try:
        fd, tmp = tempfile.mkstemp(suffix=".ifc", prefix="acc_upload_")
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
        report = orchestrator.ComplianceOrchestrator(
            tmp, ttl_path=ttl_path, salva_casa=salva_casa, thr=thr).run()
    except Exception as exc:  # noqa: BLE001
        import checker
        if isinstance(exc, checker.NotCertifiableError):
            # The engine's classified REFUSAL (exit-2 class): measurement impossible.
            raise HTTPException(status_code=422,
                                detail={"error": "not certifiable", "reason": str(exc)[:500]})
        raise HTTPException(status_code=422,
                            detail={"error": "model could not be evaluated",
                                    "reason": str(exc)[:300]})
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    report.pop("model", None)                     # never echo a server-side temp path
    return {
        "verdict": _verdict_word(report),
        "pack": {"id": pack_id, "description": desc, "bars": thr.to_legacy_dict(),
                 "salva_casa": salva_casa},
        "model": {"filename": file.filename, "schema": report.get("schema")},
        "report": report,
    }
