#!/usr/bin/env python3
"""Neuro layer — parse legal natural-language text into a structured RASE rule (JSON).

A local open LLM (via Ollama, OpenAI-style structured output) extracts the rule's
structure; the output is constrained by the JSON Schema derived from the pydantic
models below and re-validated, so the deterministic checker (`checker.py`) only ever
consumes well-typed rules. If no LLM is reachable (or with --offline), a deterministic
regex extractor reads the headline numbers straight from the law text, so the pipeline
runs at zero cost and **editing the law .md changes the output** (Stage-1 wiring).

    python parser.py rules/dm_1975_salva_casa.md --offline --out rules/compiled/dm_1975.json

Output: JSON {rule, thresholds, source}. 'thresholds' is the flat contract checker.py reads.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from enum import Enum
from typing import List, Optional

try:
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover
    sys.exit("pydantic required: pip install pydantic")


class Operator(str, Enum):
    GE = ">="
    LE = "<="
    GT = ">"
    LT = "<"
    EQ = "=="


class Clause(BaseModel):
    """A single RASE operator extracted from the text."""

    kind: str = Field(description="requirement | applicability | selection | exception")
    subject: str = Field(description="entity the clause is about, e.g. 'habitable room'")
    metric: Optional[str] = Field(None, description="measured property, e.g. 'net height'")
    operator: Optional[Operator] = None
    value: Optional[float] = None
    unit: Optional[str] = Field(None, description="e.g. 'm', 'm2', 'ratio'")
    ifc_hint: Optional[str] = Field(None, description="suggested IFC target, e.g. IfcSpace.Height")
    text: str = Field(description="verbatim source span")


class Rule(BaseModel):
    """RASE-structured, machine-checkable rule (Requirement/Applicability/Selection/Exception)."""

    id: str
    source: str
    description: str
    ifc_target: List[str] = Field(default_factory=list)
    applicability: List[Clause] = Field(default_factory=list)
    selection: List[Clause] = Field(default_factory=list)
    requirement: List[Clause] = Field(default_factory=list)
    exception: List[Clause] = Field(default_factory=list)


RULE_JSON_SCHEMA = Rule.model_json_schema()

SYSTEM_PROMPT = (
    "You are a legal-to-logic extractor for building-code compliance. Decompose the "
    "provided regulation text into the RASE structure (Requirement, Applicability, "
    "Selection, Exception). Emit ONLY JSON matching the given schema. Use SI units "
    "(m, m2, ratio). Never invent thresholds that are not present in the text."
)

# --- Thresholds: the flat checker-ready contract emitted alongside the RASE rule ------
DEFAULT_THRESHOLDS = {
    "min_height_habitable_m": 2.70,
    "min_height_accessory_m": 2.40,
    "min_height_salva_casa_m": 2.40,
    "aero_illuminating_ratio": 0.125,
}


def _num(s: str) -> float:
    """Parse an Italian-style number ('2,70') to float."""
    return float(s.strip().replace(",", "."))


def extract_thresholds_from_text(text: str) -> dict:
    """Deterministic (regex) extraction of the headline numbers from the law text.

    This is the low-code Stage-1 bridge: editing the prose in ``rules/*.md`` changes these
    values, so the verdict changes with no Python edit. Best-effort — any key not found
    falls back to DEFAULT_THRESHOLDS in the caller. (Stage 2 replaces this with the LLM.)
    """
    out: dict = {}
    m = re.search(r"altezza minima interna utile.*?m\s*\*{0,2}\s*(\d+[.,]\d+)", text, re.S | re.I)
    if m:
        out["min_height_habitable_m"] = _num(m.group(1))
    m = re.search(r"riducibile a[^\d]*(\d+[.,]\d+)", text, re.S | re.I)
    if m:
        out["min_height_accessory_m"] = _num(m.group(1))
    m = re.search(r"(\d+)\s*/\s*(\d+)\s*della superficie del pavimento", text, re.S | re.I)
    if m:
        out["aero_illuminating_ratio"] = int(m.group(1)) / int(m.group(2))
    m = re.search(r"minimum internal height\s*\*{0,2}\s*(\d+[.,]\d+)", text, re.S | re.I)
    if m:
        out["min_height_salva_casa_m"] = _num(m.group(1))
    return out


