#!/usr/bin/env python3
"""Stage 5b — the Rule Orchestrator (ADR-009): rule loading + SHACL validation + report parsing.

Decoupled architecture:
  checker.py       = the FEATURE EXTRACTOR — IfcOpenShell parsing, the P0-guarded measurements
                     (positivity, unit resolvability, trustworthy-window trust), and the per-space
                     A-Box materialization (projection of extracted facts into acc: triples).
  orchestrator.py  = the RULES side — loads + fail-closed-validates + thr-parameterizes the SHACL
                     shapes (the regulatory .ttl is passed DYNAMICALLY), fires pyshacl, and parses
                     the ValidationReport with a DETERMINISTIC SPARQL query (sh:focusNode /
                     sh:resultPath / sh:sourceConstraintComponent / sh:resultMessage / sh:value —
                     no string hacking), then maps rows to the tri-valued verdicts.

This module never imports ifcopenshell — it is IFC-agnostic and import-safe on a machine without
the wheel; `import checker` happens lazily inside ComplianceOrchestrator.run() (which also keeps
the checker->orchestrator import one-directional at module-load time: no cycle).

Fail-closed contract (ADR-008/008a, unchanged by this refactor):
  * load_shacl_shapes RAISES on: a missing/unparseable .ttl; a shapes graph not targeting all
    three materialization classes (an untargeted class would conform VACUOUSLY — a silent pass);
    a missing sh:minInclusive slot; a missing sh:minCount >= 1 (THE construct that turns an absent
    measurement into UNDETERMINED — without it the no-result->PASS default fails OPEN).
  * verdicts_from_report RAISES on any unexpected result path or constraint component.
  * Ternary mapping (MinCount-dominant, blueprint §3.5): MinCount -> None (UNDETERMINED);
    MinInclusive -> False (VIOLATION), remapped to None for an UNBOUNDED aero ratio (C-1b L-2);
    no result -> True (PASS).
"""
from __future__ import annotations

import argparse
import os
import time
from decimal import Decimal
from typing import Optional

from rdflib import Graph, Literal, Namespace
from rdflib.namespace import XSD
from rdflib.plugins.sparql import prepareQuery

import graph as _accgraph  # the acc: namespace; import-safe (pure rdflib, no ifcopenshell)

SH = Namespace("http://www.w3.org/ns/shacl#")
LEGAL = Namespace("https://acc.local/legal#")

DEFAULT_SHACL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "ontology", "dm1975_salvacasa.ttl")
_SHAPES_CACHE: dict = {}     # (abs .ttl path, 4 threshold floats) -> parameterized shapes Graph

# The four stable property-shape URIs re-parameterized from Thresholds — the gate-verified
# compiled JSON stays the numeric source of truth (Stage-1 dynamic coupling); the sh:message is
# regenerated WITH the value so an overridden bar never reports a stale number (ADR-008).
_THRESHOLD_SLOTS = (
    ("MinHeightHabitable_PS", "min_height_habitable_m",
     "height below the {v} m habitable minimum (DM 1975 art.1)"),
    ("MinHeightAccessory_PS", "min_height_accessory_m",
     "height below the {v} m accessory minimum (DM 1975 art.1)"),
    ("MinHeightSalvaCasa_PS", "min_height_salva_casa_m",
     "height below the {v} m Salva-Casa derogated minimum (DPR 380/2001 art.24 c.5-bis)"),
    ("MinAeroRatio_PS", "aero_illuminating_ratio",
     "aero-illuminating ratio below the {v} (1/8) floor-area minimum (DM 1975 art.5)"),
)
TARGET_CLASSES = ("AccessorySpace", "HabitableBaselineSpace", "HabitableSalvaCasaSpace")

# --- ADR-017: the measurement paths the engine's extractor ADVERTISES (rules-side registry) ----
# Keys are the canonical acc: measurement paths a rule pack may bind with sh:path; the extractor
# side is checker.MEASUREMENT_EXTRACTORS (checker imports orchestrator, never the reverse — the
# two key sets are pinned equal in tests/test_aero_extraction.py). load_shacl_shapes REFUSES a
# pack binding any other path: the engine could never supply that measurement, so every space
# would read UNDETERMINED through sh:minCount while the pack looked loaded — and a typo'd path
# (acc:areoRatio) would silently drop a legal check. Surface both at load time instead.
SUPPORTED_MEASUREMENT_PATHS = {
    _accgraph.ACC.heightM: "net room height (m) — Qto multi-key extraction",
    _accgraph.ACC.aeroRatio: "openable-window area / net floor area — IfcRelSpaceBoundary "
                             "traversal + conservative min(attr, Qto) / boundary-geometry bound",
}


