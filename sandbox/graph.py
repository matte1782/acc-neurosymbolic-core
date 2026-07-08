#!/usr/bin/env python3
"""Stage 4b — graph layer for occupancy/applicability discovery.

The room->occupancy decision is answered by the **match table materialized from a SPARQL-1.1-
specified query over an rdflib in-memory ontology** (`occupancy_via_graph`; the live per-token
SPARQL path remains runtime-selectable via ACC_GRAPH_CLASSIFIER=sparql — QW-1/ADR-015), the seam
that replaces `checker.classify()`'s Python substring branch in Task 2. This module is the read-only graph layer (Task 1): it builds + caches the
ontology and answers the query; it does NOT import `checker` (one-directional dependency:
`checker -> graph`, never back — and `checker`'s module-top `import ifcopenshell` sys.exits when the
wheel is absent, checker.py:27-37, so the neuro/graph layer must stay independent).

HONESTY CONTRACT (baseline §1 / §6 / §7; ADR-006). On the 3 current fixtures **every room is
flat-substring-decidable**, so a graph seeded from the same hints is **verdict-equivalent to the
flat table BY CONSTRUCTION** — reproducing the controls proves a *faithful copy of classify()*, NOT
correctness. What this layer actually delivers, and all it claims, is exactly three things:
  1. the architectural seam (room->occupancy via a SPARQL-SPECIFIED query over a store; since
     QW-1/ADR-015 the default runtime path is the table materialized from that query, with the
     live engine path selectable and differentially pinned equivalent);
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
import re
import weakref
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

# Per-TOKEN SPARQL 1.1 SELECT (M-4 fix). occupancy_via_graph tokenises the label and asks the graph
# for EACH token's class; this query returns ONE token's class. A class matches a token if (a) one of
# its :hintText literals is a PREFIX of the token (STRSTARTS), OR (b) a room-type node whose
# :typeLabel is a prefix of the token reaches the class via rdfs:subClassOf+ (the transitive-
# inference path). PREFIX (head-stem), not CONTAINS: it still resolves agglutinative compounds (token
# 'wohnzimmer' starts with 'wohn'; 'badezimmer' with 'bad') while rejecting the internal fragments
# CONTAINS admitted ('messeraum' does NOT start with 'ess'); cross-word collisions are handled by
# tokenisation + the caller's aggregation. Accessory-first WITHIN a token: priority BIND (accessory
# 0 < habitable 1) + ORDER BY + LIMIT 1. Branch (a) FILTERs ?cls to the two known classes
# (ADR-015): without it a hypothetical third broaderTerm class would enter as a prio-1 row and
# could SHADOW a co-matching habitable row under the spec-UNDEFINED ORDER BY tie + LIMIT 1 —
# unreachable from build_ontology (only Accessory/Habitable are ever asserted), but the reference
# query must be well-defined for the table-equivalence contract below. The token is injected via
# initBindings (never interpolated) so a name with SPARQL-illegal characters is safe.
_TOKEN_QUERY = """
PREFIX acc: <https://acc.local/ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?cls (IF(?cls = acc:Accessory, 0, 1) AS ?prio) WHERE {
  {
    ?h acc:hintText ?ht ; acc:broaderTerm ?cls .
    FILTER(?cls IN (acc:Accessory, acc:Habitable))
    FILTER(STRSTARTS(?tok, LCASE(STR(?ht))))
  }
  UNION
  {
    ?rt acc:typeLabel ?tl ; rdfs:subClassOf+ ?cls .
    FILTER(?cls IN (acc:Accessory, acc:Habitable))
    FILTER(STRSTARTS(?tok, LCASE(STR(?tl))))
  }
}
ORDER BY ?prio
LIMIT 1
"""

# Token boundary: split the lowercased label on any run of NON-letters (whitespace, digits, '-', '/',
# punctuation), keeping unicode Latin letters incl. accents/umlauts ('à-ÿ' covers ü/ä/ö/è/à/…).
_TOKEN_SPLIT = re.compile(r"[^a-zà-ÿ]+")

_ONTOLOGY_CACHE: "Optional[Graph]" = None

# =========================================================================================
# QW-1 / Phase A-1 (ADR-015): _TOKEN_QUERY above remains the SEMANTIC SPEC, but firing the
# rdflib SPARQL engine once per token per space measured 3.86 s of Institute's wall time
# (70-77%, STRATEGIC_MOAT_ANALYSIS §3.1.2). Pair-level (Name, LongName) memoization is
# measured-dead (Institute's 82 pairs are ALL distinct — §3.1.7 QW-1), so the sanctioned
# lever is a ONE-TIME materialization of the query's match table from the (static per
# run) ontology — prefix lists per class plus the typeLabel/subClassOf+ closure — then
# per-token Python prefix matching with a token-level memo. Verdict-equivalence is by
# construction (the derivation mirrors the two UNION branches; accessory-priority
# `ORDER BY ?prio LIMIT 1` maps to check-accessory-first) and is differentially asserted
# against the live SPARQL path (ADR-015 evidence: tests/test_graph.py differential pin +
# the fuzz record in the ADR; set ACC_GRAPH_CLASSIFIER=sparql to force the legacy engine
# path at runtime). The derived table is cached per graph OBJECT IDENTITY (id() +
# weakref.finalize eviction — NOT rdflib Graph equality, which compares only the graph
# IDENTIFIER and would alias two same-identifier graphs) and guarded by a FINGERPRINT of
# the classification-relevant triples (hintText/broaderTerm/typeLabel/subClassOf,
# order-independent XOR of triple hashes), so ANY in-place mutation of those triples —
# including an equal-count remove+add swap, which a bare len() guard provably misses —
# invalidates it. The fingerprint pass is ~100 triple lookups per call: noise next to
# the ~47 ms/space SPARQL cost it replaces.
# =========================================================================================
_DERIVED_CACHE: dict = {}          # id(graph) -> (fingerprint, table, token_memo)
_RELEVANT_PREDICATES = (ACC.hintText, ACC.broaderTerm, ACC.typeLabel, RDFS.subClassOf)


def _table_fingerprint(g: Graph) -> int:
    """Order-independent fingerprint of the classification-relevant triples."""
    acc = 0
    for pred in _RELEVANT_PREDICATES:
        for t in g.triples((None, pred, None)):
            acc ^= hash(t)
    return acc


def _derive_match_table(g: Graph) -> tuple:
    """Materialize _TOKEN_QUERY's match table: (accessory_prefixes, habitable_prefixes).

    Branch (a): every ``:hintText`` whose ``:broaderTerm`` is acc:Accessory/acc:Habitable —
    any OTHER broaderTerm class is excluded, matching the query's branch-(a) FILTER (added
    with this table: pre-FILTER, an other-class row could shadow a co-matching habitable
    row under the spec-undefined ORDER BY tie; no such class exists in build_ontology's
    output — graph.py's _CLASS_URI is the whole codomain). Branch (b): every
    ``:typeLabel`` whose node reaches acc:Accessory/acc:Habitable via ``rdfs:subClassOf+``
    (transitive closure walked iteratively). Prefixes are lowercased ONCE here — the query
    applies LCASE per evaluation; both equal ``str.lower()`` on this charset."""
    acc_p, hab_p = [], []
    for hn, _, ht in g.triples((None, ACC.hintText, None)):
        for _, _, cls in g.triples((hn, ACC.broaderTerm, None)):
            if cls == ACC.Accessory:
                acc_p.append(str(ht).lower())
            elif cls == ACC.Habitable:
                hab_p.append(str(ht).lower())
    for rt, _, tl in g.triples((None, ACC.typeLabel, None)):
        seen, stack = set(), [rt]
        while stack:
            node = stack.pop()
            for _, _, parent in g.triples((node, RDFS.subClassOf, None)):
                if parent not in seen:
                    seen.add(parent)
                    stack.append(parent)
        if ACC.Accessory in seen:
            acc_p.append(str(tl).lower())
        if ACC.Habitable in seen:
            hab_p.append(str(tl).lower())
    return tuple(acc_p), tuple(hab_p)


def _match_table(g: Graph) -> tuple:
    """Per-graph-identity cached ``(table, token_memo)``, invalidated whenever the
    fingerprint of the classification-relevant triples changes."""
    key = id(g)
    fp = _table_fingerprint(g)
    ent = _DERIVED_CACHE.get(key)
    if ent is None or ent[0] != fp:
        if ent is None:            # first entry for this identity: evict when g is GC'd
            weakref.finalize(g, _DERIVED_CACHE.pop, key, None)
        ent = (fp, _derive_match_table(g), {})
        _DERIVED_CACHE[key] = ent
    return ent[1], ent[2]


def _classify_token_table(tok: str, table: tuple) -> "Optional[str]":
    acc_p, hab_p = table
    if any(tok.startswith(p) for p in acc_p):    # accessory priority == ORDER BY ?prio LIMIT 1
        return "accessory"
    if any(tok.startswith(p) for p in hab_p):
        return "habitable"
    return None


def _classify_token_sparql(g: Graph, tok: str) -> "Optional[str]":
    """The legacy per-token SPARQL path — kept as the REFERENCE implementation for
    differential verification (and forced via ACC_GRAPH_CLASSIFIER=sparql)."""
    rows = list(g.query(_TOKEN_QUERY, initBindings={"tok": Literal(tok)}))
    if not rows:
        return None
    cls = rows[0][0]
    if cls == ACC.Accessory:
        return "accessory"
    if cls == ACC.Habitable:
        return "habitable"
    return None


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
    """Answer room -> {'accessory'|'habitable'|'unknown'} by per-token classification against the
    match table materialized from _TOKEN_QUERY's semantics (one-time per graph, token-memoized;
    QW-1/ADR-015). ACC_GRAPH_CLASSIFIER=sparql forces the per-token SPARQL reference path.

    M-4 fix (code audit). The old whole-label CONTAINS misclassified mixed/compound names: e.g.
    'Soggiorno con bagno' (a habitable living room) classified 'accessory' merely because the string
    contained 'bagno' (relaxing it to the 2.40 m bar AND skipping the 1/8 aero check), and
    'Messeraum' classified 'habitable' via the internal 'ess' fragment. Now the label is TOKENISED
    (whitespace/punct/digit boundaries) and each token is classified independently by a head-stem
    PREFIX match (so agglutinative compounds like 'Wohnzimmer'->'wohn' still resolve while internal
    fragments do not), then aggregated:
      - no token classified                                   -> 'unknown'
      - only accessory token(s)                               -> 'accessory'
      - any habitable token (incl. a MIXED accessory+habitable phrase) -> 'habitable'
    Rationale (DM-1975 Art.1): an accessory room is named by a SINGLE enumerated term (bagno,
    ripostiglio, corridoio, disimpegno); a habitable room may carry an accessory qualifier
    ('... con bagno'), so a mixed phrase is habitable. 'unknown' is the strict complement and is
    evaluated like habitable (stricter 2.70 m bar + aero) -> the safe, fail-closed direction.
    Verdict-neutral on the 3 fixtures: 0/110 spaces reclassified (controls + the 220-/110-row
    equivalence oracles hold); only previously-misclassified mixed/fragment names move.

    Two distinct fail-closed outcomes (assert both, baseline / HARD RULES):
      - a no-match label -> 'unknown' (never a silent pass — 'unknown' takes the habitable bar+aero);
      - an EMPTY / FAILED ontology -> RAISE (never a silent 'unknown' masking a broken graph).
    """
    g = graph if graph is not None else _ontology()
    if not _has_ontology(g):
        raise RuntimeError(
            "occupancy_via_graph: empty/failed ontology — fail-closed (RAISE, not 'unknown')")
    # QW-1/ADR-015: tokens are classified against the materialized match table (one-time
    # per graph, token-memoized) instead of one SPARQL engine invocation per token; the
    # query above stays the semantic spec and the runtime-selectable reference path.
    use_sparql = os.environ.get("ACC_GRAPH_CLASSIFIER") == "sparql"
    if not use_sparql:
        table, memo = _match_table(g)
    label = " ".join(str(x or "") for x in (name, long_name)).lower()
    classes = set()
    for tok in _TOKEN_SPLIT.split(label):
        if not tok:
            continue
        if use_sparql:
            cls = _classify_token_sparql(g, tok)
        elif tok in memo:
            cls = memo[tok]
        else:
            cls = _classify_token_table(tok, table)
            memo[tok] = cls
        if cls is not None:
            classes.add(cls)
    if not classes:
        return "unknown"
    if classes == {"accessory"}:
        return "accessory"
    return "habitable"   # habitable-only OR mixed accessory+habitable -> habitable (see docstring)
