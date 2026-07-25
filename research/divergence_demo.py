#!/usr/bin/env python3
"""Differenziale eseguibile: la stessa stanza, il motore e le regole locali (studio 25/07/2026).

    CORREZIONE 26/07/2026 (v3). La ri-codifica cieca M-1 (tre agenti indipendenti sul solo testo
    primario, preregistrata) piu' la LETTURA DELLA FIGURA a pag. 69 del PDF (persa dall'estrazione
    testuale) hanno stabilito che: (a) la banda "p" dell'art. 105 c.4 e' ancorata all'INTRADOSSO
    dell'aggetto, non alla testa della finestra come assumevano v1/v2 — senza quella quota il
    verdetto e' NON DETERMINABILE; (b) Milano ha DUE requisiti distinti, aerante (art. 103, anta
    al lordo del telaio, 1/10 del piano di calpestio) e illuminante (art. 105): questo script
    modella SOLO l'illuminante; (c) restano non determinabili dal testo: L perpendicolare vs 45
    gradi, la clausola del 30%, ribalta/lucernari sotto i 30 gradi, gli operandi della regola di
    profondita'. Dettaglio in research/M1_RESULTS_LOCAL.md.

    CORREZIONE 25/07/2026 (v2). La v1 di questo script conteneva un errore di metodo che ne
    invalidava la conclusione principale, ed e' stato trovato da una revisione avversariale della
    proposta ADR-021 che si basava su di esso. Documentato qui invece che riscritto in silenzio.

    ERRORE 1 - il regime "nazionale" non era il motore. La v1 dava al DM 1975 il numeratore
    `superficie_apribile_m2` (anta netta). Il motore non calcola MAI un'anta netta: il numeratore
    aeroilluminante e' `cons = min(OverallHeight x OverallWidth, Qto_WindowBaseQuantities.Area)`
    (sandbox/checker.py:347-355 e :704), cioe' il VANO LORDO. Il differenziale confrontava
    quindi le regole comunali con codice che non esiste.

    ERRORE 2 - due finestre fisicamente impossibili. CASO 4 dichiarava un'anta di 5,00 m2 dentro
    una luce di 2,00 x 2,20 = 4,40 m2 (113,6% del foro); CASO 2 dichiarava un'anta pari al 100,0%
    della propria luce (telai a spessore zero). Erano esattamente i due casi che producevano la
    direzione "il nazionale promuove, la Lombardia boccia".

    CONSEGUENZA. Rieseguito con il numeratore vero, l'errore NON e' bidirezionale: il motore
    sbaglia sempre nella stessa direzione, promuovendo cio' che il regolamento comunale boccia.
    La frase della v1 "falsi fail E falsi pass, quindi non e' una scelta conservativa" era
    l'argomento su cui ADR-021 fondava il salto da "limitazione" a "difetto". Quell'argomento
    e' morto. Cio' che resta e' un difetto diverso e piu' semplice: il motore adotta una
    convenzione di misura LORDA che nessuna fonte nazionale gli fornisce, e non la dichiara.

PERCHE' ESISTE
    Le interviste sostenevano che il vincolo vero e' la regola LOCALE, non il calcolo nazionale.
    Lo studio su documenti pubblici (research/DIVERGENCE_STUDY_LOCAL.md) lo ha confermato su
    testo normativo primario. Questo script converte quella conclusione in aritmetica eseguibile:
    dato UN disegno, calcola la superficie accreditata e il verdetto sotto ciascun regime.

COSA NON E'
    * NON e' codice di produzione: nessun import del motore, nessun effetto sul gate.
    * NON e' un rule-pack: le codifiche qui sotto sono la MIA lettura dei testi citati nello
      studio, non verificata da un tecnico ne' da un ufficio comunale. Servono a dimostrare che
      la divergenza e' reale e quantificabile, non a decidere una pratica.
    * NON copre l'intero regolamento: solo la parte aeroilluminante necessaria al confronto.

FONTI (testo primario, citato verbatim nello studio)
    DM 5/7/1975 art. 5   -- "superficie finestrata apribile" >= 1/8 della superficie di pavimento;
                            la norma NON definisce come si misura la superficie finestrata.
    Milano RE art. 105   -- "superficie totale dell'apertura finestrata, misurata convenzionalmente
                            alla luce architettonica detratta l'eventuale porzione ad altezza
                            inferiore a 60 cm dal pavimento, sia pari ad almeno 1/10 della
                            superficie di pavimento"; 1/8 nella fascia profonda (2,5x-3,5x
                            l'altezza dell'architrave); oltre 3,5x nessuna dimensione basta;
                            aggetti > 150 cm: P = L/2, la porzione entro P vale 1/3 (1/2 se la
                            parete guarda a sud entro +/-60 gradi).
    Codogno RLI 3.4.10   -- stessa costruzione ma soglia aggetto > 120 cm e coefficiente 1/3
                            ("b + 1/3 a"); detrazione della quota sotto i 60 cm.

Uso:  python research/divergence_demo.py
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Frazione anta-netta / luce architettonica usata quando il caso non la dichiara.
# E' un'ASSUNZIONE di lavoro (telaio+controtelaio di un serramento ordinario), NON una fonte.
# Serve solo alla gamba "DM come e' scritto", che il motore comunque non implementa.
_FRAZIONE_ANTA_SU_LUCE = 0.70


@dataclass
class Locale:
    """Un locale e la sua finestra, come li leggerebbe un tecnico dal disegno."""
    nome: str
    superficie_pavimento_m2: float
    profondita_m: float               # dalla parete finestrata alla parete opposta
    larghezza_finestra_m: float
    altezza_finestra_m: float         # luce architettonica (vuoto di progetto)
    quota_davanzale_m: float          # dal pavimento al bordo inferiore del vuoto
    superficie_apribile_m2: Optional[float] = None   # anta netta; None = derivata dalla luce
    aggetto_sovrastante_m: float = 0.0   # balcone/veletta sopra la finestra (0 = nessuno)
    parete_a_sud: bool = False           # entro +/-60 gradi da sud
    # v3 (ri-codifica cieca M-1 + schema pag. 69 del PDF): la banda "p" di Milano art. 105 c.4
    # e' ancorata all'INTRADOSSO dell'aggetto, non alla testa della finestra. Senza questa quota
    # il verdetto milanese sotto aggetto e' NON DETERMINABILE (niente ancoraggi impliciti).
    quota_intradosso_aggetto_m: Optional[float] = None

    def __post_init__(self) -> None:
        if self.superficie_apribile_m2 is None:
            self.superficie_apribile_m2 = self.luce_architettonica_m2 * _FRAZIONE_ANTA_SU_LUCE
        # GUARDIA FISICA (errore 2 della v1): un'anta non puo' essere >= del foro che la contiene.
        # Senza questa assert la v1 dichiarava un'anta al 113,6% della propria luce, e proprio
        # quel caso impossibile generava meta' della "bidirezionalita'".
        if self.superficie_apribile_m2 >= self.luce_architettonica_m2:
            raise ValueError(
                f"{self.nome}: anta {self.superficie_apribile_m2:.2f} m2 >= luce architettonica "
                f"{self.luce_architettonica_m2:.2f} m2 - finestra fisicamente impossibile")

    @property
    def luce_architettonica_m2(self) -> float:
        return self.larghezza_finestra_m * self.altezza_finestra_m

    @property
    def quota_architrave_m(self) -> float:
        return self.quota_davanzale_m + self.altezza_finestra_m


@dataclass
class Esito:
    regime: str
    superficie_accreditata_m2: Optional[float]
    superficie_richiesta_m2: Optional[float]
    conforme: Optional[bool]           # None = la regola stessa dice "non sanabile"/indeterminato
    come_si_misura: str
    note: str = ""


def _detrai_fascia_bassa(loc: Locale, soglia_m: float = 0.60) -> float:
    """Detrae la porzione di vuoto sotto `soglia_m` dal pavimento (convenzione lombarda)."""
    sotto = max(0.0, min(soglia_m, loc.quota_architrave_m) - loc.quota_davanzale_m)
    return loc.luce_architettonica_m2 - sotto * loc.larghezza_finestra_m


def _derata_aggetto(loc: Locale, superficie_utile_m2: float, soglia_aggetto_m: float,
                    coeff_ombra: float) -> tuple[Optional[float], str]:
    """Porzione in ombra d'aggetto, accreditata a `coeff_ombra`.

    v3 (correzione M-1): la banda "p" (alta L/2) e' ancorata all'INTRADOSSO dell'aggetto e scende
    verso il basso — cosi' lo schema di pag. 69 del RE Milano, che partiziona la finestra in
    a (dentro p) / b (libera) / c (fascia 60 cm). La v1/v2 la ancorava alla testa della finestra:
    un ancoraggio scelto in silenzio fra letture che ribaltano il verdetto (blind test M-1, 3/3).
    Senza la quota dell'intradosso il risultato e' None = NON DETERMINABILE."""
    if loc.aggetto_sovrastante_m <= soglia_aggetto_m:
        return superficie_utile_m2, ""
    if loc.quota_intradosso_aggetto_m is None:
        return None, ("aggetto oltre soglia ma quota intradosso ignota: la banda p si ancora "
                      "all'intradosso (schema RE Milano pag. 69) -> non determinabile")
    p = loc.aggetto_sovrastante_m / 2.0
    banda_hi = loc.quota_intradosso_aggetto_m
    banda_lo = banda_hi - p
    base_utile = max(loc.quota_davanzale_m, 0.60)
    # a = finestra utile ∩ banda p (sovrapposizione di intervalli verticali)
    lo = max(banda_lo, base_utile)
    hi = min(banda_hi, loc.quota_architrave_m)
    a = max(0.0, hi - lo) * loc.larghezza_finestra_m   # porzione in ombra
    b = superficie_utile_m2 - a                        # porzione libera
    return b + coeff_ombra * a, (f"aggetto {loc.aggetto_sovrastante_m:.2f} m: p = L/2 = {p:.2f} m "
                                 f"dall'intradosso {banda_hi:.2f} m, {a:.2f} m2 accreditati a "
                                 f"{coeff_ombra:.2f}")


def motore_oggi(loc: Locale) -> Esito:
    """IL REGIME CHE CONTA: il DM 1975 come lo applica DAVVERO sandbox/checker.py.

    Numeratore = vano LORDO, min(OverallHeight x OverallWidth, Qto Area) (checker.py:347-355, :704);
    nessuna detrazione dei telai, nessuna detrazione della fascia sotto i 60 cm. Qui si modella
    il caso in cui il Qto e' assente o non piu' stretto del bounding box, cioe' la luce.
    Il DM art. 5 dice "apribile" e non definisce la misura: questa convenzione lorda e' una
    scelta del motore, senza fonte nazionale a sostegno."""
    richiesta = loc.superficie_pavimento_m2 / 8.0
    acc = loc.luce_architettonica_m2
    return Esito("MOTORE OGGI (DM 1975, vano lordo)", acc, richiesta, acc >= richiesta,
                 "OverallHeight x OverallWidth (vano lordo, telai inclusi)")


def dm1975_come_scritto(loc: Locale) -> Esito:
    """Il DM letto alla lettera ("finestrata APRIBILE"), che il motore NON implementa.

    Tenuto solo per mostrare quanto pesa la convenzione di misura a parita' di norma:
    il divario fra questa riga e quella sopra e' interamente una scelta del motore."""
    richiesta = loc.superficie_pavimento_m2 / 8.0
    return Esito("DM 1975 letterale (anta netta)", loc.superficie_apribile_m2, richiesta,
                 loc.superficie_apribile_m2 >= richiesta,
                 "superficie finestrata APRIBILE (anta netta)",
                 "NON e' cio' che il motore calcola")