def load_shacl_shapes(thr, path: Optional[str] = None) -> Graph:
    """Load + validate + parameterize the SHACL shapes graph. FAIL-CLOSED (mirrors
    checker.load_applicability): every guard below exists because its absence was a proven silent
    failure mode — see the module docstring and ADR-008/008a."""
    path = path or DEFAULT_SHACL_PATH
    g = Graph()
    # Explicit context manager (freeze-review V3): rdflib manages the handle internally when given a
    # path, but an explicit with-open guarantees deterministic release during batch execution.
    with open(path, "rb") as fh:                 # FileNotFoundError -> fail-closed
        g.parse(fh, format="turtle")             # parse error -> fail-closed
    targeted = set(g.objects(None, SH.targetClass))
    expected = {_accgraph.ACC[c] for c in TARGET_CLASSES}
    if not expected <= targeted:
        raise ValueError(f"SHACL shapes {path!r}: missing sh:targetClass for "
                         f"{sorted(str(c) for c in expected - targeted)} — a space materialized "
                         f"under an untargeted class would conform vacuously (fail-closed)")
    # ADR-017: every sh:path the pack binds must be a measurement the extractor advertises.
    bound_paths = set(g.objects(None, SH.path))
    unsupported = bound_paths - set(SUPPORTED_MEASUREMENT_PATHS)
    if unsupported:
        raise ValueError(f"SHACL shapes {path!r}: sh:path binds unsupported measurement(s) "
                         f"{sorted(str(p) for p in unsupported)} — not in the extractor's "
                         f"measurement registry (SUPPORTED_MEASUREMENT_PATHS); the engine cannot "
                         f"supply them, refusing (fail-closed, ADR-017)")
    # SPARQL-based constraints carry no sh:path, so they evade the registry guard above AND the
    # runtime's path-routed verdict mapping (verdicts_from_report would crash on the unrouted
    # result) — refuse them classified at load (red-team round 6).
    if next(g.triples((None, SH.sparql, None)), None) is not None:
        raise ValueError(f"SHACL shapes {path!r}: sh:sparql constraint present — SPARQL-based "
                         f"constraints carry no sh:path and cannot be routed to a verdict slot; "
                         f"refusing (fail-closed, ADR-017)")
    for ps_name, thr_attr, msg_tmpl in _THRESHOLD_SLOTS:
        ps = LEGAL[ps_name]
        if g.value(ps, SH.minInclusive) is None:
            raise ValueError(f"SHACL shapes {path!r}: {ps_name} has no sh:minInclusive slot "
                             f"(fail-closed — refusing an unparameterized legal bar)")
        # sh:minCount is THE load-bearing fail-closed construct: it alone turns an ABSENT
        # measurement into UNDETERMINED (the post-pass maps no-result -> PASS). A shapes file
        # without it silently demotes undetermined -> pass (ADR-008a) — refuse it.
        mc = g.value(ps, SH.minCount)
        if mc is None or int(mc) < 1:
            raise ValueError(f"SHACL shapes {path!r}: {ps_name} has no sh:minCount >= 1 — the "
                             f"fail-closed UNDETERMINED construct is missing (an absent measurement "
                             f"would read as PASS); refusing (fail-closed)")
        val = getattr(thr, thr_attr)             # resolves via the record model; raises if absent
        raw_bar = g.value(ps, SH.minInclusive)   # the pack's own emitted bar, pre-overwrite
        g.set((ps, SH.minInclusive, Literal(Decimal(str(val)), datatype=XSD.decimal)))
        # ADR-017: when the pack's raw bar ALREADY equals the live threshold, keep the pack's own
        # sh:message — a regional pack (e.g. an emitted Lombardia mock, ADR-016) must not have its
        # provenance text rewritten into the DM-1975 template (the ADR-008 wrong-message class:
        # a violation note citing the wrong statute). Only a genuinely re-parameterized bar
        # (edited-law recompile) regenerates the message, value included, so a stale number can
        # still never be reported. Preservation is STRUCTURALLY guarded (red-team round 6):
        # exactly ONE message triple (multiple would ALL survive into report rows — g.set never
        # fires on the keep path) and a control-character-free plain literal; anything else
        # regenerates deterministically. Message CONTENT stays pack-authored — packs are CODE
        # under the ADR-016 trust model (in-repo, reviewed, emitter-verified); see ADR-017's
        # honesty boundary.
        raw_msgs = list(g.objects(ps, SH.message))
        try:
            keep_raw_msg = (len(raw_msgs) == 1 and _message_literal_ok(raw_msgs[0])
                            and Decimal(str(raw_bar)) == Decimal(str(val)))
        except Exception:                        # non-numeric raw bar -> regenerate (as before)
            keep_raw_msg = False
        if not keep_raw_msg:
            g.set((ps, SH.message, Literal(msg_tmpl.format(v=val))))
    return g