def build_rule(thr: dict) -> Rule:
    """Assemble a RASE Rule from a thresholds dict (offline / text-extraction path)."""
    return Rule(
        id="IT-DM-1975-HAB",
        source="DM Sanità 5 luglio 1975; DL 69/2024 conv. L 105/2024 (Salva Casa)",
        description="Habitability: minimum internal height and aero-illuminating ratio for dwellings.",
        ifc_target=["IfcSpace", "IfcWindow"],
        applicability=[
            Clause(kind="applicability", subject="locale di abitazione", metric="use",
                   text="locali adibiti ad abitazione"),
        ],
        selection=[
            Clause(kind="selection", subject="habitable room", ifc_hint="IfcSpace",
                   text="vani abitabili (escl. corridoi, bagni, ripostigli)"),
        ],
        requirement=[
            Clause(kind="requirement", subject="habitable room", metric="net height",
                   operator=Operator.GE, value=thr["min_height_habitable_m"], unit="m",
                   ifc_hint="Qto_SpaceBaseQuantities.Height", text="altezza minima interna utile"),
            Clause(kind="requirement", subject="accessory room", metric="net height",
                   operator=Operator.GE, value=thr["min_height_accessory_m"], unit="m",
                   ifc_hint="Qto_SpaceBaseQuantities.Height",
                   text="riducibile per corridoi, disimpegni, bagni, ripostigli"),
            Clause(kind="requirement", subject="window", metric="openable area / floor area",
                   operator=Operator.GE, value=thr["aero_illuminating_ratio"], unit="ratio",
                   ifc_hint="IfcWindow area / IfcSpace NetFloorArea",
                   text="superficie finestrata apribile >= 1/8 della superficie del pavimento"),
        ],
        exception=[
            Clause(kind="exception", subject="existing building (recupero)", metric="net height",
                   operator=Operator.GE, value=thr["min_height_salva_casa_m"], unit="m",
                   ifc_hint="Qto_SpaceBaseQuantities.Height",
                   text="Salva Casa (DPR 380/2001 art. 24 c. 5-bis/5-ter): asseverabile, edificio esistente"),
        ],
    )


def compile_thresholds(rule: Rule) -> dict:
    """Map a RASE Rule's clauses back to the flat checker contract (LLM path)."""
    thr = dict(DEFAULT_THRESHOLDS)
    for c in rule.requirement:
        if c.value is None:
            continue
        if c.metric == "net height":
            key = "min_height_accessory_m" if "accessory" in c.subject.lower() else "min_height_habitable_m"
            thr[key] = float(c.value)
        elif c.unit == "ratio" or "area" in (c.metric or ""):
            thr["aero_illuminating_ratio"] = float(c.value)
    for c in rule.exception:
        if c.metric == "net height" and c.value is not None:
            thr["min_height_salva_casa_m"] = float(c.value)
    return thr


def parse_with_ollama(text: str, model: Optional[str] = None) -> Rule:
    """Call a local Ollama model with JSON-schema-constrained output. Raises on failure."""
    import requests  # local import: only needed for the neuro path

    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    model = model or os.environ.get("ACC_LLM_MODEL", "llama3.1")
    resp = requests.post(
        f"{host}/api/chat",
        json={
            "model": model,
            "format": RULE_JSON_SCHEMA,  # Ollama structured outputs (>= 0.5)
            "stream": False,
            "options": {"temperature": 0},  # determinism on the neuro side, best-effort
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        },
        timeout=120,
    )
    resp.raise_for_status()
    content = resp.json()["message"]["content"]
    return Rule.model_validate_json(content)


def parse_rule(text: str, offline: bool = False):
    """Return (rule, thresholds, source). source = llm | text-extraction | defaults."""
    if not offline:
        try:
            rule = parse_with_ollama(text)
            return rule, compile_thresholds(rule), "llm"
        except Exception as exc:  # noqa: BLE001 - degrade to deterministic text extraction
            print(f"[parser] LLM unavailable ({exc}); using deterministic text extraction",
                  file=sys.stderr)
    extracted = extract_thresholds_from_text(text)
    thr = {**DEFAULT_THRESHOLDS, **extracted}
    return build_rule(thr), thr, ("text-extraction" if extracted else "defaults")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Parse a legal snippet into a RASE rule + thresholds JSON")
    ap.add_argument("rule_md", help="path to the markdown law snippet")
    ap.add_argument("--offline", action="store_true", help="skip the LLM, use deterministic extraction")
    ap.add_argument("--out", metavar="FILE", help="write the compiled {rule, thresholds} JSON here")
    args = ap.parse_args(argv)

    with open(args.rule_md, encoding="utf-8") as fh:
        text = fh.read()
    rule, thr, source = parse_rule(text, offline=args.offline)
    payload = {"rule": json.loads(rule.model_dump_json()), "thresholds": thr, "source": source}
    out_json = json.dumps(payload, indent=2, ensure_ascii=False)

    if args.out:
        out_dir = os.path.dirname(args.out)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(out_json + "\n")
        print(f"[parser] wrote {args.out} (source={source}) thresholds={thr}", file=sys.stderr)
    else:
        print(out_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
