# Kit di contatto — design partner (R1)

Scopo: trovare 3–5 professionisti (geometri, architetti, ingegneri, BIM manager) per
interviste da 30 minuti + eventuale pilota. Questo file contiene il messaggio pronto da
inviare e la traccia d'intervista, così il vincolo "farei le interviste se avessi le persone"
si riduce a: inviare N messaggi.

## Canali: regole di selezione

**Inbound (il contatto nel README)** — criteri: credibile per uno sconosciuto, a basso
attrito, letto ogni giorno. Usare un alias dedicato su dominio proprio (es. `acc@…` /
`pilot@…`), MAI un indirizzo con brand estraneo al progetto; quando il repo è pubblico,
aggiungere un issue template GitHub "Pilot / design partner" come secondo canale.

**Outbound (chi firma il messaggio)** — le persone rispondono alle persone: inviare dal
proprio nome (email personale professionale o LinkedIn), mai da un alias di progetto.
Per i profili BIM-attivi, il DM LinkedIn tende a rendere più dell'email (il profilo È la
verifica di credibilità).

**Selezione dei destinatari — scala di calore (dall'alto):** (1) rete personale e contatti
universitari (relatori/dipartimenti AEC); (2) LinkedIn filtrato per EVIDENZA — chi pubblica
di Salva Casa / CILA / IFC si è auto-selezionato come raggiungibile; (3) email pubbliche
degli studi, scrivendo a una persona nominata con un riferimento specifico; (4) come ultima
istanza i registri pubblici (Albo / INI-PEC) — la PEC funziona ma è canale formale: solo
individuale, mai in massa.

**Disciplina (non è parere legale):** contatti individuali, manuali, in piccolo numero;
chi sei + perché proprio loro + un "no grazie" facile. Niente liste, tracking o automazioni.

**Mix dei 3–5 intervistati (screening: tratta pratiche di abitabilità? riceve/produce IFC?):**
2 geometri/piccolo studio ad alto volume (la domanda-report R1) · 1 architetto (agibilità,
terminologia) · 1 BIM manager (la realtà dei Qto/IFC — il problema "Duplex") · 1 volutamente
NON-BIM tradizionalista (il confine di adozione: "esporta l'IFC con le quantità" è un
dealbreaker?). Chiudere sempre con la domanda snowball.

## Dove cercare (in ordine di resa attesa)

1. Contatti diretti / colleghi di corso che lavorano in studi tecnici (il canale più caldo).
2. Ordini e collegi locali (Collegio Geometri, Ordine Architetti/Ingegneri) — eventi BIM.
3. Community: gruppi LinkedIn/Telegram italiani su BIM, openBIM, IFC; forum ArchiCAD/Revit IT.
4. Studi che pubblicano di CILA/SCIA/Salva Casa su LinkedIn (cercare "Salva Casa" + "pratica").

## Messaggio pronto (adattare il saluto)

> Buongiorno [Nome],
>
> sto sviluppando uno strumento open-source che verifica automaticamente i requisiti di
> abitabilità (altezze minime DM 5/7/1975, rapporto aeroilluminante 1/8, deroga Salva Casa)
> direttamente dal modello IFC — in locale, senza caricare il modello da nessuna parte.
>
> La particolarità: quando un dato non è misurabile dal modello, lo strumento risponde
> "non determinabile" invece di indovinare — pensato per chi poi firma la pratica.
>
> Cerco 3–5 professionisti per un confronto di 30 minuti (video o telefono): mi interessa
> capire come verificate oggi questi requisiti e cosa dovrebbe contenere un report perché
> sia davvero utile in una pratica. Non vendo nulla: il motore è gratuito e open-source,
> e in cambio del suo tempo le mostro volentieri la verifica su un suo modello IFC.
>
> Le andrebbe la settimana prossima?

## Traccia d'intervista (30 min — R1 del piano di ricerca)

1. **Contesto (5')** — che pratiche tratta (CILA/SCIA/agibilità/Salva Casa)? quanti modelli
   IFC reali vede? chi produce i modelli?
2. **Processo attuale (10')** — come verifica oggi altezze e rapporto aeroilluminante? quanto
   tempo costa? dove sbaglia più spesso? che software usa (ACCA? Solibri? nulla)?
3. **Il report (10' — la domanda chiave)** — mostrare il report HTML di esempio
   (`sandbox/data/AC20-FZK-Haus_report.html`). Cosa manca perché lo allegherebbe a una
   pratica con la sua firma? Come reagisce a "non determinabile"? (fiducia o fastidio?)
4. **Chiusura (5')** — proverebbe il tool su un suo modello? cosa lo bloccherebbe
   (formato, privacy, tempo)? conosce altri 2 colleghi da sentire? (snowball)

## Regole (disciplina delle affermazioni — ADR-010)

- Mai promettere certificazioni, garanzie o valore legale. Copertura onesta: oggi 2 regole
  del DM 1975 + Salva Casa; il pacchetto "Lombardia" è un mock dimostrativo, non legge.
- Niente prezzi (nessuna offerta commerciale prima del parere legale).
- Annotare le parole ESATTE usate dall'intervistato per i concetti (terminologia → R3).
