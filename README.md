# acc-neurosymbolic-core

Open-source, self-hostable **Automated Compliance Checking (ACC)** framework that bridges
natural-language building/zoning regulation (Italian *Testo Unico Edilizia*, European
*Eurocodes*) and open structural models via the neutral **IFC / openBIM** data standard.

The paradigm is **neuro-symbolic**: probabilistic LLMs parse messy legal text into structured
rules, while deterministic Knowledge Representation & Reasoning (SMT solvers, ASP, RDF/SHACL,
OWL reasoners) performs the actual zero-hallucination compliance check against the IFC model.

## Status

Stage 0 (foundation) ✅ — the deterministic research baseline is done, and a **sandbox
prototype** of the neuro-symbolic bridge runs end-to-end on a real IFC model (Slice A:
Italian habitability, DM 5/7/1975 + Salva Casa). Production progress is tracked stage-by-stage
in **[`ROADMAP.md`](ROADMAP.md)** — the single source of truth, updated every iteration.

Architecture beyond the sandbox is still intentionally undesigned (see *Working constraints*):
existing tools and regulatory data structures dictate it, not the other way round.

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
├── ROADMAP.md                # production roadmap (4 stages) — living, updated each iteration
├── .gitignore
├── research/
│   └── FACTUAL_BASELINE.md   # market, competitor, OSS-stack, and ROI baseline
└── sandbox/                  # Stage-0 prototype of the neuro-symbolic bridge (Slice A)
    ├── rules/                # raw law + RASE decomposition
    ├── parser.py             # neuro: NL → RASE rule JSON
    └── checker.py            # symbolic: IfcOpenShell → deterministic verdict
```

## Generated artefacts

- **[`ROADMAP.md`](ROADMAP.md)** — production roadmap and progress tracker (Stages 1–4).
- [`research/FACTUAL_BASELINE.md`](research/FACTUAL_BASELINE.md) — the deterministic
  research baseline (competitor matrix, audited OSS stack, quantitative ROI, data
  bottlenecks).
- [`sandbox/`](sandbox/README.md) — verified end-to-end prototype (Italian habitability slice).
