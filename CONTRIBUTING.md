# Contributing

Thank you for your interest. This project is licensed under Apache-2.0 (see
`LICENSE`); third-party obligations are inventoried in `NOTICE` and
`THIRD_PARTY_LICENSES`.

## Developer Certificate of Origin (DCO) — required

Every contribution must be signed off under the
[Developer Certificate of Origin 1.1](https://developercertificate.org/).
By adding a `Signed-off-by:` line to your commit message
(`git commit -s`), you certify that you have the right to submit the work
under the project's license:

```
Signed-off-by: Your Name <your.email@example.com>
```

Commits without a DCO sign-off will not be merged. This is deliberate and
was set up **before** the first external contribution: retroactive
relicensing requires contributor consent, so provenance discipline starts at
contribution one (see `research/COUNSEL_QUESTIONS.md` Q6 for the open
DCO-vs-CLA question).

## Ground rules (from the repo operating contract, `CLAUDE.md`)

- The canonical test gate is `scripts/run_all_tests.sh` — it runs all 9
  suites in script mode (case-level checks) **plus** pytest. Both modes must
  be green; plain `pytest` alone does not execute every check.
- Never weaken a check, a gate, or a frozen control to make something pass.
- Every factual claim in code comments or docs cites its source
  (`file:line` or URL).
- Decisions are recorded in `docs/decisions.md` (append-only ADR chain);
  never edit a past ADR — amend with a new `ADR-Na` entry.
