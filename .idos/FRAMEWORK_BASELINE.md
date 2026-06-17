# Framework measurement baseline (pre-registration)

Installed: 2026-06-17 at HEAD `02b64d1`.
Framework version: minimal-v1.

## Why this log exists
To judge, after 1-3 months, whether this minimal discipline layer adds value to ACC - by accrued non-fabricatable data, not by feeling. Mirrors the bug-bounty HARNESS_EXPERIMENT preregistration: do not claim the tool helps until the log says so.

## session_log.jsonl schema v1 (Stop hook; deterministic)
ts, dur_s, sha0, sha1, files, ins, dels, adr, tests, stops.

## events.jsonl schema v1 (Claude appends only when notable)
{ ts, kind: STOP|GATE|DEFECT|DEVIATION, note (<=30 words), ref }.

## Retrospective questions (answer at ~30/60/90 sessions)
1. Churn: files re-edited within 3 sessions trending down?
2. STOP yield: fraction of events that were a REAL caught issue?
3. ADR density: decision trail keeping pace with code growth?
4. Honest null: no signal => the layer is noise here; revise or remove, and say so openly.

## Analysis
A retro aggregation script is written LATER (not now). The schema is fixed NOW so the accruing data stays analyzable (comparability binding). If the schema must change, bump to v2 and never edit past rows.
