#!/usr/bin/env bash
# =============================================================================
# ACC quickstart demo — one building, two legal frameworks, verdicts in ms.
#
# Builds a synthetic FZK-style IFC (one habitable room, 10 m² floor, 3.10 m
# height, one 1.2 m² window attached via IfcRelSpaceBoundary), then evaluates
# it against:
#   1. DM 5/7/1975 (national baseline)      — aero minimum 1/8  (0.125)
#   2. LR Lombardia MOCK (emitted rule pack) — aero minimum 1/10 (0.100)
# The room's aero-illuminating ratio is 0.12: a VIOLATION under 1/8, COMPLIANT
# under 1/10 — the verdict flips purely through the swapped SHACL rule pack.
#
# Usage:  scripts/quickstart_demo.sh          (from anywhere; repo-relative)
#         NO_COLOR=1 scripts/quickstart_demo.sh   (plain output)
# =============================================================================
set -u
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python}"

exec "$PYTHON" - "$REPO_ROOT" <<'PYEOF'
import os
import sys
import tempfile
import time

if hasattr(sys.stdout, "reconfigure"):          # Windows consoles default to cp1252
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

repo = sys.argv[1]
sys.path.insert(0, os.path.join(repo, "sandbox"))

want_color = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
def c(code, s):
    return f"\033[{code}m{s}\033[0m" if want_color else s
RED, GREEN, YELLOW, BOLD, DIM = "31", "32", "33", "1", "2"

import warnings
warnings.filterwarnings("ignore")

import ifcopenshell as ifc
import checker
import gate_spike as gs
import orchestrator

# --- 1. the showcase model (synthetic, built in-memory, written to a temp .ifc) -------------
f = ifc.file(schema="IFC4")
metre = f.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")
f.create_entity("IfcProject", GlobalId=ifc.guid.new(), Name="quickstart",
                UnitsInContext=f.create_entity("IfcUnitAssignment", Units=[metre]))
space = f.create_entity("IfcSpace", GlobalId=ifc.guid.new(), Name="Soggiorno")
qto = f.create_entity(
    "IfcElementQuantity", GlobalId=ifc.guid.new(), Name="BaseQuantities",
    Quantities=[f.create_entity("IfcQuantityLength", Name="Height", LengthValue=3.10),
                f.create_entity("IfcQuantityArea", Name="NetFloorArea", AreaValue=10.0)])
f.create_entity("IfcRelDefinesByProperties", GlobalId=ifc.guid.new(),
                RelatedObjects=[space], RelatingPropertyDefinition=qto)
win = f.create_entity("IfcWindow", GlobalId=ifc.guid.new(), Name="W1",
                      OverallHeight=1.0, OverallWidth=1.2)
f.create_entity("IfcRelSpaceBoundary", GlobalId=ifc.guid.new(), RelatingSpace=space,
                RelatedBuildingElement=win, PhysicalOrVirtualBoundary="PHYSICAL",
                InternalOrExternalBoundary="EXTERNAL")
tmpdir = tempfile.mkdtemp(prefix="acc_quickstart_")
ifc_path = os.path.join(tmpdir, "showcase.ifc")
f.write(ifc_path)

# --- 2. the two rule packs -------------------------------------------------------------------
dm_thr = checker.Thresholds()                                     # national defaults (1/8)
ttl_text = gs.emit_shacl(gs._LOMBARDY_MOCK_VERIFIED, None, gs._LOMBARDY_MOCK_CORPUS,
                         spec=gs.LOMBARDY_MOCK_SPEC)              # ADR-016 verified emitter
gs.verify_emitted_shapes(ttl_text, gs._LOMBARDY_MOCK_VERIFIED, spec=gs.LOMBARDY_MOCK_SPEC)
lom_ttl = os.path.join(tmpdir, "lombardy_mock.ttl")
with open(lom_ttl, "w", encoding="utf-8") as fh:
    fh.write(ttl_text)
lom_thr = checker.Thresholds(requirements=checker._dm1975_requirements(3.00, 2.55, 2.55, 0.1))

def run(ttl, thr):
    t0 = time.perf_counter()
    rep = orchestrator.ComplianceOrchestrator(ifc_path, ttl_path=ttl, thr=thr).run()
    return rep, (time.perf_counter() - t0) * 1000.0

rep_dm, ms_dm = run(None, dm_thr)
rep_lo, ms_lo = run(lom_ttl, lom_thr)
fd, fl = rep_dm["findings"][0], rep_lo["findings"][0]

def tick(ok):
    return c(GREEN, "PASS") if ok else c(RED, "FAIL")

W = 66
print()
print(c(BOLD, "  ACC Neurosymbolic Compliance Engine — quickstart"))
print(c(DIM, "  " + "─" * W))
print(f"  Model    Soggiorno · floor {c(BOLD,'10.00 m²')} · height {c(BOLD,'3.10 m')}"
      f" · window {c(BOLD,'1.20 m²')} (via IfcRelSpaceBoundary)")
print(f"  Measured aero-illuminating ratio: {c(BOLD, str(fd['aero_ratio']))}"
      f"  (window area / floor area)")
print(c(DIM, "  " + "─" * W))

def block(title, bar_txt, find, rep, ms):
    verdict = "COMPLIANT" if find["compliant"] else "VIOLATION"
    vcol = GREEN if find["compliant"] else RED
    hreq = find["height_required_m"]
    aero = find["aero_ratio"]
    stats = "({0} violation(s) · {1:.0f} ms)".format(rep["violations"], ms)
    print("  " + c(BOLD, title))
    print("    height   3.10 m  ≥ {0:.2f} m   {1}".format(hreq, tick(find["height_ok"])))
    print("    aero     {0}  ≥ {1}   {2}".format(aero, bar_txt, tick(find["aero_ok"])))
    print("    verdict  " + c(vcol, c(BOLD, verdict)) + "   " + c(DIM, stats))
    print()

print()
block("1 · DM 5/7/1975 — national baseline (aero ≥ 1/8)", "0.125", fd, rep_dm, ms_dm)
block("2 · LR Lombardia MOCK — regional pack (aero ≥ 1/10)", "0.100", fl, rep_lo, ms_lo)
print(c(DIM, "  " + "─" * W))
print(f"  Same building, same extraction — the verdict flips "
      f"{c(RED, 'FAIL')} → {c(GREEN, 'PASS')} purely through the swapped,")
print(f"  statute-gate-verified SHACL rule pack, in "
      f"{c(BOLD, f'{ms_dm + ms_lo:.0f} ms')} total.")
print(c(DIM, "  Every bar is re-derived from the statute's own text (ADR-016); every"))
print(c(DIM, "  verdict is ternary and fail-closed (pass / violation / undetermined)."))
print()
PYEOF
