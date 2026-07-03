#!/usr/bin/env bash
# =============================================================================
# Unified dual-mode test runner — the single blockable gate for CI/CD.
#
# WHY THIS EXISTS (ADR-011; research/STRATEGIC_MOAT_ANALYSIS.md §5 Days 2-3):
#   The 9 suites under sandbox/tests are dual-mode by convention, but two of
#   them (test_height_keys.py, test_requirement_model.py) keep every check
#   inside main() with no test_* function, so plain `pytest` collects ZERO
#   nodes from them and silently skips their 34 case-level checks. Script mode
#   (`python tests/test_X.py`) is the canonical mode (ADR-008a note): it
#   executes all 189 case-level checks. This runner executes BOTH modes and
#   fails (exit 1) if either mode reports any failure.
#
# Usage:
#   scripts/run_all_tests.sh            # from anywhere; repo-relative
# Env overrides:
#   PYTHON           python executable (default: python)
#   ACC_SANDBOX_DIR  sandbox dir (default: <repo>/sandbox) — for harness tests
#
# Exit codes: 0 = every script-mode check AND every pytest node green.
#             1 = any failure in either mode (blockable for CI).
# =============================================================================
set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SANDBOX="${ACC_SANDBOX_DIR:-$REPO_ROOT/sandbox}"
PYTHON="${PYTHON:-python}"

if [ ! -d "$SANDBOX/tests" ]; then
    echo "ERROR: test directory not found: $SANDBOX/tests" >&2
    exit 1
fi

overall_fail=0
total_pass=0
total_fail=0
suite_count=0

echo "=================================================================="
echo "MODE 1 — script mode (canonical: all case-level checks execute)"
echo "=================================================================="
# Per-suite timeout (GNU coreutils `timeout`, present in Git Bash and Linux CI);
# a hung suite must fail with attribution, not stall the gate until the job dies.
if command -v timeout >/dev/null 2>&1; then
    RUN=(timeout 300 "$PYTHON")
else
    RUN=("$PYTHON")
fi

for f in "$SANDBOX"/tests/test_*.py; do
    [ -e "$f" ] || { echo "ERROR: no test_*.py suites found" >&2; exit 1; }
    name="$(basename "$f")"
    suite_count=$((suite_count + 1))
    out="$("${RUN[@]}" "$f" 2>&1)"
    rc=$?
    # grep -c exits 1 on zero matches; that is a count, not an error.
    pass_n="$(printf '%s\n' "$out" | grep -c '^PASS ' || true)"
    fail_n="$(printf '%s\n' "$out" | grep -c '^FAIL ' || true)"
    total_pass=$((total_pass + pass_n))
    total_fail=$((total_fail + fail_n))
    if [ "$rc" -eq 124 ]; then
        overall_fail=1
        echo "FAIL  $name  (TIMEOUT after 300s)"
    elif [ "$rc" -ne 0 ] || [ "$fail_n" -ne 0 ]; then
        overall_fail=1
        echo "FAIL  $name  (exit=$rc, failed checks=$fail_n, passed=$pass_n)"
        printf '%s\n' "$out" | grep '^FAIL ' || printf '%s\n' "$out" | tail -n 5
    elif [ "$pass_n" -eq 0 ]; then
        # A suite that emits zero checks and exits 0 is silently broken (e.g. a
        # renamed main() or a dropped __main__ dispatch) — exactly the masking
        # class this runner exists to close. Require >=1 executed check per
        # suite; the TOTAL is deliberately not pinned (new checks may be added).
        overall_fail=1
        echo "FAIL  $name  (suite emitted 0 case-level checks — silently broken)"
    else
        echo "ok    $name  ($pass_n checks)"
    fi
done
echo "------------------------------------------------------------------"
echo "script mode: $suite_count suites, $total_pass checks passed, $total_fail failed"

echo
echo "=================================================================="
echo "MODE 2 — pytest (wrapper parity; collects the test_* functions)"
echo "=================================================================="
if (cd "$SANDBOX" && "$PYTHON" -m pytest tests -q); then
    :
else
    overall_fail=1
    echo "FAIL  pytest mode reported failures"
fi

echo
if [ "$overall_fail" -ne 0 ]; then
    echo "RESULT: FAIL — the gate is closed."
    exit 1
fi
echo "RESULT: PASS — $total_pass script-mode checks + pytest suite green."
exit 0
