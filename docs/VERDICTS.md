# Verdicts — the ternary is the product

Most checkers answer pass/fail. This engine answers **pass / fail / "I cannot know"** — and
treats the third state as a first-class result, because in compliance work a guess dressed as
a verdict is worse than no verdict.

## The three states, per requirement and per space

| State | IT label | Meaning |
|---|---|---|
| `true` | **conforme** | The measurement exists, is trusted, and satisfies the legal bar. |
| `false` | **violazione** | The measurement exists, is trusted, and fails the bar. |
| `null` | **non determinabile** | The measurement is absent or cannot be trusted. The engine refuses to guess. |

A space is `compliant: true` **only if every requirement applicable to its class was actually
evaluated and passed**. Partial evidence never becomes a pass (ADR-003/ADR-004): a room with a
verified height but an unmeasurable window ratio is `non determinabile`, not compliant.

## How "undetermined" happens (always fail-closed, never silent)

- **Absent quantity** — no net height / floor area in the model → the SHACL `sh:minCount`
  guard fires; the value is omitted, never defaulted to 0 or assumed.
- **Untrusted measurement** — a window whose declared area is non-physical (larger than the
  floor it serves, negative, non-finite) is excluded; if the remaining trusted windows can't
  prove a pass, the space is undetermined (C-1b conservative lower-bound semantics).
- **Lower-bound-only evidence** — boundary-geometry areas (ADR-017) and spatial-fallback
  candidates (ADR-018) are proven lower/upper bounds: `≥ bar` on a lower bound proves a pass;
  `< bar` proves nothing and reads undetermined.

## Refusals (stronger than undetermined)

Some models cannot be measured *at all*. Those are **refused**, with a classified exit:

| Exit | Meaning |
|---|---|
| `0` | Every space evaluated, zero violations, zero undetermined. |
| `1` | Violations found, or undetermined spaces present, or zero evaluable spaces. |
| `2` | **NOT CERTIFIABLE** — e.g. the project length unit is absent/unresolvable (a silent 1000× misread risk), or a required measurement has no registered extractor. |

## Why you can believe this

Every legal bar is re-derived from the statute's own text by a validation gate that rejects
decoys, paraphrases, and edits (37 pinned cases). The comparison layer is declarative SHACL,
parameterized from gate-verified numbers. The whole pipeline is pinned by a dual-mode test
gate (script + pytest, exit 0), byte-frozen fixture controls, an adversarial IFC corpus
(GATE-S), and six independent adversarial review rounds — each of which found real defects
that are now permanent regression tests. The full decision history is public:
[`docs/decisions.md`](decisions.md).