def milano(loc: Locale) -> Esito:
    """Milano RE art. 105: luce architettonica meno fascia < 60 cm; 1/10, 1/8 in fascia profonda,
    non sanabile oltre 3,5x l'altezza dell'architrave; derata d'aggetto oltre 150 cm."""
    rapporto_prof = loc.profondita_m / loc.quota_architrave_m if loc.quota_architrave_m else 0.0
    if rapporto_prof > 3.5:
        return Esito("Milano RE art. 105", None, None, None,
                     "luce architettonica meno fascia < 60 cm",
                     f"profondita {rapporto_prof:.2f}x l'architrave: oltre 3,5x la norma non "
                     f"ammette conformita' con nessuna dimensione di finestra")
    utile = _detrai_fascia_bassa(loc)
    coeff = 0.5 if loc.parete_a_sud else (1.0 / 3.0)
    utile, nota_aggetto = _derata_aggetto(loc, utile, soglia_aggetto_m=1.50, coeff_ombra=coeff)
    if utile is None:
        return Esito("Milano RE art. 105", None, None, None,
                     "luce architettonica meno fascia < 60 cm", nota_aggetto)
    divisore = 8.0 if rapporto_prof > 2.5 else 10.0
    richiesta = loc.superficie_pavimento_m2 / divisore
    note = f"rapporto 1/{int(divisore)} (profondita' {rapporto_prof:.2f}x l'architrave)"
    if nota_aggetto:
        note += f"; {nota_aggetto}" + (" [parete a sud]" if loc.parete_a_sud else "")
    return Esito("Milano RE art. 105", utile, richiesta, utile >= richiesta,
                 "luce architettonica meno fascia < 60 cm", note)


