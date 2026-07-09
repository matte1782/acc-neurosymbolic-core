# Public-Debut Design Investigation — Scope

Status: PROPOSED (scoping only — no build work authorized by this document).
Date: 2026-07-10. Inputs: `research/STRATEGIC_MOAT_ANALYSIS.md` (§2 matrix, §2.4 buyers,
§4 weaknesses), ADR-010 (claims/counsel gate), ADR-016/017/018/019 (what is demonstrably true).

## 0. The reframe that sets the whole scope

The moat analysis is explicit: zero customers, zero pilots, zero channel (§4.2 #5/#9) — this is
"a pre-seed technical asset with a strong verification story, not a company with a moat."
Therefore the public debut is **not a sales site**. It is a **credibility artifact** with exactly
two jobs, in priority order:

1. **Recruit 3–5 design partners** (studi tecnici / BIM managers) into pilots — the moat doc's
   own first monetization gate is validation, and every pricing figure is marked unvalidated.
2. **Earn OSS scrutiny** of the verification method (§2.2 O1–O4: the open layer's value grows
   with public scrutiny — that value is currently zero because nobody has looked).

Success metric for the debut: qualified design-partner conversations started, and external
eyes on the verification harness. Not traffic, not signups.

## 1. The four surfaces (the user named three; the repo adds a fourth)

| Surface | Primary audience | The ONE question it must answer |
|---|---|---|
| **Repo README** (the real landing page for the OSS audience) | engineers, auditors, competitors | "Is this verification story real? Show me in 90 seconds." |
| **Landing page** (one static page) | studi tecnici, design-partner candidates | "Does this reduce MY liability on a pratica, and can I try it today?" |
| **Report UI** (the verdict, rendered for humans) | the geometra AND whoever they hand it to | "What failed, by how much, under which statute — and what could NOT be measured?" |
| **Docs** | adopters and integrators | "How do I run it on my model, and what exactly does/doesn't it check?" |

Insight the scoping must protect: **the report is the product** for the practitioner segment —
it is the artifact attached to a pratica edilizia. The landing page only sells the report.
And the moat matrix already splits it: a basic renderer is OSS funnel; the provenance-bearing
regulatory report is **P3, proprietary, and blocked on Phase-0 provenance emission (unbuilt)**.
The design investigation must respect that boundary, not blur it.

## 2. Hard constraints on every surface (claims discipline — non-negotiable)

- **Counsel gate (ADR-010):** no commercial claim, no LGPL-posture statement, no "certified"
  language before counsel sign-off. A debut CAN ship as an open-source project presentation
  with honest capability statements; it CANNOT ship pricing, guarantees, or liability language.
- **Coverage honesty:** the engine ships 2 statute rules over 3 fixtures. Every surface carries
  the coverage table. Overclaiming in a liability-adjacent domain is the one unrecoverable
  debut mistake.
- **LOMBARDY_MOCK is a test fixture, not law** — demo materials must label it as the
  generalization proof, never as a shipped regional pack.
- **No benchmark claims** (QW-2 harness debt, ADR-015/019): "~0.4 s on our fixtures" style
  only, machine-qualified.
- **Undetermined is the signature, not a bug:** the ternary verdict (pass / violation /
  UNDETERMINED-refuses-to-guess) is the differentiation vs T1/T2 (ACCA, Solibri). The visual
  language must make undetermined a first-class, dignified state (amber, explained), because
  "we refuse to guess" IS the pitch.

## 3. The investigation itself (the "deep research" worth paying for)

Five questions, cheapest adequate method each. Everything else is opinion we already hold.

| # | Question | Method | Output |
|---|---|---|---|
| R1 | What must a verdict report contain for a geometra to attach it to a CILA/SCIA/agibilità with their signature on it? | 3–5 practitioner interviews (the design-partner funnel doubles as research) | Report-content checklist; the P3 gap list |
| R2 | What do Solibri/ACCA/usBIM check-reports actually look like, and where do they hide uncertainty? | Artifact teardown (trials/screenshots), 2–3 days | Differentiation table; "show the false-pass" demo brief (feeds §4.1 T1) |
| R3 | Which words do practitioners use? (aeroilluminante vs aero ratio; altezza utile; asseverazione flow) | Same interviews + statute text we already gate-verify | Bilingual terminology sheet (IT-first UI labels, EN docs) |
| R4 | Does the IDS/bSDD ecosystem have report/exchange conventions the report UI should echo? (§1.5 boundary posture) | Desk review of IDS examples + EUnet4DBP outputs, 1–2 days | Interop notes for report schema naming |
| R5 | What makes an OSS verification project credible on first contact? | Teardown of 3 reference READMEs in adjacent trust-critical OSS | README skeleton |

Explicitly NOT in scope: brand identity, market sizing (the moat doc refuses invented TAM;
so do we), generative user research at scale, and anything requiring counsel-gated claims.

## 4. Scope tiers (recommendation: T0 now, T1 after ≥3 partner interviews, T2 gated)

**T0 — the honest minimum (days, no research dependency):**
- README rewrite around the 90-second story: quickstart demo (ADR-019) as GIF/asciinema,
  coverage table, verification-story links (ADR chain, GATE-S, frozen controls), design-partner
  CTA (a single email/form).
- Docs v0: quickstart, API seam usage, "what is and is not checked", the ternary semantics
  page (undetermined explained), FAQ for the honest limits.
- Report UI v0: a **self-contained static HTML renderer** of the existing report JSON —
  per-space table, ternary color language, notes verbatim, pack bars + pack id. OSS side of the
  split. No provenance claims (that is P3). This seeds R1 interviews with something reactable.

**T1 — the debut proper (1–2 weeks, after R1–R3):**
- One-page landing (static): practitioner-language (IT-first), the flip demo as the hero,
  coverage honesty above the fold, design-partner CTA. No pricing (counsel gate).
- Report UI v1: R1-checklist-driven revision; bilingual labels; print-clean.
- Docs v1: integrator path (API), pack-authoring boundary explained (ADR-016 trust model).

**T2 — gated, not scheduled:**
- P3 provenance report (proprietary) — blocked on Phase-0 provenance emission (unbuilt, §2.2).
- Hosted playground — blocked on abuse/security posture AND counsel (LGPL/SaaS reading).
- Any commercial page — blocked on counsel sign-off + first pilot evidence.

## 5. Decision points for the owner

- **D1 — audience priority:** confirm design-partners-first (recommended) vs OSS-first.
- **D2 — report split:** OSS renderer now, provenance report stays P3/proprietary (recommended).
- **D3 — no hosted playground at debut** (recommended: local-first is also the data-sovereignty
  story, §1.2) — revisit on demand evidence.
- **D4 — language:** IT-first landing + report labels, EN-first docs/README (recommended).
- **D5 — commit to the 3–5 practitioner interviews** — the only spend that de-risks the debut;
  without R1 the report UI is designed from imagination.
