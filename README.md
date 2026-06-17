# acc-neurosymbolic-core

Open-source, self-hostable **Automated Compliance Checking (ACC)** framework that bridges
natural-language building/zoning regulation (Italian *Testo Unico Edilizia*, European
*Eurocodes*) and open structural models via the neutral **IFC / openBIM** data standard.

The paradigm is **neuro-symbolic**: probabilistic LLMs parse messy legal text into structured
rules, while deterministic Knowledge Representation & Reasoning (SMT solvers, ASP, RDF/SHACL,
OWL reasoners) performs the actual zero-hallucination compliance check against the IFC model.

## Status

Phase 0 — **factual baseline only**. No architecture, code, classes, or database schemas
have been committed yet. This is deliberate (see *Working constraints*): the factual
constraints of existing tools and regulatory data structures will dictate the architecture
in a later phase.

## Working constraints

1. **Strict determinism.** Findings are grounded in empirical facts, active repository
   metrics, peer-reviewed literature (through 2026), and concrete economic data — not
   speculative AI-marketing language.
2. **No pre-imposed architecture.** No code structures, classes, or DB schemas until the
   research baseline is settled.
3. **Self-hostable first.** Prefer primitives that run on commodity hardware / free tiers,
   to bypass the compute-wealth trap.

## Layout

```text
acc-neurosymbolic-core/
├── README.md
├── .gitignore
└── research/
    └── FACTUAL_BASELINE.md   # market, competitor, OSS-stack, and ROI baseline
```

## Generated artefacts

- [`research/FACTUAL_BASELINE.md`](research/FACTUAL_BASELINE.md) — the deterministic
  research baseline (competitor matrix, audited OSS stack, quantitative ROI, data
  bottlenecks).
