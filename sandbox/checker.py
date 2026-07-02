#!/usr/bin/env python3
"""Deterministic compliance checker — Slice A: Italian habitability (DM 5/7/1975 + Salva Casa).

This is the *symbolic* / zero-hallucination half of the neuro-symbolic bridge. It reads
geometry and quantities straight from an IFC model with IfcOpenShell and evaluates the rule
with plain Python arithmetic — no LLM, fully reproducible.

Rule under test (see rules/dm_1975_salva_casa.md):
    R1   habitable room net height        >= 2.70 m   (accessory rooms >= 2.40 m)
    R1'  Salva Casa exception (existing building, recupero, asseverazione) -> 2.40 m
    R2   rapporto aeroilluminante: openable window area >= 1/8 of room floor area

Usage:
    python checker.py model.ifc                  # baseline DM 1975
    python checker.py model.ifc --salva-casa     # apply the 2.40 m conditional exception
    python checker.py model.ifc --json out.json  # also write the full report
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import asdict, dataclass, field
from typing import List, Optional

try:
    import ifcopenshell
    import ifcopenshell.util.element as ue
    import ifcopenshell.util.unit as uu
except ImportError as exc:  # pragma: no cover - environment guard
    sys.exit(
        "IfcOpenShell is required for the deterministic checker.\n"
        "  pip install ifcopenshell   (needs a wheel for your Python version; if none is\n"
        "  available, use conda-forge `ifcopenshell` or a Python 3.11/3.12 venv)\n"
        f"  import error: {exc}"
    )

# Stage 4b — the room->occupancy decision flows from a SPARQL query over an rdflib ontology
# (graph.occupancy_via_graph), which REPLACES classify()'s substring branch below. graph.py seeds
# its ontology from the SAME rules/applicability.json this checker loads and does NOT import checker
# (one-directional: checker -> graph), so there is no cycle.
import graph  # noqa: E402

# Stage 5 (ADR-008) — the LEGAL COMPARISON layer is declarative: check_space materializes each
# space's extracted facts into an in-memory rdflib A-Box and validates it against the SHACL shapes
# in ontology/dm1975_salvacasa.ttl via pyshacl. EXTRACTION math (the P0 fixes: positivity,
# unit resolvability, trustworthy-window F-C/L-2) stays in Python and runs BEFORE materialization.
from decimal import Decimal  # noqa: E402

from rdflib import Graph as _RdfGraph, Literal as _RdfLiteral, Namespace as _RdfNamespace  # noqa: E402
from rdflib import RDF as _RDF, URIRef as _URIRef  # noqa: E402
from rdflib.namespace import XSD as _XSD  # noqa: E402

_SH = _RdfNamespace("http://www.w3.org/ns/shacl#")
_LEGAL = _RdfNamespace("https://acc.local/legal#")

# --- Verified thresholds (rules/dm_1975_salva_casa.md) ---------------------------------
MIN_HEIGHT_HABITABLE_M = 2.70   # DM 5/7/1975 art. 1
MIN_HEIGHT_ACCESSORY_M = 2.40   # corridoi, disimpegni, bagni, ripostigli
MIN_HEIGHT_SALVA_CASA_M = 2.40  # DL 69/2024 conv. L 105/2024 — conditional, existing buildings
AEROILLUM_RATIO = 1.0 / 8.0     # superficie finestrata apribile / superficie pavimento

# Alloggio monostanza (single-room dwelling-UNIT) minimum surfaces — DM 5/7/1975 (mq 28 1p / mq 38
# 2p) + the Salva-Casa derogation (20 m² 1p / 28 m² 2p, DL 69/2024). Stage 4 Part 4 holds these in
# the requirement model (the 2nd rule), but evaluates them UNIT-level (a monolocale dwelling + a
# person count), which no current fixture carries -> 'undetermined', never a pass (monostanza_status).
# These are hardcoded statute constants, NOT parameterized by the compiled JSON and NOT gate-checked
# at runtime (honesty boundary): the parser-side verify_monostanza_against_text proves the SAME four
# numbers against the statute prose, test-side.
MIN_SURFACE_MONOSTANZA_1P_M2 = 28.0
MIN_SURFACE_MONOSTANZA_2P_M2 = 38.0
MIN_SURFACE_MONOSTANZA_SC_1P_M2 = 20.0   # Salva Casa, 1 person
MIN_SURFACE_MONOSTANZA_SC_2P_M2 = 28.0   # Salva Casa, 2 persons

# Heuristic classification of an IfcSpace by name (Name / LongName).
#
# Stage 4 Part 2: the occupancy vocabulary + occupancy→{height-bar, aero-applies} map is now
# EXTERNALIZED into rules/applicability.json, which classify()/check_space() read at runtime (via
# _applicability()). These tuples remain as the FROZEN REFERENCE: the table is generated from them
# and a load-time guard pins the loaded table set-equal to them INCLUDING codepoints — so e.g. the
# "küche" U+00FC hint cannot drift (FZK space 6 'Küche' matches the U+00FC hint, not the ASCII
# "kuche"; dropping it regresses FZK 5→fewer). They are also the provenance source (see below).
_HABITABLE_HINTS = ("living", "soggiorno", "bed", "letto", "camera", "kitchen", "cucina",
                    "dining", "pranzo", "studio", "room", "stanza",
                    # German (KIT/FZK fixtures)
                    "wohn", "schlaf", "kuche", "küche", "kind", "ess", "zimmer", "galerie",
                    "buro", "büro",
                    # KIT Institute names use the ASCII transliteration "Buero" (ue, not ü) which
                    # "buro" does not match, plus office/lab/teaching rooms. All habitable-strength,
                    # so the 1/8 aero check still applies (additive only; accessory hints take
                    # precedence in classify(), so these can never flip an accessory space).
                    "buero", "labor", "seminar", "besprechung")
_ACCESSORY_HINTS = ("corrid", "disimpegno", "bagno", "wc", "toilet", "bath", "closet",
                    "ripostiglio", "hall", "ingresso", "storage", "lavanderia", "laundry",
                    # German
                    "flur", "diele", "bad", "abstell", "keller", "treppe", "gaste", "gäste",
                    "speis", "technik", "hwr", "garage")

# The ONLY accessory tokens literally enumerated in DM-1975 Art.1 (rules/dm_1975_salva_casa.md:9-10:
# "corridoi, i disimpegni in genere, i bagni, i gabinetti ed i ripostigli"). These are the tokens
# Part 3 may gate-anchor to Art.1. Everything else — English, German/KIT, non-enumerated Italian
# (ingresso/lavanderia/…), and the ENTIRE habitable vocabulary — is a declared, test-pinned
# cross-lingual/heuristic glossary = named debt (baseline §7); Part 3 must NOT over-claim it as
# statute-verified. (gabinetti is represented via its synonyms wc/toilet, not the literal token.)
# This constant is the provenance source the table's "art1" hint group is generated from and the
# load-time guard pins it to — so the gate-anchorable subset cannot silently drift either.
_ART1_ACCESSORY_TOKENS = ("corrid", "disimpegno", "bagno", "ripostiglio")


class RequirementLookupError(LookupError):
    """Fail-closed: resolving a metric/applicability absent from the requirement model RAISES
    rather than returning a default — the checker-side mirror of parser.py's gate-raise
    (parser.py:329-332, 365-367). An unknown 5th metric (e.g. monostanza, Part 4) therefore
    cannot silently default to a pass; it must be added to the model explicitly."""


@dataclass(frozen=True)
class Requirement:
    """One canonical statutory requirement record. The requirement *model* is a small list of
    these; `Thresholds` is a backward-compatible accessor *view* over them (Stage-4 baseline §3).
    A new metric (monostanza, Part 4) is added as another record — no new dataclass field and no
    AttributeError, removing the rigidity the baseline flagged (the old fixed-4-field dataclass)."""

    rule_id: str            # statute anchor id, e.g. "dm1975-art1"
    metric: str             # "min_height" | "aero_ratio" | (future: "min_surface_monostanza_1p" …)
    applicability: str      # subject the metric applies to: "habitable" | "accessory" | …
    operator: str           # ">="
    value: float            # baseline value (metres / ratio)
    unit: str               # "m" | "ratio"
    salva_casa_value: Optional[float] = None  # derogated value under the Salva-Casa regime, if any


def _dm1975_requirements(min_height_habitable_m: float = MIN_HEIGHT_HABITABLE_M,
                         min_height_accessory_m: float = MIN_HEIGHT_ACCESSORY_M,
                         min_height_salva_casa_m: float = MIN_HEIGHT_SALVA_CASA_M,
                         aero_illuminating_ratio: float = AEROILLUM_RATIO) -> "List[Requirement]":
    """The canonical DM-1975 (+ Salva-Casa derogation) record set behind Thresholds. The four
    frozen numbers enter here and resolve back out byte-identically via the legacy accessors. The
    Salva-Casa height is the *derogated value of the habitable bar* (DPR 380 art.24 c.5-bis), so it
    lives as salva_casa_value on the habitable min_height record — not as a separate metric."""
    return [
        Requirement("dm1975-art1", "min_height", "habitable", ">=",
                    min_height_habitable_m, "m", salva_casa_value=min_height_salva_casa_m),
        Requirement("dm1975-art1", "min_height", "accessory", ">=",
                    min_height_accessory_m, "m", salva_casa_value=None),
        Requirement("dm1975-art5", "aero_ratio", "habitable", ">=",
                    aero_illuminating_ratio, "ratio", salva_casa_value=None),
        # Stage 4 Part 4 — the 2nd rule: alloggio monostanza minimum surfaces, per person count, the
        # Salva-Casa derogation carried as salva_casa_value (mirroring the habitable-height record
        # above). Hardcoded statute constants — NOT parameterized by the compiled JSON, NOT
        # gate-checked at runtime (honesty boundary). Applicability 'monolocale' is UNIT-level and
        # disjoint from the per-space occupancy classes, so the legacy accessors / to_legacy_dict()
        # are byte-unperturbed and check_space never resolves these — no per-space verdict can move.
        Requirement("dm1975-monostanza", "min_surface_monostanza_1p", "monolocale", ">=",
                    MIN_SURFACE_MONOSTANZA_1P_M2, "m²",
                    salva_casa_value=MIN_SURFACE_MONOSTANZA_SC_1P_M2),
        Requirement("dm1975-monostanza", "min_surface_monostanza_2p", "monolocale", ">=",
                    MIN_SURFACE_MONOSTANZA_2P_M2, "m²",
                    salva_casa_value=MIN_SURFACE_MONOSTANZA_SC_2P_M2),
    ]


class Thresholds:
    """Checker contract — a backward-compatible accessor *view* over a record-backed requirement
    model (Stage-4 baseline §3). The four legacy names (min_height_habitable_m /
    min_height_accessory_m / min_height_salva_casa_m / aero_illuminating_ratio) resolve through the
    records to the same DM-1975 floats, so check_space / the report / the print line are
    byte-unchanged. A future metric is added to the model without a new field. Fail-closed:
    resolving an absent metric RAISES (see resolve())."""

    def __init__(self, requirements: "Optional[List[Requirement]]" = None,
                 extras: Optional[dict] = None) -> None:
        self.requirements = (list(requirements) if requirements is not None
                             else _dm1975_requirements())
        # Unknown thresholds-block keys are PRESERVED here (never silently dropped, never
        # defaulted) so a future rule's metric reaches the model rather than vanishing (§3).
        self.extras = dict(extras or {})

    def resolve(self, metric: str, applicability: str, salva_casa: bool = False) -> float:
        """Resolve one requirement value from the records. Fail-closed: an absent
        metric/applicability (or an absent Salva-Casa derogation) RAISES — never a default."""
        for r in self.requirements:
            if r.metric == metric and r.applicability == applicability:
                if salva_casa:
                    if r.salva_casa_value is None:
                        raise RequirementLookupError(
                            f"no Salva-Casa derogation for metric={metric!r} "
                            f"applicability={applicability!r} (fail-closed)")
                    return r.salva_casa_value
                return r.value
        raise RequirementLookupError(
            f"requirement model has no metric={metric!r} applicability={applicability!r} "
            f"(fail-closed: refusing to backfill a default)")

    # --- backward-compatible legacy accessors (resolve to the same DM-1975 floats) ----------
    @property
    def min_height_habitable_m(self) -> float:
        return self.resolve("min_height", "habitable")

    @property
    def min_height_accessory_m(self) -> float:
        return self.resolve("min_height", "accessory")

    @property
    def min_height_salva_casa_m(self) -> float:
        return self.resolve("min_height", "habitable", salva_casa=True)

    @property
    def aero_illuminating_ratio(self) -> float:
        return self.resolve("aero_ratio", "habitable")

    def to_legacy_dict(self) -> dict:
        """The 4-key thresholds block, byte-identical to the pre-refactor asdict(Thresholds())
        (same keys, same insertion order, same floats) — keeps the report `thresholds` block and
        the verdict print line unchanged."""
        return {
            "min_height_habitable_m": self.min_height_habitable_m,
            "min_height_accessory_m": self.min_height_accessory_m,
            "min_height_salva_casa_m": self.min_height_salva_casa_m,
            "aero_illuminating_ratio": self.aero_illuminating_ratio,
        }

    @classmethod
    def from_rules_json(cls, path: str) -> "Thresholds":
        """Build the model from a compiled rule JSON. Reads today's 4-threshold block exactly as
        before: a present, non-None legacy key overrides the DM-1975 default, an absent one keeps
        it (identical to the old cls(**kw)). Any *extra* thresholds key is PRESERVED in `extras`
        (not silently dropped — §3), never defaulted."""
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        t = data.get("thresholds", data) if isinstance(data, dict) else {}
        if not isinstance(t, dict):
            t = {}
        legacy = ("min_height_habitable_m", "min_height_accessory_m",
                  "min_height_salva_casa_m", "aero_illuminating_ratio")
        defaults = (MIN_HEIGHT_HABITABLE_M, MIN_HEIGHT_ACCESSORY_M,
                    MIN_HEIGHT_SALVA_CASA_M, AEROILLUM_RATIO)
        vals = {k: (float(t[k]) if t.get(k) is not None else d)
                for k, d in zip(legacy, defaults)}
        extras = {k: t[k] for k in t if k not in legacy}
        return cls(requirements=_dm1975_requirements(**vals), extras=extras)


@dataclass
class SpaceFinding:
    global_id: str
    name: str
    occupancy: str                       # habitable | accessory | unknown
    height_m: Optional[float]
    floor_area_m2: Optional[float]
    window_area_m2: float
    aero_ratio: Optional[float]
    height_required_m: float
    height_ok: Optional[bool]
    aero_ok: Optional[bool]
    notes: List[str] = field(default_factory=list)

    @property
    def compliant(self) -> Optional[bool]:
        # Compliant-completeness (Stage 3 Part 3, Task A0): a space may read True ONLY if every
        # check applicable to its occupancy was actually evaluated. accessory needs {height_ok}
        # (aero is N/A — separate ventilation rules); habitable/unknown need BOTH {height_ok,
        # aero_ok}. If any applicable check is None => undetermined (None), never a pass on
        # partial evidence (closes the hole where a real geometry height alone would flip a
        # habitable space to compliant while its 1/8 aero ratio was never checked).
        required = ([self.height_ok] if self.occupancy == "accessory"
                    else [self.height_ok, self.aero_ok])
        if any(c is None for c in required):
            return None
        return all(required)


# Candidate quantity-set names. ArchiCAD/KIT files (incl. AC20-FZK-Haus) name the set
# literally "BaseQuantities", not "Qto_SpaceBaseQuantities" — verified empirically with
# IfcOpenShell 0.8.5, so both names must be tried.
_SPACE_QTO = ("Qto_SpaceBaseQuantities", "BaseQuantities")
_WINDOW_QTO = ("Qto_WindowBaseQuantities", "BaseQuantities")

# Net-room-height quantity keys, in precedence order. "Height" is FIRST so ArchiCAD/KIT files
# (FZK, Institute) resolve exactly as before; vendor net-height variants are fallbacks for files
# that name the quantity differently. All are read Qto-only (see _qty) — Revit's Pset
# "Unbounded Height" is a floor-to-floor span, not a net room height, so it is intentionally NOT
# in this list; recovering geometry-derived height is Part 3 work.
_SPACE_HEIGHT_KEYS = ("Height", "ClearHeight", "FinishCeilingHeight", "NetHeight", "AltezzaNetta")


def _qty(element, scale: float, pset_names, key: str, power: int = 1) -> Optional[float]:
    """Read a quantity from the first matching (Q)set name, converting length**power to metres.

    POSITIVITY (P0 audit, C-1/M-5): a height/area/length is physically > 0. A non-positive or
    non-finite value (negative, zero, NaN, inf) is rejected -> None (undetermined), never consumed
    as a real measurement. Returning a negative/zero quantity would fabricate a pass (or a
    nonsensical aero ratio over a non-positive denominator). Fail-closed: a present-but-garbage
    quantity becomes 'unmeasurable', not a laundered value."""
    qtos = ue.get_psets(element, qtos_only=True)  # 'id'/'type' helper keys are ignored by .get(key)
    for name in pset_names:
        raw = qtos.get(name, {}).get(key)
        if raw is not None:
            try:
                val = float(raw) * (scale ** power)
            except (TypeError, ValueError):
                return None
            if not math.isfinite(val) or val <= 0:
                return None
            return val
    return None


def space_height(space, scale: float) -> Optional[float]:
    """Net room height from a (Q)set. Try the key variants in _SPACE_HEIGHT_KEYS ("Height" first),
    returning the first non-None — so files that use ClearHeight/NetHeight/AltezzaNetta resolve
    while "Height"-bearing files (FZK, Institute) are unchanged. Qto-only via _qty."""
    for key in _SPACE_HEIGHT_KEYS:
        val = _qty(space, scale, _SPACE_QTO, key, power=1)
        if val is not None:
            return val
    return None


def space_floor_area(space, scale: float) -> Optional[float]:
    for key in ("NetFloorArea", "GrossFloorArea"):
        val = _qty(space, scale, _SPACE_QTO, key, power=2)
        if val is not None and val > 0:   # positivity (P0 audit, M-5): a negative/zero area is never
            return val                    # consumed as the aero denominator; _qty also guards now
    return None


def _window_area_bounds(win, scale: float):
    """Both positivity-guarded window-area sources as a tuple ``(attr, qto)``, each None if invalid or
    absent. ``attr`` = OverallHeight×OverallWidth (a bounding box); ``qto`` =
    Qto_WindowBaseQuantities.Area (net glazing). POSITIVITY + TYPE GUARD (P0 audit, C-1/M-3): the old
    ``if h and w`` admitted negatives (truthy), so two negative dims fabricated a POSITIVE area; and
    the bare float() crashed on a non-numeric dim. Require BOTH dims present, numeric, finite, and > 0
    (each dim, so −h·−w cannot sneak a positive product through); ``_qty`` already guards ``qto``.
    ``window_area`` prefers ``attr``; the C-1b aero lower bound uses ``min(attr, qto)`` so a 'pass' is
    a true lower bound (research/DECISION_MATRIX.md, F-C + L-2)."""
    h, w = getattr(win, "OverallHeight", None), getattr(win, "OverallWidth", None)
    attr = None
    if h is not None and w is not None:
        try:
            hf, wf = float(h), float(w)
        except (TypeError, ValueError):
            hf = wf = None
        if hf is not None and math.isfinite(hf) and math.isfinite(wf) and hf > 0 and wf > 0:
            attr = hf * wf * (scale ** 2)
    return attr, _qty(win, scale, _WINDOW_QTO, "Area", power=2)


def window_area(win, scale: float) -> Optional[float]:
    # Attr-preferring single window area (vendor-independent OverallHeight×OverallWidth, populated
    # across all tested models; Qto fallback when the attributes are absent). Positivity per C1-B
    # lives in _window_area_bounds. Returns None if neither source is valid -> the caller treats the
    # window as unmeasurable (never a fabricated / laundered area).
    attr, qto = _window_area_bounds(win, scale)
    return attr if attr is not None else qto


# --- Declarative applicability/selection table (Stage 4 Part 2) ------------------------
# rules/applicability.json externalizes the occupancy vocabulary + the occupancy→{height-bar,
# aero-applies} map + the Salva-Casa swap out of Python. classify()/check_space() read it via
# _applicability() (lazy, cached). 'unknown' is the STRICT COMPLEMENT of (accessory ∪ habitable)
# and is NEVER a stored class entry. No graph, no SPARQL — just data.
_APPLICABILITY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "rules", "applicability.json")
_APPLICABILITY_CACHE = None


@dataclass(frozen=True)
class _Applicability:
    accessory_hints: tuple                 # flat union of the accessory hint_groups (order preserved)
    habitable_hints: tuple                 # flat union of the habitable hint_groups
    classes: dict                          # {"accessory": {height_metric, aero_applies}, "habitable": …}
    salva_casa_swaps_non_accessory: bool   # salva_casa_regime.swaps.non_accessory_height present


def load_applicability(path: "Optional[str]" = None) -> "_Applicability":
    """Load + validate the declarative applicability/selection table.

    FAIL-CLOSED: a missing / empty / structurally invalid table RAISES — never a silent
    fallthrough that classifies everything 'unknown' (which would drop accessory's lower bar or
    mis-apply the aero check, i.e. a silent verdict shift). The loaded hint sets are pinned
    set-equal to the frozen Python tuples INCLUDING codepoints, and the 'art1' provenance subset is
    pinned to _ART1_ACCESSORY_TOKENS, so neither the vocabulary nor the gate-anchorable subset can
    drift from the frozen reference. 'unknown' must NOT be a stored class (it is the complement)."""
    path = path or _APPLICABILITY_PATH
    with open(path, encoding="utf-8") as fh:        # FileNotFoundError if missing -> fail-closed
        data = json.load(fh)
    classes_raw = data.get("occupancy_classes")
    if (not isinstance(classes_raw, dict)
            or "accessory" not in classes_raw or "habitable" not in classes_raw):
        raise ValueError(f"applicability table {path!r}: missing occupancy_classes accessory/habitable")
    if "unknown" in classes_raw:                    # strict-complement invariant
        raise ValueError(f"applicability table {path!r}: 'unknown' must NOT be a stored class "
                         f"(it is the strict complement of accessory ∪ habitable)")

    def _flat_hints(cls_name: str) -> tuple:
        groups = classes_raw[cls_name].get("hint_groups")
        if not isinstance(groups, list) or not groups:
            raise ValueError(f"applicability table {path!r}: {cls_name} has no hint_groups")
        out: List[str] = []
        for g in groups:
            out.extend(g.get("hints", []))
        return tuple(out)

    accessory_hints = _flat_hints("accessory")
    habitable_hints = _flat_hints("habitable")

    # Anti-drift guard: loaded hint sets MUST equal the frozen tuples incl. every codepoint
    # ('küche' U+00FC, 'gäste'/'büro' …). Divergence => raise (no silent classification regression).
    if set(accessory_hints) != set(_ACCESSORY_HINTS):
        raise ValueError(f"applicability table {path!r}: accessory hints diverge from frozen tuple")
    if set(habitable_hints) != set(_HABITABLE_HINTS):
        raise ValueError(f"applicability table {path!r}: habitable hints diverge from frozen tuple")
    art1 = {h for g in classes_raw["accessory"]["hint_groups"]
            if g.get("provenance") == "art1" for h in g.get("hints", [])}
    if art1 != set(_ART1_ACCESSORY_TOKENS):
        raise ValueError(f"applicability table {path!r}: art1 provenance subset diverges from "
                         f"the frozen Art.1 anchor")

    classes = {}
    for name in ("accessory", "habitable"):
        c = classes_raw[name]
        hm, aa = c.get("height_metric"), c.get("aero_applies")
        if hm not in ("accessory", "habitable") or not isinstance(aa, bool):
            raise ValueError(f"applicability table {path!r}: {name} invalid height_metric/aero_applies")
        classes[name] = {"height_metric": hm, "aero_applies": aa}

    swaps = (data.get("salva_casa_regime") or {}).get("swaps") or {}
    swap_non_acc = swaps.get("non_accessory_height") == "min_height_salva_casa_m"
    return _Applicability(accessory_hints, habitable_hints, classes, swap_non_acc)


def _applicability() -> "_Applicability":
    """Lazily load + cache the table. Lazy (not import-time) so importing checker never depends on
    the file existing, while the first classify()/check_space() call validates fail-closed."""
    global _APPLICABILITY_CACHE
    if _APPLICABILITY_CACHE is None:
        _APPLICABILITY_CACHE = load_applicability()
    return _APPLICABILITY_CACHE


def classify(space) -> str:
    # Stage 4b: the room->occupancy decision now flows from a SPARQL 1.1 query over the rdflib
    # ontology (graph.occupancy_via_graph), REPLACING the prior Python substring branch. Accessory-
    # first precedence + the strict 'unknown' complement live IN the query (priority ORDER BY +
    # LIMIT 1; a no-match yields 'unknown'); an empty/failed ontology RAISES (fail-closed — never a
    # silent pass). The ontology is seeded from the SAME rules/applicability.json _applicability()
    # loads, so this is verdict-equivalent to the flat table on the 3 fixtures BY CONSTRUCTION
    # (baseline §6) — reproducing the controls is necessary-but-insufficient; see ADR-006.
    return graph.occupancy_via_graph(space.Name, space.LongName)


def serving_windows(space):
    """The IfcWindow elements bounding a space via IfcRelSpaceBoundary (``space.BoundedBy``).

    TODO (audit M-8): fallback when a model omits IfcRelSpaceBoundary — associate windows by storey
    containment / exterior-wall hosting. Until then a space with no resolvable boundaries serves no
    windows (and, for a habitable room, an aero ratio that may be understated)."""
    return [getattr(rel, "RelatedBuildingElement", None) for rel in (space.BoundedBy or [])
            if getattr(rel, "RelatedBuildingElement", None) is not None
            and getattr(rel, "RelatedBuildingElement").is_a("IfcWindow")]


# --- Stage 5: declarative SHACL evaluation of the LEGAL comparison layer (ADR-008) -------------
# ontology/dm1975_salvacasa.ttl carries the DM-1975 / Salva-Casa rules as sh:NodeShape/
# sh:PropertyShape. check_space materializes each space's EXTRACTED facts (P0 math untouched,
# runs first) into a tiny A-Box and pyshacl-validates it; the ValidationReport is parsed back into
# the tri-valued height_ok/aero_ok via the MinCount-dominant post-pass (blueprint §3.5):
#   MinCount result (measurement ABSENT — the materializer omitted an unmeasurable value, never a
#   laundered 0.0)                               -> None  (UNDETERMINED)
#   MinInclusive result (present-but-below)      -> False (VIOLATION) — for aero, remapped to None
#     when the ratio was UNBOUNDED (an untrustworthy window present, C-1b L-2)
#   no result                                    -> True  (PASS)
# Fail-closed: a missing/empty/mis-targeted shapes file RAISES at load (anti-vacuous-conformance
# guard); an unexpected result path/constraint component RAISES (never silently mapped).
_SHACL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "ontology", "dm1975_salvacasa.ttl")
_SHACL_CACHE: dict = {}          # (h_hab, h_acc, h_sc, aero) -> parameterized shapes Graph
_SPACE_NODE = _URIRef("urn:acc:eval:space")   # the single-space A-Box focus node

# The four stable property-shape URIs the loader re-parameterizes from Thresholds — so the
# gate-verified compiled JSON stays the numeric source of truth (Stage-1 dynamic coupling: edit the
# law -> recompile -> the shapes carry the new number, no .py and no .ttl edit).
_SHACL_THRESHOLD_SLOTS = (
    # (property-shape local name, Thresholds attribute, sh:message template — the message is
    #  re-generated WITH the value so an overridden threshold never reports a stale number)
    ("MinHeightHabitable_PS", "min_height_habitable_m",
     "height below the {v} m habitable minimum (DM 1975 art.1)"),
    ("MinHeightAccessory_PS", "min_height_accessory_m",
     "height below the {v} m accessory minimum (DM 1975 art.1)"),
    ("MinHeightSalvaCasa_PS", "min_height_salva_casa_m",
     "height below the {v} m Salva-Casa derogated minimum (DPR 380/2001 art.24 c.5-bis)"),
    ("MinAeroRatio_PS", "aero_illuminating_ratio",
     "aero-illuminating ratio below the {v} (1/8) floor-area minimum (DM 1975 art.5)"),
)
_SHACL_TARGET_CLASSES = ("AccessorySpace", "HabitableBaselineSpace", "HabitableSalvaCasaSpace")


def load_shacl_shapes(thr: "Thresholds", path: "Optional[str]" = None) -> "_RdfGraph":
    """Load + validate + parameterize the SHACL shapes graph. FAIL-CLOSED (mirrors
    load_applicability): a missing/unparseable file raises; a shapes graph that does not target all
    three materialization classes raises (a mis-targeted shape set would conform VACUOUSLY — a
    silent pass); a missing threshold slot raises (never a silently unparameterized bar)."""
    path = path or _SHACL_PATH
    g = _RdfGraph()
    g.parse(path, format="turtle")               # FileNotFoundError / parse error -> fail-closed
    targeted = set(g.objects(None, _SH.targetClass))
    expected = {graph.ACC[c] for c in _SHACL_TARGET_CLASSES}
    if not expected <= targeted:
        raise ValueError(f"SHACL shapes {path!r}: missing sh:targetClass for "
                         f"{sorted(str(c) for c in expected - targeted)} — a space materialized "
                         f"under an untargeted class would conform vacuously (fail-closed)")
    for ps_name, thr_attr, msg_tmpl in _SHACL_THRESHOLD_SLOTS:
        ps = _LEGAL[ps_name]
        if g.value(ps, _SH.minInclusive) is None:
            raise ValueError(f"SHACL shapes {path!r}: {ps_name} has no sh:minInclusive slot "
                             f"(fail-closed — refusing an unparameterized legal bar)")
        # sh:minCount is THE load-bearing fail-closed construct: it is the only thing that turns an
        # ABSENT measurement (the materializer omits unmeasurable values) into UNDETERMINED instead
        # of a vacuous PASS (the post-pass maps no-result -> True). A shapes file without it would
        # silently demote undetermined -> pass (adversarial-verify 2026-07-02, ADR-008a) — refuse it.
        mc = g.value(ps, _SH.minCount)
        if mc is None or int(mc) < 1:
            raise ValueError(f"SHACL shapes {path!r}: {ps_name} has no sh:minCount >= 1 — the "
                             f"fail-closed UNDETERMINED construct is missing (an absent measurement "
                             f"would read as PASS); refusing (fail-closed)")
        val = getattr(thr, thr_attr)             # resolves via the record model; raises if absent
        g.set((ps, _SH.minInclusive, _RdfLiteral(Decimal(str(val)), datatype=_XSD.decimal)))
        # message parameterized WITH the value: an overridden bar (e.g. an edited-law recompile)
        # must never emit a message asserting the stale default number.
        g.set((ps, _SH.message, _RdfLiteral(msg_tmpl.format(v=val))))
    return g


def _shacl_shapes(thr: "Thresholds") -> "_RdfGraph":
    key = (thr.min_height_habitable_m, thr.min_height_accessory_m,
           thr.min_height_salva_casa_m, thr.aero_illuminating_ratio)
    if key not in _SHACL_CACHE:
        _SHACL_CACHE[key] = load_shacl_shapes(thr)
    return _SHACL_CACHE[key]


def _shacl_verdict(occ: str, salva_swap: bool, h, aero_ratio, aero_unbounded: bool,
                   thr: "Thresholds"):
    """Materialize one space's facts and SHACL-validate them. Returns
    ``(height_ok, aero_ok, violation_messages)`` — each verdict tri-valued (True/False/None).

    Materialization = projection of INPUT facts only: the target class encodes occupancy (from the
    Stage-4b graph) + the Salva-Casa regime flag; ``h``/``aero_ratio`` are the extracted values
    (None = unmeasurable -> triple OMITTED so sh:minCount fires UNDETERMINED). The legal
    comparisons happen in the shapes, not here."""
    import pyshacl  # heavy import, deferred; cached in sys.modules after first use

    if occ == "accessory":
        cls = graph.ACC.AccessorySpace
    elif salva_swap:
        cls = graph.ACC.HabitableSalvaCasaSpace
    else:
        cls = graph.ACC.HabitableBaselineSpace

    # Defense-in-depth: extraction (P0) already rejects non-finite values, but the post-pass maps
    # no-result -> True, so an uncomparable literal slipping through would fail OPEN. Never trust
    # the upstream alone at a fail-open boundary — raise here (adversarial-verify 2026-07-02).
    if h is not None and not math.isfinite(float(h)):
        raise ValueError(f"_shacl_verdict: non-finite height {h!r} reached materialization (fail-closed)")
    if aero_ratio is not None and not math.isfinite(float(aero_ratio)):
        raise ValueError(f"_shacl_verdict: non-finite aero ratio {aero_ratio!r} reached "
                         f"materialization (fail-closed)")

    data = _RdfGraph()
    data.add((_SPACE_NODE, _RDF.type, cls))
    # Measurements are materialized as xsd:decimal via the float's SHORTEST ROUND-TRIP repr, NOT as
    # xsd:double: float(2.4) is stored below the exact decimal 2.4, so a double-vs-decimal compare
    # flipped a genuinely-2.40 m room PASS -> VIOLATION at the exact bar (adversarial-verify
    # 2026-07-02, ADR-008a). Decimal(str(v)) puts both sides in decimal space: 2.4 == 2.40 -> PASS,
    # matching the old float-to-float semantics at the bar.
    if h is not None:
        data.add((_SPACE_NODE, graph.ACC.heightM,
                  _RdfLiteral(Decimal(str(float(h))), datatype=_XSD.decimal)))
    if occ != "accessory" and aero_ratio is not None:
        data.add((_SPACE_NODE, graph.ACC.aeroRatio,
                  _RdfLiteral(Decimal(str(float(aero_ratio))), datatype=_XSD.decimal)))

    _, report, _ = pyshacl.validate(data, shacl_graph=_shacl_shapes(thr))

    comps = {"height": [], "aero": []}
    path_msgs = {"height": [], "aero": []}
    for res in report.subjects(_RDF.type, _SH.ValidationResult):
        rpath = report.value(res, _SH.resultPath)
        comp = report.value(res, _SH.sourceConstraintComponent)
        if rpath == graph.ACC.heightM:
            slot = "height"
        elif rpath == graph.ACC.aeroRatio:
            slot = "aero"
        else:                                    # an unmodeled result = a shapes/materializer bug
            raise RuntimeError(f"unexpected SHACL result path {rpath!r} (fail-closed)")
        comps[slot].append(comp)
        msg = report.value(res, _SH.resultMessage)
        if msg is not None and comp == _SH.MinInclusiveConstraintComponent:
            path_msgs[slot].append(str(msg))

    def _tri(comp_list, unbounded=False):
        """MinCount-dominant ternary mapping (blueprint §3.5)."""
        if not comp_list:
            return True
        if _SH.MinCountConstraintComponent in comp_list:
            return None                          # measurement absent -> UNDETERMINED
        if all(c == _SH.MinInclusiveConstraintComponent for c in comp_list):
            return None if unbounded else False  # unbounded ratio can't prove a violation (L-2)
        raise RuntimeError(f"unexpected SHACL constraint components {comp_list} (fail-closed)")

    height_ok = _tri(comps["height"])
    aero_ok = None if occ == "accessory" else _tri(comps["aero"], unbounded=aero_unbounded)
    msgs = (path_msgs["height"] if height_ok is False else []) + \
           (path_msgs["aero"] if aero_ok is False else [])
    return height_ok, aero_ok, msgs


def check_space(space, scale: float, salva_casa: bool, thr: "Thresholds") -> SpaceFinding:
    table = _applicability()
    occ = classify(space)
    h = space_height(space, scale)
    area = space_floor_area(space, scale)
    # Per serving window: pref = attr-preferring area (== window_area); cons = conservative
    # min(attr, Qto) lower bound. pref is None when the window is unmeasurable (no valid source).
    wdata = []
    for w in serving_windows(space):
        attr, qto = _window_area_bounds(w, scale)
        pref = attr if attr is not None else qto
        cons = min([v for v in (attr, qto) if v is not None], default=None)
        wdata.append((pref, cons))
    win_display = sum(pref for pref, _ in wdata if pref is not None)   # measurable sum (display)

    # Applicability is table-driven (rules/applicability.json), not a hardcoded if: accessory uses
    # its own entry; habitable AND unknown (the strict complement) use the habitable entry, so
    # unknown is measured exactly like habitable (Institute 402/403 keep their aero check) but is
    # never relabelled accessory. _applicability()/classify() raise fail-closed on a missing table.
    applic = table.classes["accessory"] if occ == "accessory" else table.classes["habitable"]
    aero_applies = applic["aero_applies"]                          # False for accessory, else True
    required = thr.resolve("min_height", applic["height_metric"])  # accessory 2.40 / habitable 2.70
    if salva_casa and table.salva_casa_swaps_non_accessory and occ != "accessory":
        required = thr.resolve("min_height", "habitable", salva_casa=True)  # Salva-Casa swap -> 2.40

    finding = SpaceFinding(
        global_id=space.GlobalId,
        name=space.Name or space.LongName or "(unnamed)",
        occupancy=occ,
        height_m=round(h, 3) if h is not None else None,
        floor_area_m2=round(area, 3) if area is not None else None,
        window_area_m2=round(win_display, 3),
        aero_ratio=round(win_display / area, 4) if area else None,
        height_required_m=required,
        height_ok=None,
        aero_ok=None,
    )

    # ---- Stage 5 (ADR-008): DECLARATIVE legal evaluation ---------------------------------------
    # Everything above this line is EXTRACTION (P0 math + applicability, untouched). Below, the
    # C-1b TRUST decision also stays in Python (it is a measurement-trust question, not law); the
    # LEGAL comparisons (2.70 / 2.40 / 1/8) are SHACL shapes in ontology/dm1975_salvacasa.ttl,
    # parameterized from thr (the gate-verified numbers) and validated per space via pyshacl.
    aero_ratio_raw = None
    untrust_present = False
    win_trust = 0.0
    if aero_applies and area and area > 0:                 # area>0 defends a latent negative-floor path
        # C-1b trustworthy-window semantics (F-C plausibility + L-2 lower bound; ADR-007b/c). A
        # serving window is UNTRUSTWORTHY if unmeasurable (None) or larger than the floor it serves
        # (non-physical for openable glazing — the room's own floor is the scale, no magic constant).
        # The numerator is ALWAYS the CONSERVATIVE min(attr, Qto) lower bound — an inflated
        # bounding-box attr <= floor would otherwise fabricate area its Qto contradicts (the
        # ADR-007c bypass). The materialized acc:aeroRatio therefore carries a TRUE LOWER BOUND:
        # >= bar proves a pass even with an untrustworthy window present (L-2); < bar with an
        # untrustworthy window present is remapped to UNDETERMINED in the post-pass (the real ratio
        # might be higher). An untrustworthy window is never laundered to 0.0. When area itself is
        # unmeasurable the triple is OMITTED so sh:minCount fires UNDETERMINED.
        untrust_present = any(pref is None or pref > area for pref, _ in wdata)
        win_trust = sum(cons for pref, cons in wdata if pref is not None and pref <= area)
        finding.window_area_m2 = round(win_trust, 3)
        finding.aero_ratio = round(win_trust / area, 4)
        aero_ratio_raw = win_trust / area

    height_ok, aero_ok, shacl_msgs = _shacl_verdict(
        occ, salva_casa and table.salva_casa_swaps_non_accessory,
        h, aero_ratio_raw, untrust_present, thr)
    finding.height_ok = height_ok
    finding.aero_ok = aero_ok
    for msg in shacl_msgs:                       # sh:resultMessage per failed legal check
        finding.notes.append(f"SHACL: {msg}")

    # Diagnostics — same conditions and messages as the procedural version (notes, not verdicts).
    if h is None:
        finding.notes.append("no Qto_SpaceBaseQuantities.Height — geometry fallback needed")
    if not aero_applies:
        finding.notes.append("aero ratio N/A for accessory room (separate ventilation rules)")
    elif area and area > 0:
        if aero_ok is True and untrust_present:
            finding.notes.append("aero passes on trustworthy windows alone (conservative lower "
                                 "bound); untrustworthy window area ignored")
        elif aero_ok is None and untrust_present:
            finding.notes.append("untrustworthy serving-window area (unmeasurable or larger than the "
                                 "floor) — aero ratio cannot be bounded; undetermined (ADR-003)")
        elif aero_ok is False and win_trust == 0.0:
            finding.notes.append("no window via IfcRelSpaceBoundary — aero ratio may be understated")
    else:
        finding.notes.append("no NetFloorArea — cannot evaluate aero ratio")

    return finding


def _monostanza_flag_is_true(v) -> bool:
    """A monolocale/monostanza pset value counts as a TRUE flag only if it is affirmatively truthy —
    a mere key presence, an empty string, or a falsey value does NOT (fail-closed)."""
    if v is True or v == 1:
        return True
    return str(v).strip().lower() in ("true", "yes", "1", "monolocale", "monostanza", "si", "sì")


def _positive_int(v) -> "Optional[int]":
    """An INTEGER occupant count > 0, else None — a float room area or an empty IFCLABEL is not a
    count (STAGE4_BASELINE §6: FZK 'Personenanzahl' is an empty label, Duplex 'OccupancyNumber'=0)."""
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def monostanza_status(model) -> dict:
    """UNIT-level monostanza applicability — alloggio monostanza is a single-room dwelling UNIT + a
    person count, NOT a per-IfcSpace occupancy class (STAGE4_BASELINE §6). It is surfaced in a
    SEPARATE report channel and kept deliberately OUT of the per-space SpaceFinding/compliant
    keystone, the violations count, and spaces_undetermined — so the frozen per-space verdicts cannot
    move. Monostanza is APPLICABLE only when BOTH (a) a monolocale/single-room dwelling-unit flag AND
    (b) an INTEGER occupant count are present; absent either, the status is honest 'undetermined'
    (fail-closed — never a fabricated pass). On all three current fixtures neither is present: FZK/
    Institute carry no occupancy data, and Duplex's PSet_Revit_Other.OccupancyZoneName='Unit A/B' is
    a dwelling-unit NAME (not a monolocale flag and not a count) — a Duplex apartment is multi-room
    anyway. Positive evaluation is therefore deferred to a monolocale fixture (mirroring Stage-3's
    net-geometry deferral, ADR-004)."""
    has_monolocale = False
    has_count = False
    for space in model.by_type("IfcSpace"):
        for pset in ue.get_psets(space).values():
            if not isinstance(pset, dict):
                continue
            for k, v in pset.items():
                kl = str(k).lower()
                if ("monolocale" in kl or "monostanza" in kl) and _monostanza_flag_is_true(v):
                    has_monolocale = True
                if (("occupant" in kl) or ("personenanzahl" in kl) or kl == "occupancynumber") \
                        and _positive_int(v) is not None:
                    has_count = True
    if has_monolocale and has_count:
        # No current fixture reaches this branch; even here there is no monostanza surface quantity
        # to measure, so the honest result is 'undetermined' (deferred), never a fabricated pass.
        return {"applicable": True, "status": "undetermined",
                "reason": "monolocale unit + occupant count present, but monostanza surface "
                          "evaluation is deferred to a monolocale fixture (no surface quantity)"}
    return {"applicable": None, "status": "undetermined",
            "reason": "no monolocale flag + occupant count (Duplex has a dwelling-unit NAME only)"}


def materialize_ifcspaces(model, scale: float):
    """Stage 4b — materialize each IfcSpace into a per-run rdflib store (the room-in-store proof,
    HARD RULE (ii)). Returns an rdflib.Graph whose nodes are addressed by a
    ``urn:acc:space:<percent-quoted-GlobalId>`` URIRef — NEVER a ``:space_<gid>`` PREFIXED name (a
    GlobalId's ``$`` is URI-valid but illegal in a SPARQL PN_LOCAL). The room verdict does NOT flow
    through this store (classify queries the ONTOLOGY, not this graph); this is the architectural
    materialization of the rooms, asserted GlobalId-set-exact in test_graph."""
    from urllib.parse import quote
    from rdflib import Graph, Literal, URIRef
    store = Graph()
    store.bind("acc", graph.ACC)
    for s in model.by_type("IfcSpace"):
        node = URIRef("urn:acc:space:" + quote(str(s.GlobalId), safe=""))
        store.add((node, graph.ACC.globalId, Literal(str(s.GlobalId))))
        store.add((node, graph.ACC.name, Literal(str(s.Name or ""))))
        store.add((node, graph.ACC.longName, Literal(str(s.LongName or ""))))
        h = space_height(s, scale)
        if h is not None:
            store.add((node, graph.ACC.heightM, Literal(float(h))))
        area = space_floor_area(s, scale)
        if area is not None:
            store.add((node, graph.ACC.floorAreaM2, Literal(float(area))))
    return store


class NotCertifiableError(ValueError):
    """The model cannot be measured as-is (e.g. no resolvable project length unit) — a REFUSAL, not a
    verdict. Surfaced as a classified non-zero exit, never a silent pass. Subclasses ValueError so
    existing fail-closed `except ValueError` / `except Exception` call sites still catch it."""


def _length_unit_entity(model):
    """The project LENGTHUNIT entity, read from projects[0] — the SAME project
    ifcopenshell.calculate_unit_scale uses — so the resolvability verdict and the scale agree. (Closes
    the multi-project divergence the audit flagged: a guard scanning ALL projects could pass while the
    scale is taken from projects[0].) Returns None if absent."""
    projs = model.by_type("IfcProject")
    if not projs:
        return None
    uic = getattr(projs[0], "UnitsInContext", None)
    if uic is None:
        return None
    for unit in (getattr(uic, "Units", None) or []):
        if getattr(unit, "UnitType", None) == "LENGTHUNIT":
            return unit
    return None


def _conversion_chains_to_si(unit, _depth: int = 0) -> bool:
    """An IfcConversionBasedUnit (foot/inch/…) resolves iff its ConversionFactor's UnitComponent
    chains to an SI METRE (directly or via nested conversion units). Bounded recursion guards a
    cyclic/pathological file."""
    if _depth > 8:
        return False
    cf = getattr(unit, "ConversionFactor", None)              # IfcMeasureWithUnit
    comp = getattr(cf, "UnitComponent", None) if cf is not None else None
    if comp is None:
        return False
    if comp.is_a("IfcSIUnit"):
        return comp.Name == "METRE"
    if comp.is_a("IfcConversionBasedUnit"):
        return _conversion_chains_to_si(comp, _depth + 1)
    return False


def _length_unit_resolvable(unit) -> bool:
    """A LENGTHUNIT resolves to a defined metre scale iff it is an IfcSIUnit (METRE, any prefix) or an
    IfcConversionBasedUnit whose conversion chains to SI metre. An IfcContextDependentUnit (a custom
    unit with NO defined SI relationship, e.g. 'SMOOT') or any other kind is UNRESOLVABLE — for those
    calculate_unit_scale silently falls back to 1.0, the exact 1000x misread C-2 must refuse.
    PRESENCE alone is insufficient (the original C2-B defect, research/DECISION_MATRIX.md C-2);
    RESOLVABILITY is the real contract."""
    if unit is None:
        return False
    if unit.is_a("IfcSIUnit"):
        return unit.Name == "METRE"
    if unit.is_a("IfcConversionBasedUnit"):
        return _conversion_chains_to_si(unit)
    return False                                              # IfcContextDependentUnit / other


def length_scale_to_m(model) -> float:
    """Resolve the project length-unit scale to metres, FAIL-CLOSED (P0 audit C-2; hardened to C2-F
    per research/DECISION_MATRIX.md after the bias-resistant pilot disqualified the presence-only
    check). calculate_unit_scale() returns 1.0 not only for a real metre model but ALSO when the unit
    is ABSENT or PRESENT-BUT-UNRESOLVABLE (an IfcContextDependentUnit / unsupported kind) — both a
    silent 1000x-misread risk. Require the project LENGTHUNIT to RESOLVE (SI metre at any prefix, or a
    conversion unit chaining to SI), else RAISE NotCertifiableError. A genuine metre/mm/foot model
    resolves normally; only the absent/unresolvable cases refuse."""
    unit = _length_unit_entity(model)
    if not _length_unit_resolvable(unit):
        kind = "absent" if unit is None else f"present-but-unresolvable ({unit.is_a()})"
        raise NotCertifiableError(
            f"project LENGTHUNIT is {kind} — cannot resolve a metre scale; refusing to assume metres "
            "(an absent/unresolvable unit silently 1000x-misreads a non-metre model). Not certifiable.")
    return uu.calculate_unit_scale(model)


def run(path: str, salva_casa: bool = False, thr: Optional["Thresholds"] = None) -> dict:
    thr = thr or Thresholds()
    model = ifcopenshell.open(path)
    scale = length_scale_to_m(model)  # project length unit -> metres; RAISES if no LENGTHUNIT (C-2)
    findings = [check_space(s, scale, salva_casa, thr) for s in model.by_type("IfcSpace")]
    # Stage 4b: materialize the rooms into a per-run store each run (the room-in-store proof). The
    # verdict already flowed through the ontology query in classify(); this is the architectural
    # materialization — its node set is asserted GlobalId-exact by test_graph, surfaced as a count.
    ifcspace_store = materialize_ifcspaces(model, scale)
    serialized = []
    for f in findings:
        record = asdict(f)
        record["compliant"] = f.compliant  # property is not captured by asdict()
        serialized.append(record)
    violations = [d for d in serialized if d["compliant"] is False]
    # Production-safety keystone (STAGE3_BASELINE §1): a space with zero measurable checks has
    # compliant=None. It is NOT a violation (do not launder absence-of-evidence into either pass
    # or fail) but it MUST be surfaced — a model with undetermined spaces is not certifiable.
    undetermined = [d for d in serialized if d["compliant"] is None]
    return {
        "model": path,
        "schema": model.schema,
        "length_unit_scale_to_m": scale,
        "salva_casa": salva_casa,
        "thresholds": thr.to_legacy_dict(),  # accessor view -> same 4-key block (byte-identical)
        "spaces_evaluated": len(serialized),
        # Stage 4b room-in-store proof: count of IfcSpace nodes materialized into the per-run store
        # (GlobalId-set-exact with the model's IfcSpace set — asserted in test_graph).
        "ifcspace_store_nodes": len(set(ifcspace_store.subjects(graph.ACC.globalId, None))),
        "violations": len(violations),
        "spaces_undetermined": len(undetermined),
        # UNIT-level 2nd-rule channel (Stage 4 Part 4): separate from findings/violations/
        # spaces_undetermined, so the per-space verdicts stay frozen. 'undetermined' on all 3
        # fixtures (no monolocale unit + person count) — never a fabricated pass.
        "monostanza": monostanza_status(model),
        "findings": serialized,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Deterministic ACC checker — Slice A (IT habitability)")
    ap.add_argument("ifc", help="path to the .ifc model")
    ap.add_argument("--rules", metavar="FILE",
                    help="compiled rule JSON from parser.py; drives thresholds (else DM-1975 defaults)")
    ap.add_argument("--salva-casa", action="store_true",
                    help="apply the conditional 2.40 m exception (existing buildings)")
    ap.add_argument("--json", metavar="FILE", help="write the full report as JSON")
    args = ap.parse_args(argv)

    thr = Thresholds.from_rules_json(args.rules) if args.rules else Thresholds()
    try:
        report = run(args.ifc, args.salva_casa, thr)
    except NotCertifiableError as e:
        # C2-C (research/DECISION_MATRIX.md): a refusal is a CLASSIFIED non-zero exit (2) with a
        # clear message — NOT a raw traceback exiting 1, which a caller cannot distinguish from a
        # normal violations run. 0=compliant, 1=violations/undetermined/no-space, 2=not-measurable.
        print(f"NOT CERTIFIABLE: {e}")
        return 2
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False)

    src = f"rules={args.rules}" if args.rules else "defaults(DM-1975)"
    undetermined = report["spaces_undetermined"]
    undet_tag = f"{undetermined} undetermined / not certifiable" if undetermined else "0 undetermined"
    print(f"{report['schema']} | {report['spaces_evaluated']} IfcSpace | "
          f"{report['violations']} violation(s) | {undet_tag} | salva_casa={report['salva_casa']} | "
          f"H={thr.min_height_habitable_m} A={thr.min_height_accessory_m} "
          f"SC={thr.min_height_salva_casa_m} aero={round(thr.aero_illuminating_ratio, 4)} [{src}]")
    for f in report["findings"]:
        if f["compliant"] is False:
            print(f"  [X] {f['name']} [{f['occupancy']}] "
                  f"h={f['height_m']}m (>= {f['height_required_m']}) "
                  f"aero={f['aero_ratio']} (>= {round(thr.aero_illuminating_ratio, 3)}) {f['notes']}")
    # Surface every unmeasurable space with its note so a missing-quantity model can never read
    # as a bare "0 violations" pass (production-safety invariant, STAGE3_BASELINE §1).
    if undetermined:
        print(f"  --- {undetermined} space(s) UNDETERMINED - not measurable, model not certifiable ---")
        for f in report["findings"]:
            if f["compliant"] is None:
                print(f"  [?] {f['name']} [{f['occupancy']}] "
                      f"h={f['height_m']} area={f['floor_area_m2']} win={f['window_area_m2']} "
                      f"{f['notes']}")
    # H-1 (P0 audit): a model with ZERO IfcSpace evaluated is uncheckable, not compliant. Findings
    # derive only from IfcSpace, so spaces_evaluated==0 gives 0 violations / 0 undetermined and would
    # otherwise exit 0 — a vacuous pass below the per-space keystone's granularity. Treat it as
    # not-certifiable (e.g. rooms modeled as IfcZone/IfcBuildingElementProxy, or an empty model).
    no_spaces = report["spaces_evaluated"] == 0
    if no_spaces:
        print("  --- 0 IfcSpace evaluated - nothing measurable, model not certifiable ---")
    # Exit non-zero on violations OR undetermined spaces OR an unevaluable (no-space) model:
    # returning success (0) when nothing could be measured would be the silent compliant-pass this
    # stage forbids.
    return 1 if (report["violations"] or undetermined or no_spaces) else 0


if __name__ == "__main__":
    raise SystemExit(main())
