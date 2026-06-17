# ACC Neurosymbolic - Operating Contract (minimal framework)

This repo runs under a minimal deterministic discipline layer. No claude-mem.

## Session start (recall)
1. Read `docs/decisions.md` (the ADR chain) before any work. It is the memory.
2. State a numbered plan before editing code on a non-trivial task; wait for confirmation.

## Discipline (every session)
- STOP on a numeric/factual discrepancy, ambiguity, or scope creep beyond the prompt. Surface it; do not push through.
- Every factual claim about code/data cites `file:line` (or a source URL for research claims).
- Fix the code, not the harness. Never weaken a check or disable a hook to make something pass.
- Observation separate from interpretation.

## Memory backbone
- `docs/decisions.md`: append-only ADR chain, one decision per ADR. Never edit a past ADR; add an amendment `ADR-Na`.

## Measurement (do not skip - this is why the layer exists)
- `.idos/session_log.jsonl` is written automatically by the Stop hook (deterministic, zero-token). Do NOT write it by hand.
- When a STOP fires, a gate catches a real issue, or you find a defect: append ONE line to `.idos/events.jsonl` in the fixed schema (see `.idos/FRAMEWORK_BASELINE.md`), <=30 words. This is the 'where it worked / where it did not' signal for the retrospective.

## Excluded by design
- No claude-mem. No decorative prompt scripts. No heavy pre-commit gates at birth. No sub-agents yet.
