# Track "scan-to-verdict" — CANCELLI PRE-IMPEGNO (scritti PRIMA di ogni riga di codice)

Status: GATES FROZEN 2026-07-18. Questo documento esiste per vincolare il futuro:
il track parte SOLO attraversando i cancelli in ordine. Saltarne uno = violazione
della disciplina di repo (CLAUDE.md: fix the code, not the harness).

Origine: interviste R1 #1 (geometra: "il dolore e' il rilievo... altezza media dei
sottotetti") e #2 (architetto: "il top sarebbe un programma che dal laser scanner mi
estrae automaticamente [ambienti e finestre]"). Evidenza in research/interviews/LOG.md.

## Cancello 0 — SINTESI R1 (bloccante)
Il track NON parte prima della sintesi delle interviste (>=3) contro i kill criteria di
PREREG_R1_interviews.md. Se la sintesi non conferma "il dolore e' l'acquisizione dati",
questo documento resta un'idea archiviata.

## Cancello 1 — LITERATURE PROBE (giorni, non settimane)
Prior documentato dalla letteratura scan-to-BIM (benchmark pubblici: S3DIS, ScanNet;
dataset sintetici: Structured3D o equivalenti) su: (a) segmentazione pavimento/soffitto,
(b) rilevazione aperture, (c) sim-to-real gap. Output: un prior scritto, con fonti,
per le soglie del Cancello 3.

## Cancello 2 — PRE-PROBE FISICO (weekend, costo zero)
Scansioni reali (telefono LiDAR o dataset) di >=3 stanze con ground truth a metro,
inclusa >=1 con soffitto inclinato. Misura: altezza media estratta vs metro.
Se l'errore mediano supera quanto serve per soglie legali a centimetri, STOP qui.

## Cancello 3 — PREREG FORMALE (prima del probe vero)
Come PREREG_C1/C2: ipotesi, soglie di accuratezza, % minima di locali determinabili,
kill criteria — TUTTO congelato prima di raccogliere i dati del probe. Corpus
sintetico procedurale (ground truth per costruzione) come GATE-S del track + scansioni
reali come controlli. Il sim-to-real e' dichiarato: il sintetico affianca, non sostituisce.

## Cancello 4 — ARCHITETTURA VINCOLATA (non negoziabile)
Neuro-simbolico, come Stage 2: la parte neurale (segmentazione, anche addestrata su
sintetico) PROPONE; un validatore deterministico RI-MISURA sui punti grezzi (fit del
piano entro epsilon, evidenza di densita' per le aperture); cio' che non regge la
ri-misura -> "non determinabile" o conferma umana. Il verdetto NON nasce mai
dall'output di un modello probabilistico. Tolleranza di misura dichiarata nel report
(a 2,68 m +/-3 cm contro soglia 2,70: la risposta giusta E' non determinabile).

## Cancello 5 — SHIP RULE
Si spedisce solo cio' che il probe dimostra (precedenti: ADR-004 boccio', ADR-017
promosse dopo 217/217). Ogni quantita' non validata resta fuori. Zero falsi conformi
per costruzione; la COPERTURA e' un numero misurato e pubblicato, mai promesso.
