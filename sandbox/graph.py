#!/usr/bin/env python3
"""Stage 4b — graph layer for occupancy/applicability discovery.

The room->occupancy decision is answered by a **SPARQL 1.1 query over an rdflib in-memory
ontology** (`occupancy_via_graph`), the seam that replaces `checker.classify()`'s Python substring
branch in Task 2. This module is the read-only graph layer (Task 1): it builds + caches the
ontology and answers the query; it does NOT import `checker` (one-directional dependency:
`checker -> graph`, never back — and `checker`'s module-top `import ifcopenshell` sys.exits when the
wheel is absent, checker.py:27-37, so the neuro/graph layer must stay independent).

HONESTY CONTRACT (baseline §1 / §6 / §7; ADR-006). On the 3 current fixtures **every room is
flat-substring-decidable**, so a graph seeded from the same hints is **verdict-equivalent to the
flat table BY CONSTRUCTION** — reproducing the controls proves a *faithful copy of classify()*, NOT
correctness. What this layer actually delivers, and all it claims, is exactly three things:
  1. the architectural seam (room->occupancy via a SPARQL query over a store);
  2. **bounded** statute-anchoring: 4 of 51 occupancy tokens (the Art.1 enumeration corrid/
     disimpegno/bagno/ripostiglio) are checked against the statute prose; the other 47 are
     `classify()`-derived, reproduced-not-independently-verified, cross-lingual = declared debt;
  3. a transitive `rdfs:subClassOf+` inference capability demonstrated on a **synthetic** divergence
     room (no real fixture needs it, baseline §6).
Circularity is **bounded, NOT eliminated.** The seed (`applicability.json`) is the SAME data the
flat table reads, so the ontology is non-cosmetic only at the seam / anchor / inference-capability
level, not at production relevance (the ~150-rule scale trigger has not fired: 2 rules / 3 fixtures).

Store API + SPARQL 1.1 only (rdflib ==7.6.0; Oxigraph is a one-line backend swap; Neo4j rejected
GPL-3.0 — baseline §1 decision 4). Requirement VALUES stay in `Thresholds.resolve`; monostanza
stays OUT of the graph (its constants are not gate-checked — ADR-005 (ii) — so promoting them to
graph "facts" would launder an unverified transcription).
"""
from __future__ import annotations

import json
import os
from typing import Optional

from rdflib import Graph, Literal, Namespace, RDF, RDFS

import parser as _parser  # statute gate for the 4 art1 tokens; NO `import checker` (see module doc)

ACC = Namespace("https://acc.local/ontology#")

_HERE = os.path.dirname(os.path.abspath(__file__))
_APPLICABILITY_PATH = os.path.join(_HERE, "rules", "applicability.json")
_LAW_PATH = os.path.join(_HERE, "rules", "dm_1975_salva_casa.md")

# The single synthetic divergence room-type. Its token is machine-proven a NON-SUBSTRING of every
# one of the 51 hints (test_graph acceptance 2a), so a faithful flat lookup genuinely returns
# 'unknown' for it; the graph reaches 'accessory' ONLY via the rdfs:subClassOf+ edge, proving the
# transitive inference is load-bearing (remove the edge -> 'unknown'). 'anticamera' would be
# REJECTED here (contains the habitable hint 'camera'); 'vestibolo' is clean.
_DIVERGENCE_LABEL = "vestibolo"
DIVERGENCE_NODE = ACC["Vestibolo"]
_DIVERGENCE_PARENT = ACC["Disimpegno"]  # a statute-anchored Art.1 accessory room-type

_CLASS_URI = {"accessory": ACC.Accessory, "habitable": ACC.Habitable}

# Single SPARQL 1.1 SELECT. A class matches if (a) one of its :hintText literals is CONTAINS-in the
# lower-cased "<name> <longName>" label, OR (b) a room-type node carrying a CONTAINS-matching
# :typeLabel reaches the class via rdfs:subClassOf+ (the transitive-inference path). Accessory-first
# precedence + strict 'unknown' complement live IN the query: priority BIND (accessory 0 < habitable
# 1) + ORDER BY + LIMIT 1; no row -> the caller returns 'unknown'. The label is injected via
# initBindings (never interpolated) so a GlobalId/name with SPARQL-illegal characters is safe.
_OCCUPANCY_QUERY = """
PREFIX acc: <https://acc.local/ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?cls (IF(?cls = acc:Accessory, 0, 1) AS ?prio) WHERE {
  {
    ?h acc:hintText ?ht ; acc:broaderTerm ?cls .
    FILTER(CONTAINS(?label, LCASE(STR(?ht))))
  }
  UNION
  {
    ?rt acc:typeLabel ?tl ; rdfs:subClassOf+ ?cls .
    FILTER(?cls IN (acc:Accessory, acc:Habitable))
    FILTER(CONTAINS(?label, LCASE(STR(?tl))))
  }
}
ORDER BY ?prio
LIMIT 1
"""

_ONTOLOGY_CACHE: "Optional[Graph]" = None


