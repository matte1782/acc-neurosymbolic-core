#!/usr/bin/env python3
"""Differenziale eseguibile: la stessa stanza, tre regole, tre verdetti (studio 25/07/2026).

PERCHE' ESISTE
    Le interviste sostenevano che il vincolo vero e' la regola LOCALE, non il calcolo nazionale.
    Lo studio su documenti pubblici (research/DIVERGENCE_STUDY_LOCAL.md) lo ha confermato su
    testo normativo primario. Questo script converte quella conclusione in aritmetica eseguibile:
    dato UN disegno, calcola la superficie accreditata e il verdetto sotto tre regimi.

    Il risultato che conta non e' "il motore sbaglia", ma: l'errore e' BIDIREZIONALE. Esiste una
    stanza che il nazionale boccia e Milano promuove, e una che il nazionale promuove e la
    Lombardia boccia. Un motore che applica in silenzio il DM 1975 fuori dal suo dominio non e'
    conservativo: e' semplicemente non informato su dove si trova l'edificio.

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


@dataclass
class Locale:
    """Un locale e la sua finestra, come li leggerebbe un tecnico dal disegno."""
    nome: str
    superficie_pavimento_m2: float
    profondita_m: float               # dalla parete finestrata alla parete opposta
    larghezza_finestra_m: float
    altezza_finestra_m: float         # luce architettonica (vuoto di progetto)
    quota_davanzale_m: float          # dal pavimento al bordo inferiore del vuoto
    superficie_apribile_m2: float     # anta netta apribile (al netto dei telai)
    aggetto_sovrastante_m: float = 0.0   # balcone/veletta sopra la finestra (0 = nessuno)
    parete_a_sud: bool = False           # entro +/-60 gradi da sud

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
                    coeff_ombra: float) -> tuple[float, str]:
    """Porzione superiore in ombra d'aggetto: alta p = L/2, accreditata a `coeff_ombra`."""
    if loc.aggetto_sovrastante_m <= soglia_aggetto_m:
        return superficie_utile_m2, ""
    p = loc.aggetto_sovrastante_m / 2.0
    base_utile = max(loc.quota_davanzale_m, 0.60)
    altezza_utile = max(0.0, loc.quota_architrave_m - base_utile)
    h_in_ombra = min(p, altezza_utile)
    a = h_in_ombra * loc.larghezza_finestra_m          # porzione in ombra
    b = superficie_utile_m2 - a                        # porzione libera
    return b + coeff_ombra * a, (f"aggetto {loc.aggetto_sovrastante_m:.2f} m: p = L/2 = {p:.2f} m, "
                                 f"{a:.2f} m2 accreditati a {coeff_ombra:.2f}")


def dm1975(loc: Locale) -> Esito:
    """Nazionale: apribile >= 1/8. La norma non definisce la superficie: si usa l'apribile."""
    richiesta = loc.superficie_pavimento_m2 / 8.0
    return Esito("DM 1975 art. 5 (nazionale)", loc.superficie_apribile_m2, richiesta,
                 loc.superficie_apribile_m2 >= richiesta,
                 "superficie finestrata APRIBILE (anta netta)")


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
    richiesta = loc.superficie_pavimento_m2 / 8.0
    return Esito("RLI Codogno art. 3.4.10", utile, richiesta, utile >= richiesta,
                 "apertura finestrata meno fascia < 60 cm", nota_aggetto)


REGIMI = (dm1975, milano, codogno)


def _fmt(e: Esito) -> str:
    if e.conforme is None:
        esito = "NON SANABILE"
    else:
        esito = "conforme" if e.conforme else "VIOLAZIONE"
    acc = f"{e.superficie_accreditata_m2:.2f}" if e.superficie_accreditata_m2 is not None else "  -"
    req = f"{e.superficie_richiesta_m2:.2f}" if e.superficie_richiesta_m2 is not None else "  -"
    return f"  {e.regime:<28} {acc:>6} m2 su {req:>6} m2 richiesti  ->  {esito}"


