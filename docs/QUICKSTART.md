# Quickstart

Everything runs locally, on commodity hardware, with no cloud calls.

## Install

```bash
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r sandbox/requirements.txt        # engine core; the API block is optional
```

`ifcopenshell` needs a wheel for your Python version (3.11–3.13 are fine; else conda-forge).

## 1. The 60-second demo — one building, two legal frameworks

```bash
bash scripts/quickstart_demo.sh
```

Builds a synthetic room (aero-illuminating ratio 0.12 — deliberately *between* the regional
mock's 1/10 and the national 1/8), evaluates it under both rule packs, and shows the verdict
flip in ~100 ms. `NO_COLOR=1` for plain output.

## 2. Check a real IFC model (CLI)

The test fixtures are NOT shipped in this repo (they are third-party IFC files, gitignored).
Download them once into `sandbox/data/`: [AC20-FZK-Haus and AC20-Institute-Var-2 (KIT
IFC examples)](https://www.ifcwiki.org/index.php?title=KIT_IFC_Examples) and
[Duplex Apartment (buildingSMART sample files)](https://github.com/buildingsmart-community/Community-Sample-Test-Files) —
or just use your own `.ifc`.

```bash
cd sandbox
python checker.py data/AC20-FZK-Haus.ifc                       # DM 5/7/1975 baseline
python checker.py data/AC20-FZK-Haus.ifc --salva-casa          # Salva Casa derogation
python checker.py data/AC20-FZK-Haus.ifc --json report.json    # machine-readable verdict
```

Exit codes are part of the contract: `0` compliant · `1` violations / undetermined /
no evaluable space · `2` NOT CERTIFIABLE (the model cannot be measured — e.g. no resolvable
length unit; a refusal, never a silent pass).

## 3. Render the verdict for humans

```bash
python report_html.py report.json --title "Pratica 123/2026"
```

Writes a single self-contained HTML file (IT-first labels, print-clean, no external
requests). See [VERDICTS.md](VERDICTS.md) for what CONFORME / VIOLAZIONE /
NON DETERMINABILE mean — the ternary is the point.

## 4. Serve it (optional API seam)

```bash
cd sandbox && uvicorn api:app --port 8000
curl -s http://localhost:8000/packs
curl -s -F "file=@data/AC20-FZK-Haus.ifc" -F "pack_id=DM1975" \
     http://localhost:8000/evaluate | python -m json.tool
```

See [API.md](API.md) for the full contract.

## 5. Prove it to yourself

```bash
bash scripts/run_all_tests.sh          # the dual-mode gate: every suite, both modes, exit 0
python research/corpus/eval_corpus.py  # the adversarial corpus (GATE-S)
```