def codogno(loc: Locale) -> Esito:
    """RLI Codogno art. 3.4.10: stessa detrazione, aggetto oltre 120 cm, coefficiente 1/3."""
    utile = _detrai_fascia_bassa(loc)
    utile, nota_aggetto = _derata_aggetto(loc, utile, soglia_aggetto_m=1.20, coeff_ombra=1.0 / 3.0)
    if utile is None:
        # Stessa costruzione "b + 1/3 a": l'ancoraggio della banda viene dalla figura del
        # rispettivo strumento, che per Codogno NON abbiamo verificato -> stessa prudenza.
        return Esito("RLI Codogno art. 3.4.10", None, None, None,
                     "apertura finestrata meno fascia < 60 cm", nota_aggetto)
    richiesta = loc.superficie_pavimento_m2 / 8.0
    return Esito("RLI Codogno art. 3.4.10", utile, richiesta, utile >= richiesta,
                 "apertura finestrata meno fascia < 60 cm", nota_aggetto)


# Il confronto che decide e' MOTORE OGGI contro i due regimi locali. La gamba letterale del DM
# e' informativa e resta fuori dal conteggio delle divergenze: confrontare il motore con una
# lettura della norma che il motore non implementa era proprio l'errore 1 della v1.
REGIME_MOTORE = motore_oggi
REGIMI_LOCALI = (milano, codogno)
REGIMI = (motore_oggi, dm1975_come_scritto, milano, codogno)