def confronta(loc: Locale) -> list[Esito]:
    esiti = [r(loc) for r in REGIMI]
    print(f"\n{loc.nome}")
    print(f"  pavimento {loc.superficie_pavimento_m2:.1f} m2, profondita' {loc.profondita_m:.1f} m; "
          f"finestra {loc.larghezza_finestra_m:.2f} x {loc.altezza_finestra_m:.2f} m "
          f"(davanzale {loc.quota_davanzale_m:.2f} m), apribile {loc.superficie_apribile_m2:.2f} m2"
          + (f", aggetto {loc.aggetto_sovrastante_m:.2f} m" if loc.aggetto_sovrastante_m else ""))
    for e in esiti:
        print(_fmt(e))
        if e.note:
            print(f"      ({e.note})")
    verdetti = {e.conforme for e in esiti}
    if len(verdetti) > 1:
        print("  >>> I VERDETTI DIVERGONO sullo stesso disegno.")
    return esiti


def main() -> int:
    print("=" * 78)
    print("DIFFERENZIALE: stessa stanza, tre regole (dimostrazione, non codice di produzione)")
    print("=" * 78)

    casi = [
        Locale("CASO 1 - il nazionale BOCCIA, Milano PROMUOVE",
               superficie_pavimento_m2=20.0, profondita_m=4.0,
               larghezza_finestra_m=1.30, altezza_finestra_m=2.00, quota_davanzale_m=0.90,
               superficie_apribile_m2=1.70),
        Locale("CASO 2 - il nazionale PROMUOVE, la Lombardia BOCCIA (portafinestra)",
               superficie_pavimento_m2=14.0, profondita_m=3.5,
               larghezza_finestra_m=0.90, altezza_finestra_m=2.20, quota_davanzale_m=0.00,
               superficie_apribile_m2=1.98),
        Locale("CASO 3 - camera sotto un balcone, parete a NORD",
               superficie_pavimento_m2=24.0, profondita_m=5.0,
               larghezza_finestra_m=1.60, altezza_finestra_m=2.10, quota_davanzale_m=0.80,
               superficie_apribile_m2=2.20, aggetto_sovrastante_m=2.00, parete_a_sud=False),
        Locale("CASO 3-bis - LA STESSA CAMERA sulla facciata opposta (a sud)",
               superficie_pavimento_m2=24.0, profondita_m=5.0,
               larghezza_finestra_m=1.60, altezza_finestra_m=2.10, quota_davanzale_m=0.80,
               superficie_apribile_m2=2.20, aggetto_sovrastante_m=2.00, parete_a_sud=True),
        Locale("CASO 4 - stanza profonda: Milano non la ammette a nessuna dimensione",
               superficie_pavimento_m2=36.0, profondita_m=12.0,
               larghezza_finestra_m=2.00, altezza_finestra_m=2.20, quota_davanzale_m=0.90,
               superficie_apribile_m2=5.00),
    ]
    divergenti = 0
    for loc in casi:
        esiti = confronta(loc)
        if len({e.conforme for e in esiti}) > 1:
            divergenti += 1

    print("\n" + "=" * 78)
    print(f"RISULTATO: {divergenti} casi su {len(casi)} in cui lo stesso disegno riceve verdetti "
          f"diversi\n           a seconda della sola giurisdizione.")
    print("\nCONSEGUENZA: l'errore e' bidirezionale (falsi fail E falsi pass), quindi applicare")
    print("il DM 1975 fuori dal suo dominio non e' una scelta conservativa: e' una scelta non")
    print("informata. La giurisdizione non e' un raffinamento, e' un ingresso mancante.")
    print("\nAVVERTENZA: queste codifiche sono una lettura dei testi citati in")
    print("research/DIVERGENCE_STUDY_LOCAL.md, non verificate da un tecnico ne' da un ufficio")
    print("comunale. Dimostrano che la divergenza esiste; non decidono nessuna pratica.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
