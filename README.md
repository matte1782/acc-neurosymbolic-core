# ACC Neurosymbolic Core

**Deterministic Italian building-compliance verdicts from IFC models — fail-closed by design.**

Point it at an openBIM model and it checks the DM 5/7/1975 habitability requirements
(minimum heights, 1/8 aero-illuminating ratio, Salva Casa derogation) with zero-hallucination
mechanics: every legal bar is re-derived from the statute's own text by a validation gate,
the comparison layer is declarative SHACL, and when something cannot be measured the engine
answers **non determinabile** — it refuses to guess. Local-first: your model never leaves
your machine.

## See it in 60 seconds

```bash
bash scripts/quickstart_demo.sh
```

```text
  ACC Neurosymbolic Compliance Engine — quickstart
  ──────────────────────────────────────────────────────────────────
  Model    Soggiorno · floor 10.00 m² · height 3.10 m · window 1.20 m²
  Measured aero-illuminating ratio: 0.12

  1 · DM 5/7/1975 — national baseline (aero ≥ 1/8)
    height   3.10 m  ≥ 2.70 m   PASS
    aero     0.12  ≥ 0.125   FAIL
    verdict  VIOLATION   (1 violation(s) · 110 ms)

  2 · LR Lombardia MOCK — regional pack (aero ≥ 1/10)
    height   3.10 m  ≥ 3.00 m   PASS
    aero     0.12  ≥ 0.100   PASS
    verdict  COMPLIANT   (0 violation(s) · 5 ms)

  Same building, same extraction — the verdict flips purely through the
  swapped, statute-gate-verified SHACL rule pack.
```

The verdict flips between legal frameworks in milliseconds because rules are **data**
(gate-verified SHACL packs), not code. The regional pack shown is a labeled test fixture —
[coverage honesty here](docs/COVERAGE.md).

## Why you could trust a verdict (the actual argument)

Compliance tools fail dangerously in one direction: the confident false pass. This engine is
built, tested, and *documented* against that direction:

- **Ternary verdicts, fail-closed.** Pass / violation / **undetermined** — a space with an
  unmeasurable quantity can never read compliant. Unmeasurable *models* are refused outright
  (classified exit 2, "NOT CERTIFIABLE"). [How verdicts work →](docs/VERDICTS.md)
- **Statute-anchored bars.** Thresholds are not typed into code; a validation gate re-derives
  each number from the statute corpus and rejects decoys, paraphrases, and edits
  (37 pinned replay cases, precision 1.000 across live runs).
- **Adversarially verified, in public.** Six independent red-team rounds so far; every round
  found real defects in freshly-shipped code — each reproduced, fixed, and pinned as a
  permanent regression test. The complete decision history, defects included, is in
  [`docs/decisions.md`](docs/decisions.md) (ADR-001…019).
- **A regression wall.** 281 case-level checks across 13 dual-mode suites
  ([`scripts/run_all_tests.sh`](scripts/run_all_tests.sh), exit 0), byte-frozen fixture
  controls, mutation + metamorphic suites, and an adversarial IFC corpus
  ([`research/corpus/`](research/corpus/), GATE-S) that proves the fail-closed guards refuse
  what they must.

## What it checks (and what it doesn't)

Today: **DM 5/7/1975 art. 1 heights (2.70/2.40 m), art. 5 aero ratio (1/8), and the
DPR 380/2001 art. 24 c. 5-bis Salva Casa derogation** — per IfcSpace, on IFC4/IFC2X3 models.
Everything else (structural, fire, energy, accessibility, municipal regolamenti) is out of
scope and says so. Full table, measurement boundaries, and fixture evidence:
[docs/COVERAGE.md](docs/COVERAGE.md).

## Use it

```bash
pip install -r sandbox/requirements.txt
cd sandbox
python checker.py data/AC20-FZK-Haus.ifc --json report.json   # CLI verdict
python report_html.py report.json                             # human-readable report (IT)
uvicorn api:app --port 8000                                   # optional self-hosted API
```

[Quickstart](docs/QUICKSTART.md) · [API contract](docs/API.md) ·
[FAQ / honest limits](docs/FAQ.md)

## For Italian practitioners — cerchiamo design partner

Sei un geometra, architetto, ingegnere o BIM manager che tratta pratiche di abitabilità
(CILA/SCIA/agibilità/Salva Casa)? Cerchiamo 3–5 professionisti per interviste da 30 minuti e
piloti sui loro modelli IFC — gratuitamente, in cambio di feedback sul report.

**Contatto:** Matteo Panzeri —
[matteo.panzeri@universitadipavia.it](mailto:matteo.panzeri@universitadipavia.it)
(oggetto: "pilota ACC"). Materiale: [docs/OUTREACH_IT.md](docs/OUTREACH_IT.md).

## Status & scope honesty

Pre-1.0, research-grade, single-slice (Italian habitability). Nothing here is legal advice;
verdicts do not replace professional judgment. Licensing: engine under
[Apache-2.0](LICENSE); dependency inventory in [`NOTICE`](NOTICE) (ifcopenshell is
LGPL-3.0-or-later, consumed as an ordinary replaceable dependency);
architecture/strategy notes in [`research/`](research/), roadmap in
[`ROADMAP.md`](ROADMAP.md).
