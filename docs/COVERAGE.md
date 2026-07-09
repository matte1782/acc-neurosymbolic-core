# Coverage — what is and is not checked

This page is deliberately blunt. In a liability-adjacent domain, overclaiming is the one
unrecoverable mistake; the engine's whole design is *refusing to guess*, and so does its
documentation.

## Checked today (statute-gate-verified, per IfcSpace)

| Requirement | Source | Bar | How verified |
|---|---|---|---|
| Minimum net height, habitable rooms | DM 5/7/1975 art. 1 | ≥ 2.70 m | bar re-derived from the statute text by the validation gate; SHACL shape |
| Minimum net height, accessory rooms (corridoi, disimpegni, bagni, gabinetti, ripostigli) | DM 5/7/1975 art. 1 | ≥ 2.40 m | same |
| Salva Casa height derogation (existing buildings, conditions operator-asserted) | DPR 380/2001 art. 24 c. 5-bis | ≥ 2.40 m | same; enabled with `--salva-casa` |
| Aero-illuminating ratio (openable window area / floor area), habitable rooms | DM 5/7/1975 art. 5 | ≥ 1/8 | window areas via IfcRelSpaceBoundary traversal + conservative trust semantics (ADR-007b/c, ADR-017) |

Also **held in the model but honest-undetermined at runtime**: alloggio monostanza minimum
surfaces (28/38 m²; Salva Casa 20/28 m²) — no available fixture carries a single-room
dwelling unit + occupant count, so the engine reports the channel `undetermined` rather than
fabricate a verdict.

The `LOMBARDY_MOCK` pack (bars 3.00/2.55, aero 1/10) is a **test fixture proving the
rule-pack generalization mechanism. It is not law** and is labeled as such everywhere.

## Explicitly NOT checked

Everything else. Including, non-exhaustively: structural adequacy, fire safety, energy
performance, accessibility (DM 236/89), acoustics, urban-planning conformity, ventilation
beyond the aero ratio, and any municipal regolamento edilizio. A `CONFORME` verdict means
*conforme to the four checked requirements above* — nothing more.

## Measurement boundaries (where verdicts become UNDETERMINED instead)

- Spaces without net height / floor-area quantities (Qto): geometry-derived substitutes were
  probed and **declined on evidence** — they recover gross, not net, values (ADR-004).
  Such spaces read `non determinabile`, never compliant.
- Windows not linked by IfcRelSpaceBoundary in a boundary-bearing model: counted as absent
  (the model's own assertion). In models that omit boundaries entirely, a spatial fallback
  can *confirm* a violation or demote it to undetermined — it can never mint a pass (ADR-018).
- Models without a resolvable length unit, or with zero IfcSpace: **refused** as NOT
  CERTIFIABLE (exit 2), never silently evaluated.

## Fixtures the evidence rests on

AC20-FZK-Haus (ArchiCAD, IFC4), AC20-Institute-Var-2 (ArchiCAD, IFC4, 82 spaces),
Duplex_A (Revit, IFC2X3 — the missing-quantities stress fixture: honestly 21/21
undetermined). No held-out third-party corpus exists yet; that gap is tracked openly in
`research/STRATEGIC_MOAT_ANALYSIS.md` §4.2.
