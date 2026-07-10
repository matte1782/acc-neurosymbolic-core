# PREREG — R1 design-partner interviews (frozen BEFORE the first interview)

Status: FROZEN 2026-07-10. Same discipline as PREREG_C1/C2: hypotheses + kill criteria are
written before the evidence; the interviews are run to FALSIFY, not to confirm. Amendments
append-only. The per-person tactics live in docs/PROSPECTS_LOCAL.md (never committed).

## 1. Hypotheses with kill criteria (what would prove us WRONG)

| # | Hypothesis | KILLED if… |
|---|---|---|
| H1 | Height/RAI verification costs practitioners real time or real errors (value exists) | ≥3 of 5 say it's trivial/never bit them — recalled from REAL pratiche, not opinion |
| H2 | Practitioners receive or produce IFC in their normal flow (the wedge premise) | ≥4 of 5 have touched zero IFC in the last year → the wedge must move (plugin? PDF/DWG era?) |
| H3 | "Non determinabile" reads as trustworthy, not broken (the signature bet) | ≥3 react to the report's undetermined rows as "the tool failed" even AFTER the one-line explanation |
| H4 | A report they'd sign against needs only: measurements + bars + statute refs + ternary + model id | any RECURRING missing element across ≥2 interviews (that list = the real P3 spec) |
| H5 | Some practitioners will run a pilot on a real model within 2 weeks of the interview | 0 of 5 hand over a model or book a pilot → interest is polite, not real |

Verdicts are tallied from evidence lines (§4), not impressions. A killed hypothesis is a
RESULT, not a failure — H2 dying young saves months.

## 2. Bias controls (the interview-level GATE-S)

1. **Past, not future.** Only questions about the LAST time they verified heights/RAI: which
   pratica, which tool, minutes spent, what went wrong. Never "would you use / would you pay"
   — hypothetical yeses are decoys and score zero.
2. **No pitch before minute 15.** The first half is 100% their current process; the demo
   (report HTML + the 60-second flip) enters only in the second half. If we describe the tool
   first, every answer afterwards is contaminated.
3. **Their words, verbatim.** Log exact phrasing for: the check itself, the report elements,
   "non determinabile" reactions. (Feeds R3 terminology; paraphrase = data loss.)
4. **Hunt the disconfirming quote.** Each interview must log ≥1 line AGAINST our thesis
   (if none was heard, we didn't push — ask "cosa NON le serve di tutto questo?").
5. **Control sample.** ≥1 of 5 interviewees is the non-BIM traditionalist; their interview
   weighs double on H2 (the reachable-online sample is BIM-biased by construction).
6. **Affinity discount.** Interviewees who already built/paid for RAI tooling are
   pre-converted: they count for H4 depth but are EXCLUDED from the H1 tally.
7. **No "AI" in the first half.** The engine is deterministic anyway; leading with AI biases
   both enthusiasts and skeptics. It comes up only if they raise it.

## 3. Per-interview extraction targets (what the OSS project actually needs)

Each 30' interview should attempt, in priority order — one miss is fine, all-miss means the
interview was social, not research:

| Target | Feeds |
|---|---|
| 1 real anonymized IFC model (quantities present OR absent — both classes are gold) | the missing held-out third-party corpus (moat weakness #8); Duplex-class reality data |
| 1 pratica with a KNOWN verdict (their own past case) | external ground truth the frozen controls can't provide |
| their room-naming vocabulary (how rooms are actually named in their models/plans) | the 47/51 unanchored applicability tokens — the declared debt (baseline §7) |
| which LOCAL rule diverges from DM-1975 in their comune/region | the first REAL regional pack candidate (P1 template) |
| the exact missing-elements list for the report | P3 spec (H4) |
| 2 snowball names, incl. "un collega non digitalizzato" | the pipeline + the control sample |

## 4. Evidence log (append-only, one line per observation)

`research/interviews/LOG.md` (gitignored if it carries names): date, role-class (not name),
H# touched, verbatim quote, FOR/AGAINST, artifact obtained (model? case? vocabulary?).
Synthesis only AFTER interview 3, against the kill criteria above — not sooner.

## 5. Time budget + kill criteria for outreach itself

Prep is amortized (kit + demo exist): ≤15' per contact (personalize 2 sentences, verify
current role). Per contact: 1 message + 1 follow-up after 5 working days, then STOP (no
third touch). Global: if after 10 sends across ≥2 tiers there are 0 interviews booked, the
CHANNEL hypothesis is killed — reassess the approach (venue? sender? message?) before
sending more; do not brute-force volume.
