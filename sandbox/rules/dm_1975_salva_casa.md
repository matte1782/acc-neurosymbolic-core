# Slice A — Italian habitability rule (raw legal text)

> Source snippet consumed by `../parser.py`. Verbatim Italian excerpts + English gloss.
> Thresholds verified against primary sources (Normattiva / Gazzetta Ufficiale); see citations.

## DM Sanità 5 luglio 1975 — *Altezza minima e requisiti igienico-sanitari dei locali d'abitazione*

> **Art. 1.** «L'altezza minima interna utile dei locali adibiti ad abitazione è fissata
> in **m 2,70**, riducibile a **m 2,40** per i corridoi, i disimpegni in genere, i bagni,
> i gabinetti ed i ripostigli.»
>
> *(Habitable rooms: min net internal height 2.70 m; reducible to 2.40 m for corridors,
> circulation, bathrooms, WCs and store rooms.)*
>
> *Separate provision:* for **comuni montani above 1000 m s.l.m.**, the habitable-room minimum
> may be reduced to **m 2,55** (local climate/typology). Do not confuse this with the 2.40 m
> accessory-room value.

> **Art. 5 (rapporto aeroilluminante).** «Per ciascun locale d'abitazione l'ampiezza della
> finestra deve essere proporzionata in modo da assicurare un valore di fattore luce diurna
> medio non inferiore al 2% … in ogni caso la superficie finestrata apribile non potrà essere
> inferiore a **1/8 della superficie del pavimento**.»
>
> *(Openable window area must be ≥ 1/8 of the floor area; mean daylight factor ≥ 2%.)*

> **Alloggio monostanza.** «Un alloggio monostanza, per una persona, deve avere una superficie
> minima, comprensiva dei servizi, non inferiore a **mq 28**, e non inferiore a **mq 38** se per
> due persone.»

## "Salva Casa" — DL 29 maggio 2024 n. 69, conv. L 24 luglio 2024 n. 105

Inserts **commi 5-bis e 5-ter nell'art. 24 (Agibilità) del DPR 380/2001** (*Testo Unico
Edilizia*) — **not** a standalone new article. Comma **5-bis** lets a *tecnico abilitato*
asseverare igienic-sanitary conformity for existing buildings down to the reduced minimums:

- minimum internal height **2,40 m** (derogating the 2,70 m baseline);
- *alloggio monostanza* minimum surface (incl. services) **20 m²** (1 person) / **28 m²** (2 persons).

Comma **5-ter** makes the asseverazione admissible **only if ALL of the following hold
(cumulative / logical AND):**

1. the works are **interventi di recupero edilizio** and/or **cambio di destinazione d'uso**
   of existing building stock (*patrimonio edilizio esistente*);
2. the units meet the **requisiti di adattabilità** of **DM 14 giugno 1989 n. 236**;
3. a concurrent **ristrutturazione** project supplies **alternative solutions** (ventilation,
   superficie finestrata, internal layout) ensuring adequate *condizioni igienico-sanitarie*.

The regime is **transitory** ("nelle more" of the *requisiti igienico-sanitari* redefinition
foreseen at art. 20 c. 1-bis DPR 380/2001) and of direct application (MIT linee guida 30/01/2025;
TAR Liguria).

> **Rule-of-record caveat:** verbatim statutory wording above is taken from authoritative
> secondary reproductions of the consolidated DPR 380/2001; before freezing as a *rule of
> record*, re-verify against Normattiva (consolidated DPR 380/2001) and L. 105/2024 in the GU.

---

## Target rule (RASE decomposition)

- **Applicability:** `locale adibito ad abitazione` (residential space).
- **Selection:** habitable `IfcSpace` (exclude corridoi/bagni/ripostigli → accessory).
- **Requirement R1:** habitable net height ≥ **2.70 m** (accessory ≥ 2.40 m).
- **Requirement R2:** openable window area / floor area ≥ **1/8 (0.125)**.
- **Exception (DPR 380/2001 art. 24, c. 5-bis/5-ter):** existing-building *recupero*/change-of-use
  **AND** adattabilità (DM 236/1989) **AND** concurrent ristrutturazione with alternative solutions
  → asseverabile down to height ≥ **2.40 m** (monolocale ≥ 20 m² 1p / 28 m² 2p).

**Citations:** DM 5 luglio 1975 (GU n. 190 del 18/07/1975); DL 69/2024 (GU n. 124 del
29/05/2024) conv. L 105/2024 (GU n. 175 del 28/07/2024); DPR 380/2001 (Testo Unico Edilizia).
