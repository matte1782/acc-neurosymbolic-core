# Sandbox — First Neuro-Symbolic Bridge prototype (Slice A)

End-to-end proof of the **NL law → RASE rule (neuro) → deterministic IFC check (symbolic)**
pipeline, on the smallest slice that is *zero-cost* and *zero-hallucination*.

## Selected slice: **A — Italian geometric/hygienic rules**

> DM 5 luglio 1975 baseline (**2.70 m** habitable height · **1/8** aero-illuminating ratio)
> + the conditional **2.40 m** "Salva Casa" exception (DL 69/2024 conv. L 105/2024).

**Why A over B (Eurocode 2 deflection, span/250):**

| Criterion | Slice A (geometric/hygienic) | Slice B (EC2 deflection) |
|---|---|---|
| Data in free IFC files | `IfcSpace` + `IfcWindow` are in **every** architectural export (FZK-Haus, Duplex…) | `IfcStructuralAnalysisModel` + applied loads are **rarely** present |
| Computed inputs needed | none — heights/areas read directly | beam **deflection** must be **computed by an FEM solver** (IFC stores design geometry, not results) |
| IfcOpenShell sufficiency | **fully** (quantities + geometry) | insufficient alone — needs an external structural engine |
| Exercises LLM→KRR bridge | **strongly** — real Applicability/Selection/Exception (conditional Salva Casa) | weakly — a single `δ ≤ L/250` inequality |
| Cost | **€0** | €0 only if you also build/host a solver |

Slice B conflates ACC with structural analysis and depends on data that open IFC files do
not carry, so it cannot guarantee a zero-cost, IfcOpenShell-only validation. **Slice A wins.**

## Layout

```text
sandbox/
├── README.md
├── requirements.txt
├── rules/
│   └── dm_1975_salva_casa.md   # raw legal text (parser input)
├── parser.py                   # neuro: NL text -> RASE rule (Ollama + pydantic schema, fallback)
├── checker.py                  # symbolic: IfcOpenShell -> extract geometry -> flag violations
└── data/                       # drop free .ifc test models here (git-ignored)
```

## Run it (zero cost)

```bash
python -m venv .venv && . .venv/Scripts/activate     # Windows; use bin/activate on *nix
pip install -r requirements.txt

# 1) Neuro — compile the law text into a rule + thresholds JSON (deterministic, no LLM yet):
python parser.py rules/dm_1975_salva_casa.md --offline --out rules/compiled/dm_1975_salva_casa.json

# 2) Symbolic — check an IFC model; thresholds DRIVEN BY that JSON (no hard-coded constants):
python checker.py data/AC20-FZK-Haus.ifc --rules rules/compiled/dm_1975_salva_casa.json
python checker.py data/AC20-FZK-Haus.ifc --rules rules/compiled/dm_1975_salva_casa.json --salva-casa

# Stage-1 wiring proof: edit a number in rules/dm_1975_salva_casa.md (e.g. 2,70 → 2,40),
# re-run step 1, then step 2 — the verdict changes with no Python edit.
```

`parser.py` uses a **local** open LLM if reachable (set `OLLAMA_HOST`, `ACC_LLM_MODEL`,
default `llama3.1`); with `--offline` (or if no LLM) it falls back to **deterministic regex
extraction** of the thresholds from the law text, so the pipeline always runs offline. The
compiled `rules/compiled/*.json` is a generated artifact (re-created by step 1).

## Free test data (`.ifc`) — verified with IfcOpenShell 0.8.5 (2026-06-17)

| Model | Entities (measured) | Download |
|---|---|---|
| **AC20-FZK-Haus** (IFC4, primary fixture) | 7 `IfcSpace` · 11 `IfcWindow` · 81 `IfcRelSpaceBoundary`; height+area 100% | <https://www.steptools.com/docs/stpfiles/ifc/AC20-FZK-Haus.ifc> · <https://www.ifcwiki.org/images/e/e3/AC20-FZK-Haus.ifc> |
| **AC20-Institute-Var-2** (IFC4, primary fixture) | 82 `IfcSpace` · 206 `IfcWindow` · 1000 boundaries; height+area 100% | <https://www.steptools.com/docs/stpfiles/ifc/AC20-Institute-Var-2.ifc> |
| **Duplex Apartment** (IFC2X3, Revit) | 21 `IfcSpace` · 24 `IfcWindow`; **no** space Qto (height/area `None`), boundaries often `RelatedBuildingElement=None` | <https://github.com/buildingsmart-community/Community-Sample-Test-Files> |

Use **FZK-Haus** and **Institute-Var-2** as the reliable fixtures (complete quantities +
boundaries). The Revit Duplex is a good stress test for the missing-quantity / no-boundary
fallback paths (windows still resolve via `OverallHeight × OverallWidth`).

> **Quantity-set caveat (handled in `checker.py`):** ArchiCAD/KIT files name the space quantity
> set literally `BaseQuantities`, **not** `Qto_SpaceBaseQuantities` — the checker tries both, and
> prefers window `OverallHeight × OverallWidth` (always populated) over the often-missing
> `Qto_WindowBaseQuantities`.

## Environment note

`ifcopenshell` **0.8.5** is confirmed working on this machine's **Python 3.13 (win_amd64)** —
`pip install ifcopenshell` should resolve a wheel. If a future Python lacks a wheel, fall back to
conda-forge (`conda install -c conda-forge ifcopenshell`) or a 3.11/3.12 venv. `pydantic` and
`requests` are already present.

> Scope: this is an experimental sandbox, intentionally separate from the (still undesigned)
> production architecture. It exists to validate the bridge on one real, verifiable rule.