def _message_literal_ok(m) -> bool:
    """A pack sh:message the loader may PRESERVE must be a non-empty, quote/backslash/control-
    character-free string of sane length (gate_spike's _safe_literal envelope, mirrored here
    without importing the spike)."""
    s = str(m)
    return 0 < len(s) <= 300 and '"' not in s and "\\" not in s \
        and not any(ord(c) < 32 for c in s)


def required_measurement_paths(thr, ttl_path: Optional[str] = None) -> frozenset:
    """The acc: measurement paths the (cached, validated) shapes graph actually binds via
    sh:path — how a caller identifies WHAT a target legal specification requires the extractor
    to measure (e.g. whether acc:aeroRatio / window data is needed at all). Loading has already
    refused any path outside SUPPORTED_MEASUREMENT_PATHS (ADR-017)."""
    return frozenset(shapes_for(thr, ttl_path).objects(None, SH.path))


def shapes_for(thr, path: Optional[str] = None) -> Graph:
    """Cached, parameterized shapes. The key includes the RESOLVED .ttl path (the regulatory file
    is dynamic) AND the four threshold values (two rule-sets must never share shapes)."""
    p = os.path.abspath(path or DEFAULT_SHACL_PATH)
    key = (p, thr.min_height_habitable_m, thr.min_height_accessory_m,
           thr.min_height_salva_casa_m, thr.aero_illuminating_ratio)
    if key not in _SHAPES_CACHE:
        _SHAPES_CACHE[key] = load_shacl_shapes(thr, path=p)
    return _SHAPES_CACHE[key]


def validate_abox(data_graph: Graph, thr, ttl_path: Optional[str] = None,
                  timer: Optional[PhaseTimer] = None):
    """Fire pyshacl over the A-Box against the (cached) parameterized shapes.
    Returns ``(conforms, report_graph)``. Any pyshacl error propagates (fail-closed)."""
    import pyshacl                               # heavy import, deferred; cached in sys.modules
    shapes = shapes_for(thr, ttl_path)
    t0 = time.perf_counter()
    conforms, report, _ = pyshacl.validate(data_graph, shacl_graph=shapes)
    if timer is not None:
        timer.add("shacl_validation_s", time.perf_counter() - t0)
    return conforms, report


# STEP-3 deterministic report extraction: one prepared SPARQL query pulls every ValidationResult's
# focus node, path, constraint component, message, and offending value straight from the report
# graph — no per-triple .value() walking, no string parsing of the text report.
_REPORT_QUERY = prepareQuery("""
    PREFIX sh: <http://www.w3.org/ns/shacl#>
    SELECT ?focus ?path ?component ?message ?value WHERE {
        ?r a sh:ValidationResult ;
           sh:focusNode ?focus ;
           sh:sourceConstraintComponent ?component .
        OPTIONAL { ?r sh:resultPath ?path }
        OPTIONAL { ?r sh:resultMessage ?message }
        OPTIONAL { ?r sh:value ?value }
    }""")


def parse_report(report: Graph) -> list:
    """SPARQL-extract the ValidationReport into deterministic, sorted rows:
    ``{focus, path, component, message, value}`` (rdflib terms; message/value may be None)."""
    rows = [{"focus": b["focus"], "path": b["path"], "component": b["component"],
             "message": b["message"], "value": b["value"]}
            for b in report.query(_REPORT_QUERY)]
    rows.sort(key=lambda r: (str(r["path"]), str(r["component"]), str(r["message"] or "")))
    return rows


