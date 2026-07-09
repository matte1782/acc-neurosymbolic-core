# API seam — `sandbox/api.py`

A deliberately thin FastAPI wrapper. The API adds **zero legal logic**: `pack_id` resolves to
the exact `(shapes, thresholds)` pair the CLI already consumes, so every engine guarantee
(fail-closed loading, ternary verdicts, refusals) flows through unchanged.

## Run

```bash
cd sandbox && uvicorn api:app --port 8000
```

## Endpoints

### `GET /health`
`{"status": "ok"}`

### `GET /packs`
Discoverable rule-pack registry — id, description, and the **live legal bars** (never guess
magic strings):

```json
{"packs": {"DM1975": {"description": "...", "bars": {"aero_illuminating_ratio": 0.125, ...}},
           "LOMBARDY_MOCK": {"description": "... MOCK (test fixture, not law) ...", "bars": {...}}}}
```

### `POST /evaluate` (multipart/form-data)

| Field | Type | Notes |
|---|---|---|
| `file` | file | the `.ifc` model (STEP; ≤ 200 MB) |
| `pack_id` | string | one of `GET /packs` |
| `salva_casa` | bool, optional | apply the DPR 380 art. 24 c. 5-bis derogation |

```bash
curl -s -F "file=@data/AC20-FZK-Haus.ifc" -F "pack_id=DM1975" \
     http://localhost:8000/evaluate | python -m json.tool
```

The response **leads with the answer**, then carries the full engine report verbatim:

```json
{
  "verdict": "violations",            // compliant | violations | undetermined | not_certifiable
  "pack":    {"id": "DM1975", "description": "...", "bars": {...}, "salva_casa": false},
  "model":   {"filename": "AC20-FZK-Haus.ifc", "schema": "IFC4"},
  "report":  { ...the standard checker report: findings[], violations, spaces_undetermined... }
}
```

Pipe `report` (or the whole envelope) into `python report_html.py -` … or save it and run
`python report_html.py response.json` for the human-readable rendering.

## Error taxonomy (classified, mirroring the CLI exits — never a traceback)

| Status | When | Body |
|---|---|---|
| 404 | unknown `pack_id` | `{"detail": {"error": "...", "available": [...]}}` |
| 413 | upload > 200 MB | — |
| 422 | not a STEP/IFC payload | `{"detail": {"error": "not a STEP/IFC file ..."}}` |
| 422 | engine refusal (**NOT CERTIFIABLE** — e.g. unresolvable length unit) | `{"detail": {"error": "not certifiable", "reason": "<the engine's own reason>"}}` |
| 422 | any other evaluation failure | `{"detail": {"error": "model could not be evaluated", ...}}` |
| 500 | a pack failed to emit/load server-side | reported, never a wrong verdict |

## Scope honesty

"Production-ready minimal" means: input validation, size caps, classified errors, no
traceback or temp-path leakage, deterministic engine underneath. It does **not** include
auth, TLS, rate limiting, or multi-tenancy — those are deployment concerns (ADR-019).
