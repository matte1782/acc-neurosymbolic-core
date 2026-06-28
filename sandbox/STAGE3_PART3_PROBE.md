# Stage 3 — Part 3 · PHASE 0 geometry method probe (READ-ONLY; the GO/NO-GO record)

> **Status.** Facts + decision, no production code reasoning beyond the keystone. Produced by
> `/stage33rdpart` Phase 0 on **2026-06-18**, ifcopenshell **0.8.5**, Python 3.13, all three
> fixtures `scale_to_m = 1` (METRE). Every number below was produced by deterministic read-only
> scripts (`sandbox/probe_geom.py`, `sandbox/probe_window.py`) and **independently re-derived** by a
> 6-agent verify Workflow (`wf_919ec580-bba`): 3 untrusted reproducers (one per fixture, raw stdout
> pasted) + 3 adversarial challengers (one per quantity, tasked to *refute* the undetermined
> decision). Reproducers: **3/3 numbers_match_expected=true**. Challengers: **3/3 decision_stands=true**.

## Unit rule (locked, applies to every geometry method)
`ifcopenshell.geom.create_shape` returns vertices in **SI metres** (`convert-back-units` defaults
`False`), regardless of model unit. The `_qty` `scale**power` convention (`checker.py:116-126`)
applies **only** to raw Qto attribute values — **never** to geom output. (Not exercised by any
shipped code this part; recorded so a future geometry fallback never double-applies `scale`.)

## API enumerated (0.8.5, verified present — not assumed)
`ifcopenshell.util.shape`: `get_z(geometry)->float` (max−min Z extent), `get_footprint_area(geometry,
axis='Z')->float` (projected floor area), `get_volume`, `get_vertices`, `get_faces`, `get_bbox`,
`get_bbox_centroid`, `get_x/get_y`. `get_element_bounding_box` **does not exist**. `ifcopenshell.geom`:
`create_shape`, `settings()`; `settings.set("use-world-coords", True)` honored (`get(...)` → `True`).
**Shape-lifetime gotcha (verified):** `create_shape(...).geometry` discards the owning shape and
leaves `geometry.verts` **empty** — the shape object must stay referenced while metrics are read
(`shape = create_shape(...); g = shape.geometry; get_z(g)`). Any future geometry fallback MUST keep
the shape alive.

## create_shape success (Phase-0 step 1)
| Fixture | spaces | create_shape | note |
|---|---|---|---|
| AC20-FZK-Haus | 7 | **7 OK / 0 FAIL** | — |
| AC20-Institute-Var-2 | 82 | **82 OK / 0 FAIL** | — |
| Duplex_A_20110907 | 21 | **21 OK / 0 FAIL** | A201/B201 footprint 0.0 (axis-Z projection collapses — IfcFaceBasedSurfaceModel) |

## GROUND-TRUTH CROSS-CHECK — geom vs Qto (Phase-0 step 3)
`prism_r = (volume/footprint)/z_ext` (≈1.0 prismatic; <1 sloped/galerie). Geom in metres, compared
directly to Qto metres.

**FZK (Qto Height + Net/GrossFloorArea present):**
| space | prism_r | geom z_ext | Qto Height | geom footprint | NetFloorArea | GrossFloorArea | fp/Net |
|---|---|---|---|---|---|---|---|
| 4 | 1.0000 | **2.5000** | **2.5000** | 22.0725 | 21.4103 | **22.0725** | 1.031 |
| 3 | 1.0000 | 2.5000 | 2.5000 | 12.5027 | 12.1276 | 12.5027 | 1.031 |
| 2 | 1.0000 | 2.5000 | 2.5000 | 12.9850 | 12.5954 | 12.9850 | 1.031 |
| 5 | 1.0000 | 2.5000 | 2.5000 | 25.9885 | 25.2089 | 25.9885 | 1.031 |
| 1 | 0.9940 | 2.5000 | 2.5000 | 11.5314 | 11.1855 | 11.5314 | 1.031 |
| 6 | 1.0000 | 2.5000 | 2.5000 | 16.3055 | 16.3055 | 16.3055 | 1.000 |
| **7** (galerie) | **0.5994** | **3.3868** | **4.0000** | 107.1600 | 74.5092 | 107.1600 | 1.438 |

**Institute (Qto Height + Net/GrossFloorArea present):** 79/82 prismatic, **geom z_ext == Qto Height
== 2.7000 exactly**, footprint/Net = **1.03093 exactly** (e.g. 24.6400/23.9008, 132.2400/128.2728).
3 sloped spaces diverge: **402/403 (Dachboden attic, prism_r 0.7603, z_ext 1.6402 vs Qto 2.7000,
footprint 201.78 vs Net 71.08)**, 401 (prism_r 0.8408, z_ext 2.6693 vs 2.7000).

**Findings (cross-check):**
- **HEIGHT:** geom Z-extent reproduces the Qto Height **EXACTLY (≤1e-3)** for the **prismatic class**
  (prism_r ≳ 0.99) on both ground-truth fixtures; for the **sloped class** it diverges (galerie/attic),
  because Qto Height is the storey/ridge height, not the volume-averaged extent. ⇒ method is sound
  **for prismatic spaces only**; sloped spaces must stay undetermined.
- **AREA:** geom footprint == **GrossFloorArea** exactly on every FZK space; gross/Net = **1.031**
  systematically (1.000 only where a room has no wall deduction). The checker requires **NetFloorArea**.
  ⇒ geom footprint is a **GROSS** quantity — it overstates net by a non-constant per-room factor.

