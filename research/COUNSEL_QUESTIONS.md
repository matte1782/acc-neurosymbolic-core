# Counsel questions (open legal items — started Day 1 post-freeze)

Status: **open list for legal counsel; nothing here is settled**. Each item is
currently operated under a stated working interpretation; none of those
interpretations may appear in an external commercial document without counsel
sign-off. Origin: `research/STRATEGIC_MOAT_ANALYSIS.md` §2.3, §1.5, §3.2.5;
`NOTICE` LGPL boundary statement.

## Q1 — LGPL-3.0 and Python imports (ifcopenshell)
Is a Python `import ifcopenshell` legally analogous to dynamic linking, such
that our own code may be licensed independently (Apache-2.0) provided the
library remains user-replaceable? Working interpretation: yes, with the
(a)–(c) mechanics in `NOTICE`. The analogy is contested; we need a signed
opinion before any commercial distribution (installer, SaaS, on-prem bundle),
including whether one-file freezing prohibitions in `NOTICE` are sufficient.

## Q2 — Rule-pack EULA protectability
The copyrightable delta of a `.ttl`/IDS encoding of a public statute is thin
(facts and law are not copyrightable; EU sui-generis database right likely
weak for small curated packs). Is a contract-law EULA enforceable enough to
anchor the proprietary rule-pack tier, and what must it say? What is the
protectable status of the *adversarial corpus + gate-run provenance* bundle?

## Q3 — bSDD dictionary content licensing
If we publish an ACC dictionary to buildingSMART bSDD: which SPDX license for
the national-baseline entries (OSS side) vs per-comune packs (proprietary
side)? Publishing grants bSI redistribution via their search/API — does that
conflict with a proprietary pack tier? (Strategy: §1.5.)

## Q4 — CC-BY-ND boundaries (IDS / IFC specs)
We implement IDS 1.0 and IFC (both CC-BY-ND-4.0) without redistributing or
modifying the specifications. Confirm that emitting standard-conformant IDS
documents and referencing schema elements is outside the ND restriction, and
what attribution the specs require in product documentation.

## Q5 — Liability boundary of the sign-off design
§3.2.5 declares zero-human-review forbidden: every emitted rule pack carries a
professional sign-off record before any verdict is externally relied upon.
Does the sign-off design (who/when/pack-hash in the provenance node) actually
place asseverazione liability with the signing professional rather than with
us, and what disclaimer language must the report artifacts carry?

## Q6 — DCO vs CLA for external contributions
LICENSE landed before any external contribution (retroactive relicensing needs
contributor consent). Confirm DCO-only is sufficient for the planned open-core
posture, or whether a CLA is needed to preserve future licensing flexibility.