def verdicts_from_report(rows: list, occ: str, aero_unbounded: bool):
    """Map parsed report rows to the tri-valued ``(height_ok, aero_ok, violation_messages)``.

    MinCount-dominant ternary (blueprint §3.5): MinCount -> None; MinInclusive -> False (for aero,
    None when the ratio was UNBOUNDED — the conservative lower bound proves a pass, never a
    violation, C-1b L-2); no result -> True. Unexpected paths/components RAISE (fail-closed)."""
    comps = {"height": [], "aero": []}
    msgs = {"height": [], "aero": []}
    for r in rows:
        if r["path"] == _accgraph.ACC.heightM:
            slot = "height"
        elif r["path"] == _accgraph.ACC.aeroRatio:
            slot = "aero"
        else:                                    # an unmodeled result = a shapes/materializer bug
            raise RuntimeError(f"unexpected SHACL result path {r['path']!r} (fail-closed)")
        comps[slot].append(r["component"])
        if r["message"] is not None and r["component"] == SH.MinInclusiveConstraintComponent:
            msgs[slot].append(str(r["message"]))

    def _tri(comp_list, unbounded=False):
        if not comp_list:
            return True
        if SH.MinCountConstraintComponent in comp_list:
            return None                          # measurement absent -> UNDETERMINED
        if all(c == SH.MinInclusiveConstraintComponent for c in comp_list):
            return None if unbounded else False
        raise RuntimeError(f"unexpected SHACL constraint components {comp_list} (fail-closed)")

    height_ok = _tri(comps["height"])
    aero_ok = None if occ == "accessory" else _tri(comps["aero"], unbounded=aero_unbounded)
    messages = (msgs["height"] if height_ok is False else []) + \
               (msgs["aero"] if aero_ok is False else [])
    return height_ok, aero_ok, messages


class PhaseTimer:
    """Accumulating phase timer for the STEP-4 benchmark (seconds, monotonic clock)."""

    def __init__(self):
        self.phases: dict = {}

    def add(self, phase: str, seconds: float) -> None:
        self.phases[phase] = self.phases.get(phase, 0.0) + seconds

    def as_dict(self) -> dict:
        return {k: round(v, 4) for k, v in sorted(self.phases.items())}


class ComplianceOrchestrator:
    """End-to-end run: a target ``.ifc`` + a target regulatory ``.ttl`` (dynamic) -> the standard
    checker report + a ``timings`` block (ifc_extraction_s / graph_construction_s /
    shacl_validation_s). Extraction + materialization are delegated to checker.py (the feature
    extractor); this class owns rule selection and the benchmark."""

    def __init__(self, ifc_path: str, ttl_path: Optional[str] = None,
                 salva_casa: bool = False, thr=None):
        self.ifc_path = ifc_path
        self.ttl_path = ttl_path
        self.salva_casa = salva_casa
        self.thr = thr

    def run(self) -> dict:
        import checker                           # lazy: ifcopenshell only needed at run time
        timer = PhaseTimer()
        report = checker.run(self.ifc_path, self.salva_casa, self.thr,
                             ttl_path=self.ttl_path, timer=timer)
        report["timings"] = timer.as_dict()
        return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Rule Orchestrator — SHACL compliance run with a timing breakdown")
    ap.add_argument("ifc", help="path to the .ifc model")
    ap.add_argument("--ttl", metavar="FILE", default=None,
                    help="regulatory SHACL shapes .ttl (default: ontology/dm1975_salvacasa.ttl)")
    ap.add_argument("--salva-casa", action="store_true")
    args = ap.parse_args(argv)
    rep = ComplianceOrchestrator(args.ifc, ttl_path=args.ttl, salva_casa=args.salva_casa).run()
    print(f"{rep['schema']} | {rep['spaces_evaluated']} IfcSpace | {rep['violations']} violation(s) "
          f"| {rep['spaces_undetermined']} undetermined | salva_casa={rep['salva_casa']}")
    print("timing breakdown (s):")
    for k, v in rep["timings"].items():
        print(f"  {k:24s} {v:8.4f}")
    return 1 if (rep["violations"] or rep["spaces_undetermined"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