## DUPLEX NET-vs-GROSS GATE (Phase-0 step 4 — the decisive question)
Duplex carries **no Qto height/area at all**; the only height-like value is the Revit Pset
`PSet_Revit_Dimensions."Unbounded Height"` (floor-to-floor span). geom z_ext vs that Pset:
| space(s) | geom z_ext | Unbounded Height | gap (unb − z) |
|---|---|---|---|
| habitable rooms (A102/B102/A202/…) | 2.5810 | 2.6000 | +0.019 |
| accessory rooms (A104/A204/…) | 2.5870 | 2.6000 | +0.013 |
| double-height (A105/B105) | 5.6810 | 5.7000 | +0.019 |
| **R301 (Roof)** | **3.0000** | **3.0000** | **0.000 (exact)** |

**Duplex geom Z-extent ≈ Unbounded Height** for every space (mean gap **+0.016 m**; R301 exactly
equal). A true *net* clear height would be ≥0.1 m below floor-to-floor (slab + finishes); the ~1.6 cm
gap is an exporter/triangulation offset, **not** a finish deduction — confirmed by the model carrying
13 `IfcCovering` CEILING (gypsum-board) elements at the 2.600 bound that a net height must subtract
and `get_z` does not. **⇒ Duplex geom height is the SAME GROSS quantity the baseline already rejected.**
Same question for area: Duplex has no Qto area; geom footprint is the (gross) projected solid (and
0.0 for the 2 surface-model spaces). There is **no independent net ground truth on Duplex** to validate
either quantity as net.

> **Adversarial check (challenger, decision_stands=true).** The steelman "verdict is invariant on this
> fixture so trust z_ext anyway" was refuted as **fixture-luck**: the FZK/Institute "net" validation is
> contaminated because there net==gross coincide by construction (FinishFloorHeight=0, Height==ClearHeight
> ==FinishCeilingHeight), so it never certified `get_z` as a net *deduction*; and Duplex accessory rooms at
> z_ext 2.587 are only **+0.187 m** above the 2.40 m bar — a routine 10–20 cm screed+suspended-ceiling
> deduction would push true net below 2.40 and **false-pass** them. (Note: Duplex *does* carry a Revit
> `PSet_Revit_Dimensions.Area`, but that is a key/area-definition fallback — Part 2 Gap 3, explicitly
> deferred as risky — **not** geometry, and the challenger showed geom footprint ≠ that Area by a variable
> 0.77–0.93 factor; out of Part-3 scope and unvalidated as net.)

## WINDOW-BY-CONTAINMENT FEASIBILITY (Phase-0 step 5)
World-XY (`use-world-coords`=True verified) point-in-footprint containment vs the `IfcRelSpaceBoundary`
mapping (the ground truth). **EXACT requires ADD=0 AND DROP=0.**
| Fixture | RAW point-in-footprint | +0.30 m buffer | EXACT? |
|---|---|---|---|
| FZK | ADD=0 **DROP=11** (all) | **ADD=11** DROP=0 | **NO** |
| Institute | ADD=8 **DROP=206** | **ADD=808** DROP=0 | **NO** |
| Duplex | ADD=6 DROP=16 | ADD=58 DROP=2 | **NO** |

Window centroids sit *inside the hosting wall*, outside the net space footprint → raw point-in-poly
**drops nearly all** real windows; any buffer big enough to reach a room's own windows (~0.14 m, ≈ the
window-in-wall offset) simultaneously pulls in **adjacent** rooms' windows (the inter-room wall spacing
is the same scale) → massive over-assignment. Challenger buffer sweep: **no epsilon** gives 0/0 on any
fixture (FZK cliff 0.10→0.20; Institute discontinuous 0.10→0.15). Worse, Institute's frozen violations
**402/403** are sloped attic spaces whose footprint reconstruction is **non-deterministic** in 0.8.5
(returned 201.78 m² in isolation, EMPTY in multi-shape runs). ⇒ containment is **not safe to ship**;
one add/drop on a ground-truth fixture already fails the bar — here there are hundreds.

## DECISION (per quantity — Tasks A/B/C are CONDITIONAL on this)
| Quantity | Decision | Evidence |
|---|---|---|
| **A0 compliant-completeness** | **SHIP (keystone, first)** | verdict-neutral; closes partial-evidence pass hole |
| **A — geom HEIGHT** | **SKIP — undetermined** | method validated net on FZK/Institute *prismatic* (z_ext==Qto, ≤1e-3), but **Duplex z_ext ≈ gross Unbounded Height** (R301 exact); no net ground truth on Duplex; finish-deduction false-pass risk on accessory rooms |
| **B — geom AREA** | **SKIP — undetermined** | geom footprint == **GrossFloorArea** (gross/Net 1.031 on FZK); gross overstates net by variable factor; Duplex footprint 0.0 on 2 spaces; unsafe (inflates aero → false pass) |
| **C — window containment** | **DROP** | cannot reproduce boundary mapping exactly on **any** fixture (no buffer epsilon); risks erasing frozen 402/403; non-deterministic footprint on the violation spaces |

**Net result:** only **Task A0** ships. The geometry *method* is sound (reproduces net height exactly
on net-cavity models); the limitation is the **Duplex fixture's modeling convention** — Revit space
solids are the **gross floor-to-floor** volume, not the net room cavity. A *meaningful* (vs honest)
verdict on the no-quantity/gross-only class therefore requires a fixture **carrying net geometry**.
⇒ Stage 3 stays **🟢** (honest-undetermined close), recorded in **ADR-004**.

## Per-class Duplex outcome (why each stays undetermined — honest, not a shortfall)
- **All 21 spaces:** height stays `None` (geom = gross floor-to-floor, not net) → for
  habitable/unknown, also missing aero (no net area) → `compliant=None` via Task A0; for accessory,
  missing net height → `compliant=None`. **0 spaces become measurable.** undetermined stays **21/21**
  in both modes (no net height ⇒ no 2.70↔2.40 divergence). This is the correct "not certifiable" output.
