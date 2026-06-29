#!/usr/bin/env python3
"""Differential evaluation of the C-1/C-2 adversarial corpus: PRE-FIX (emulated) vs FIXED (HEAD),
each scored against the spec-derived expected verdicts in expected_verdicts.json.

This is the corpus VALIDITY check demanded by the preregs (§7): the pre-fix code MUST fail the
safety gate on the discriminating fixtures (else the corpus is inadequate), and the shipped fix
(candidate C1-B / C2-B) is measured against the SAME external oracle — never the circular control
set. Emits research/corpus/corpus_results.json + a printed table.

Pre-fix emulation = the exact two pre-fix lines (verifiable against the ec07b03 diff):
  window_area: `if h and w: return float(h)*float(w)*scale**2` (negatives truthy);
  scale:       `calculate_unit_scale(model)` (silent 1.0, no LENGTHUNIT check).

Run from repo root:  python research/corpus/eval_corpus.py
"""
from __future__ import annotations

import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SANDBOX = os.path.join(_REPO, "sandbox")
_CORPUS = os.path.dirname(os.path.abspath(__file__))
_ADV = os.path.join(_CORPUS, "adversarial")
sys.path.insert(0, _SANDBOX)

import ifcopenshell.util.unit as uu  # noqa: E402
import checker as C  # noqa: E402


def _old_window_area(win, scale):
    h, w = getattr(win, "OverallHeight", None), getattr(win, "OverallWidth", None)
    if h and w:                                   # pre-fix: negatives are truthy
        return float(h) * float(w) * (scale ** 2)
    return C._qty(win, scale, C._WINDOW_QTO, "Area", power=2)


def _old_scale(model):
    return uu.calculate_unit_scale(model)          # pre-fix: silent 1.0 on missing LENGTHUNIT


def _evaluate(path, *, prefix: bool):
    """Return a dict describing the outcome of run() on `path` under fixed or emulated-prefix code."""
    if prefix:
        sv_w, sv_s = C.window_area, C.length_scale_to_m
        C.window_area = _old_window_area
        C.length_scale_to_m = _old_scale
    try:
        try:
            rep = C.run(path)
        except Exception as e:  # noqa: BLE001 — a refusal (e.g. no LENGTHUNIT) is a valid outcome
            return {"outcome": "refused", "error": f"{type(e).__name__}: {e}"}
        viol = rep["violations"]
        undet = rep["spaces_undetermined"]
        by_gid = {f["global_id"]: f["compliant"] for f in rep["findings"]}
        return {"outcome": "ran", "violations": viol, "undetermined": undet, "compliant_by_gid": by_gid}
    finally:
        if prefix:
            C.window_area, C.length_scale_to_m = sv_w, sv_s


def _judge(name, exp, prefix_res, fix_res):
    """Score each run against the spec-derived expectation. Returns (prefix_ok, fix_ok, note)."""
    if exp.get("expected") == "not_certifiable":
        fix_ok = fix_res["outcome"] == "refused"
        prefix_ok = prefix_res["outcome"] == "refused"
        note = "must REFUSE (no resolvable LENGTHUNIT)"
    elif exp.get("expected") == "processes":
        fix_ok = fix_res["outcome"] == "ran"
        prefix_ok = prefix_res["outcome"] == "ran"
        note = "declared unit -> must PROCESS (GATE-N over-reject guard)"
    else:  # C-1: violation-count + target-not-compliant
        want_v = exp["expected_total_violations"]
        gid = exp["target_gid"]

        def ok(res):
            if res["outcome"] != "ran":
                return False
            tgt = res["compliant_by_gid"].get(gid)
            tgt_ok = (tgt is not True) if exp.get("target_must_not_be_compliant") else True
            # instrument fix (DECISION_MATRIX C-1b): a fix that DROPS the target from the report could
            # pass "not compliant" + viol==want_v with undet=0. Pin the target as specifically
            # undetermined (compliant is None) when the spec expects undetermined.
            if exp.get("target_expected_undetermined"):
                tgt_ok = tgt_ok and (tgt is None)
            return res["violations"] == want_v and tgt_ok
        fix_ok = ok(fix_res)
        prefix_ok = ok(prefix_res)
        note = f"target {gid} must NOT be compliant; total violations == {want_v}"
    return prefix_ok, fix_ok, note


def main() -> int:
    exp_path = os.path.join(_CORPUS, "expected_verdicts.json")
    if not os.path.exists(exp_path) or not os.path.isdir(_ADV):
        print("SKIP: corpus absent — run gen_adversarial.py first (fixtures must be present).")
        return 0
    expected = json.load(open(exp_path, encoding="utf-8"))
    results = {}
    print(f"{'fixture':22} {'expected':16} {'PRE-FIX':28} {'FIXED':20} verdict")
    print("-" * 110)
    gate_s_fail_fix = 0
    corpus_discriminates = 0
    for name, exp in expected.items():
        path = os.path.join(_ADV, name)
        if not os.path.exists(path):
            print(f"{name:22} (file missing — regenerate)")
            continue
        pre = _evaluate(path, prefix=True)
        fix = _evaluate(path, prefix=False)
        pre_ok, fix_ok, note = _judge(name, exp, pre, fix)
        results[name] = {"expected": exp.get("expected") or f"viol={exp.get('expected_total_violations')}",
                         "prefix": pre, "fixed": fix, "prefix_correct": pre_ok, "fixed_correct": fix_ok}

        def summ(r):
            if r["outcome"] == "refused":
                return "refused"
            return f"viol={r['violations']} undet={r['undetermined']}"
        # GATE-S: the FIXED code must be correct (safe) on every adversarial fixture.
        if not fix_ok:
            gate_s_fail_fix += 1
        # corpus validity: pre-fix must be WRONG on the discriminating fixtures (not the controls).
        if exp.get("expected") != "processes" and not pre_ok:
            corpus_discriminates += 1
        verdict = "FIX OK" if fix_ok else "FIX FAIL"
        print(f"{name:22} {results[name]['expected']:16} "
              f"{summ(pre)+(' [WRONG]' if not pre_ok else ' [ok]'):28} "
              f"{summ(fix)+(' [ok]' if fix_ok else ' [WRONG]'):20} {verdict}")

    json.dump(results, open(os.path.join(_CORPUS, "corpus_results.json"), "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)
    print("-" * 110)
    print(f"GATE-S (fixed safe on all adversarial fixtures): "
          f"{'PASS' if gate_s_fail_fix == 0 else f'FAIL ({gate_s_fail_fix})'}")
    print(f"Corpus discriminating power (pre-fix wrong on >=1 discriminating fixture): "
          f"{'YES' if corpus_discriminates else 'NO — corpus inadequate, strengthen before judging'}")
    return 1 if (gate_s_fail_fix or not corpus_discriminates) else 0


if __name__ == "__main__":
    raise SystemExit(main())