def build_ontology(applicability_path: "Optional[str]" = None,
                   law_path: "Optional[str]" = None,
                   *, _inject_fabricated_art1: "Optional[str]" = None) -> Graph:
    """Build the occupancy ontology from `applicability.json`, gate-anchoring the 4 Art.1 tokens.

    Seed (stdlib json, NOT `import checker`): every hint -> a `:hintText` node `:broaderTerm` its
    class, tagged `:provenance`. The 4 `art1`-provenance tokens are cross-checked against the
    DM-1975 Art.1 prose via `parser.verify_accessory_selection_against_text` (a FABRICATED token
    RAISES — fail-closed, NO-INVENT) and marked `:statuteAnchored true`; every `cross-lingual-
    glossary` edge is `:declaredDebt true` and NEVER `:statuteAnchored` (baseline §7). A small
    `rdfs:subClassOf` taxonomy gives the statute-anchored room-type `:Disimpegno ⊑ acc:Accessory`
    plus the synthetic divergence sub-type `:Vestibolo ⊑ :Disimpegno`.

    Fail-closed: a missing seed file raises (open); a fabricated art1 token raises (the gate); an
    empty result (no `:hintText`) raises — the ontology is never returned vacuous.
    """
    applicability_path = applicability_path or _APPLICABILITY_PATH
    law_path = law_path or _LAW_PATH

    with open(applicability_path, encoding="utf-8") as fh:   # FileNotFoundError -> fail-closed
        data = json.load(fh)
    classes_raw = data["occupancy_classes"]

    art1_tokens: list = []
    debt_tokens: list = []
    hint_specs: list = []  # (hintText, class_uri, provenance)
    for cls_name in ("accessory", "habitable"):
        for grp in classes_raw[cls_name]["hint_groups"]:
            prov = grp.get("provenance")
            for h in grp.get("hints", []):
                hint_specs.append((h, _CLASS_URI[cls_name], prov))
                (art1_tokens if prov == "art1" else debt_tokens).append(h)

    if _inject_fabricated_art1 is not None:                  # over-claim guard (test): must RAISE
        art1_tokens = art1_tokens + [_inject_fabricated_art1]

    # STATUTE GATE — verify, never trust: bind the art1 tokens to the Art.1 prose enumeration; a
    # fabricated/unanchored token RAISES ValidationGateError. Cross-lingual tokens are recorded as
    # declared, unanchored debt — never statute-checked, never reported anchored.
    with open(law_path, encoding="utf-8") as fh:
        law_text = fh.read()
    verdict = _parser.verify_accessory_selection_against_text(
        art1_tokens, law_text, debt_tokens=debt_tokens)
    anchored = set(verdict["anchored"])                      # the 4 art1 tokens that anchored

    g = Graph()
    g.bind("acc", ACC)
    g.bind("rdfs", RDFS)
    for cls in (ACC.Accessory, ACC.Habitable):
        g.add((cls, RDF.type, RDFS.Class))

    for i, (ht, curi, prov) in enumerate(hint_specs):
        hn = ACC[f"hint_{i}"]
        g.add((hn, RDF.type, ACC.Hint))
        g.add((hn, ACC.hintText, Literal(ht)))
        g.add((hn, ACC.broaderTerm, curi))
        g.add((hn, ACC.provenance, Literal(prov)))
        if prov == "art1":
            # statute-anchored ONLY for tokens the gate actually bound (it raised otherwise above).
            if ht in anchored:
                g.add((hn, ACC.statuteAnchored, Literal(True)))
        else:
            g.add((hn, ACC.declaredDebt, Literal(True)))

    # rdfs:subClassOf taxonomy. Terminal parent is the statute-anchored Art.1 class. The divergence
    # sub-type carries a :typeLabel (the taxonomy match path) and reaches acc:Accessory ONLY through
    # the subClassOf+ chain — :Disimpegno deliberately has no :typeLabel, so no real fixture label
    # touches this path (keeps the 220-row equivalence intact; the divergence is synthetic).
    g.add((_DIVERGENCE_PARENT, RDFS.subClassOf, ACC.Accessory))
    g.add((DIVERGENCE_NODE, RDFS.subClassOf, _DIVERGENCE_PARENT))
    g.add((DIVERGENCE_NODE, ACC.typeLabel, Literal(_DIVERGENCE_LABEL)))

    if not _has_ontology(g):                                 # never return a vacuous ontology
        raise RuntimeError("graph.build_ontology: empty ontology (no :hintText) — fail-closed")
    return g


def _has_ontology(g: Graph) -> bool:
    """A usable ontology must carry at least one :hintText edge."""
    return next(iter(g.triples((None, ACC.hintText, None))), None) is not None


def _ontology() -> Graph:
    """Lazily build + cache the ontology. Lazy (not import-time) and `run()`-independent: mirrors
    `checker._applicability()` so `classify()`/`occupancy_via_graph` work standalone (the kept
    `test_applicability_table` calls them outside any `run()`)."""
    global _ONTOLOGY_CACHE
    if _ONTOLOGY_CACHE is None:
        _ONTOLOGY_CACHE = build_ontology()
    return _ONTOLOGY_CACHE


def occupancy_via_graph(name, long_name, graph: "Optional[Graph]" = None) -> str:
    """Answer room -> {'accessory'|'habitable'|'unknown'} via a SPARQL query over the ontology.

    Two distinct fail-closed outcomes (assert both, baseline / HARD RULES):
      - a no-match label -> 'unknown' (the strict complement of accessory ∪ habitable);
      - an EMPTY / FAILED ontology -> RAISE (never a silent 'unknown' — that would mask a broken
        graph as a benign no-match).
    """
    g = graph if graph is not None else _ontology()
    if not _has_ontology(g):
        raise RuntimeError(
            "occupancy_via_graph: empty/failed ontology — fail-closed (RAISE, not 'unknown')")
    label = " ".join(str(x or "") for x in (name, long_name)).lower()
    rows = list(g.query(_OCCUPANCY_QUERY, initBindings={"label": Literal(label)}))
    if not rows:
        return "unknown"
    cls = rows[0][0]
    if cls == ACC.Accessory:
        return "accessory"
    if cls == ACC.Habitable:
        return "habitable"
    return "unknown"