def _fmt(e: Esito) -> str:
    if e.conforme is None:
        esito = "NON DETERMINABILE" if "non determinabile" in e.note else "NON SANABILE"
    else:
        esito = "conforme" if e.conforme else "VIOLAZIONE"
    acc = f"{e.superficie_accreditata_m2:.2f}" if e.superficie_accreditata_m2 is not None else "  -"
    req = f"{e.superficie_richiesta_m2:.2f}" if e.superficie_richiesta_m2 is not None else "  -"
    return f"  {e.regime:<34} {acc:>6} m2 su {req:>6} m2 richiesti  ->  {esito}"


def confronta(loc: Locale) -> tuple[bool, str]:
    """Stampa il caso. Ritorna (divergente, direzione) dove direzione in
    {'', 'motore promuove / locale boccia', 'motore boccia / locale promuove', 'entrambe'}."""
    esiti = [r(loc) for r in REGIMI]
    print(f"\n{loc.nome}")
    print(f"  pavimento {loc.superficie_pavimento_m2:.1f} m2, profondita' {loc.profondita_m:.1f} m; "
          f"finestra {loc.larghezza_finestra_m:.2f} x {loc.altezza_finestra_m:.2f} m "
          f"(luce {loc.luce_architettonica_m2:.2f} m2, davanzale {loc.quota_davanzale_m:.2f} m), "
          f"anta {loc.superficie_apribile_m2:.2f} m2 "
          f"({100.0 * loc.superficie_apribile_m2 / loc.luce_architettonica_m2:.0f}% della luce)"
          + (f", aggetto {loc.aggetto_sovrastante_m:.2f} m" if loc.aggetto_sovrastante_m else ""))
    for e in esiti:
        print(_fmt(e))
        if e.note:
            print(f"      ({e.note})")

    v_motore = REGIME_MOTORE(loc).conforme
    esiti_locali = [r(loc) for r in REGIMI_LOCALI]
    # Un NON DETERMINABILE non e' un verdetto: non boccia e non promuove, quindi non entra
    # nel conteggio delle divergenze ne' nella direzione dell'errore (niente laundering).
    determinati = [e for e in esiti_locali
                   if not (e.conforme is None and "non determinabile" in e.note)]
    indeterminati = len(esiti_locali) - len(determinati)
    divergente = any(e.conforme != v_motore for e in determinati)
    permissivo = v_motore is True and any(e.conforme is not True for e in determinati)
    restrittivo = v_motore is False and any(e.conforme is True for e in determinati)
    direzione = ("entrambe" if permissivo and restrittivo else
                 "motore promuove / locale boccia" if permissivo else
                 "motore boccia / locale promuove" if restrittivo else "")
    if divergente:
        print(f"  >>> DIVERGENZA sul verdetto: {direzione or 'stesso esito, motivazione diversa'}")
    if indeterminati:
        print(f"  >>> {indeterminati} regime/i locale/i NON DETERMINABILE/I: senza la quota "
              f"dell'intradosso il confronto non si puo' nemmeno fare")
    return divergente, direzione


