#!/usr/bin/env python3
"""Neuro layer — parse legal natural-language text into a structured RASE rule (JSON).

A local open LLM (via Ollama, OpenAI-style structured output) extracts the rule's
structure; the output is constrained by the JSON Schema derived from the pydantic
models below and re-validated, so the deterministic checker (`checker.py`) only ever
consumes well-typed rules. If no LLM is reachable, a hand-coded ``FALLBACK_RULE`` keeps
the end-to-end pipeline runnable at zero cost.

    python parser.py rules/dm_1975_salva_casa.md            # LLM if available, else fallback
    python parser.py rules/dm_1975_salva_casa.md --offline  # force fallback (no LLM)

Skeleton: the schema + RASE structure are real; the LLM call degrades gracefully.
"""
from __future__ import annotations

import argparse
import os
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

# Hand-coded ground truth for Slice A so the pipeline runs without any LLM.
FALLBACK_RULE = Rule(
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
               operator=Operator.GE, value=2.70, unit="m",
               ifc_hint="Qto_SpaceBaseQuantities.Height",
               text="altezza minima interna utile m 2,70"),
        Clause(kind="requirement", subject="accessory room", metric="net height",
               operator=Operator.GE, value=2.40, unit="m",
               ifc_hint="Qto_SpaceBaseQuantities.Height",
               text="riducibile a m 2,40 per corridoi, disimpegni, bagni, ripostigli"),
        Clause(kind="requirement", subject="window", metric="openable area / floor area",
               operator=Operator.GE, value=0.125, unit="ratio",
               ifc_hint="IfcWindow area / IfcSpace NetFloorArea",
               text="superficie finestrata apribile >= 1/8 della superficie del pavimento"),
    ],
    exception=[
        Clause(kind="exception", subject="existing building (recupero)", metric="net height",
               operator=Operator.GE, value=2.40, unit="m",
               ifc_hint="Qto_SpaceBaseQuantities.Height",
               text=("Salva Casa (DPR 380/2001 art. 24 c. 5-bis/5-ter): m 2,40 asseverabile per "
                     "edificio esistente, SE recupero/cambio d'uso AND adattabilita DM 236/1989 "
                     "AND ristrutturazione con soluzioni alternative igienico-sanitarie")),
    ],
)


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


def parse_rule(text: str, offline: bool = False) -> Rule:
    if offline:
        return FALLBACK_RULE
    try:
        return parse_with_ollama(text)
    except Exception as exc:  # noqa: BLE001 - skeleton degrades gracefully
        print(f"[parser] LLM unavailable ({exc}); using FALLBACK_RULE", file=sys.stderr)
        return FALLBACK_RULE


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Parse a legal snippet into a RASE rule (JSON)")
    ap.add_argument("rule_md", help="path to the markdown law snippet")
    ap.add_argument("--offline", action="store_true", help="skip the LLM, emit FALLBACK_RULE")
    args = ap.parse_args(argv)

    with open(args.rule_md, encoding="utf-8") as fh:
        text = fh.read()
    rule = parse_rule(text, offline=args.offline)
    print(rule.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