def main() -> int:
    print("=" * 82)
    print("DIFFERENZIALE v3: la stessa stanza, il motore e due regolamenti comunali")
    print("(dimostrazione, non codice di produzione - vedi la CORREZIONE nel docstring)")
    print("=" * 82)

    casi = [
        Locale("CASO 1 - stanza ordinaria, finestra sopra il minimo nazionale",
               superficie_pavimento_m2=20.0, profondita_m=4.0,
               larghezza_finestra_m=1.30, altezza_finestra_m=2.00, quota_davanzale_m=0.90,
               superficie_apribile_m2=1.70),
        Locale("CASO 2 - portafinestra: tutta la fascia bassa e' detratta in Lombardia",
               superficie_pavimento_m2=14.0, profondita_m=3.5,
               larghezza_finestra_m=0.90, altezza_finestra_m=2.20, quota_davanzale_m=0.00),
        Locale("CASO 3 - camera sotto un balcone, parete a NORD",
               superficie_pavimento_m2=24.0, profondita_m=5.0,
               larghezza_finestra_m=1.60, altezza_finestra_m=2.10, quota_davanzale_m=0.80,
               superficie_apribile_m2=2.20, aggetto_sovrastante_m=2.00, parete_a_sud=False,
               quota_intradosso_aggetto_m=2.90),   # intradosso alla testa della finestra
        Locale("CASO 3-bis - LA STESSA CAMERA sulla facciata opposta (a sud)",
               superficie_pavimento_m2=24.0, profondita_m=5.0,
               larghezza_finestra_m=1.60, altezza_finestra_m=2.10, quota_davanzale_m=0.80,
               superficie_apribile_m2=2.20, aggetto_sovrastante_m=2.00, parete_a_sud=True,
               quota_intradosso_aggetto_m=2.90),
        Locale("CASO 3-ter - LA STESSA CAMERA, ma con la quota dell'aggetto IGNOTA",
               superficie_pavimento_m2=24.0, profondita_m=5.0,
               larghezza_finestra_m=1.60, altezza_finestra_m=2.10, quota_davanzale_m=0.80,
               superficie_apribile_m2=2.20, aggetto_sovrastante_m=2.00, parete_a_sud=False),
        Locale("CASO 4 - stanza profonda: Milano non la ammette a nessuna dimensione",
               superficie_pavimento_m2=36.0, profondita_m=12.0,
               larghezza_finestra_m=2.00, altezza_finestra_m=2.20, quota_davanzale_m=0.90),
    ]
    divergenti = 0
    direzioni: dict[str, int] = {}
    for loc in casi:
        div, direzione = confronta(loc)
        divergenti += div
        if direzione:
            direzioni[direzione] = direzioni.get(direzione, 0) + 1

    print("\n" + "=" * 82)
    print(f"RISULTATO: {divergenti} casi su {len(casi)} in cui il verdetto del MOTORE differisce")
    print("           da almeno un regolamento comunale sullo stesso disegno.")
    print("\nDIREZIONE DELL'ERRORE (e' la parte che la v1 aveva sbagliata):")
    for d, n in sorted(direzioni.items()):
        print(f"  {d:<34} {n} casi")
    if not direzioni.get("motore boccia / locale promuove"):
        print("\n  L'errore e' A SENSO UNICO: il motore promuove cio' che il comune boccia,")
        print("  mai il contrario. Non e' quindi il caso 'ne' conservativo ne' informato' che")
        print("  la v1 affermava: e' una PERMISSIVITA' SISTEMATICA, che si corregge nel")
        print("  numeratore e nella sua dichiarazione, non aggiungendo un ingresso giurisdizione.")

    print("\nCOSA MOSTRA DAVVERO QUESTO SCRIPT")
    print("  1. La divergenza fra comuni e' reale e cambia i verdetti (Milano 150 cm contro")
    print("     Codogno 120 cm sull'aggetto: due strumenti lombardi che divergono TRA LORO).")
    print("  2. Il motore misura il vano LORDO. Il DM art. 5 dice 'apribile' e non definisce")
    print("     la misura: quella convenzione e' una scelta del motore, non dichiarata e senza")
    print("     fonte nazionale. Il divario fra le prime due righe di ogni caso e' quella scelta.")
    print("  3. Quello che NON mostra: che serva un ingresso 'giurisdizione'. Vedi")
    print("     research/ADR-021_PROPOSAL.md, respinta in quella forma il 25/07/2026.")

    print("\nAVVERTENZA: queste codifiche sono una lettura dei testi citati in")
    print("research/DIVERGENCE_STUDY_LOCAL.md, non verificate da un tecnico ne' da un ufficio")
    print("comunale. Dimostrano che la divergenza esiste; non decidono nessuna pratica.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
