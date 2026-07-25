# ADR-021 (PROPOSTA) — la giurisdizione come ingresso dichiarato

Status: **RESPINTA IN QUESTA FORMA** (revisione avversariale del 25/07/2026, esito
`REWRITE_PROPOSAL`). **Non implementata. Non appesa a `docs/decisions.md`**: la catena registra
decisioni prese, e questa non lo è.

La v1 della proposta è conservata integralmente in fondo (§ APPENDICE) perché l'errore che
conteneva è il reperto più utile prodotto in questa sessione, e cancellarlo sarebbe esattamente
il tipo di igiene retrospettiva che il progetto rifiuta.

---

## 0. Cosa è successo, in una frase

La proposta si fondava su un differenziale eseguibile che confrontava i regolamenti comunali con
**codice che non esiste**. Rieseguito contro il numeratore che il motore usa davvero, l'argomento
centrale della proposta si dissolve, e sotto ne emerge un difetto diverso, più piccolo e più
facile da correggere.

## 1. Il reperto che uccide la v1 (verificato di persona, non solo riportato)

La v1 diceva: *l'errore è bidirezionale, quindi applicare il DM fuori dominio non è prudenza, è
disinformazione*. Quella frase era l'unico ponte fra «limitazione» e «difetto».

**Errore di metodo.** `research/divergence_demo.py` (v1) dava alla gamba nazionale il numeratore
`superficie_apribile_m2`, l'anta netta. Il motore non calcola mai un'anta netta: il numeratore
aeroilluminante è `cons = min(OverallHeight × OverallWidth, Qto_WindowBaseQuantities.Area)`
(`sandbox/checker.py:347-355` e `:704`), cioè il **vano lordo**.

**Errore aritmetico.** Due dei cinque casi dichiaravano finestre fisicamente impossibili: CASO 4
un'anta di 5,00 m² dentro una luce di 4,40 m² (**113,6%** del foro), CASO 2 un'anta pari al
**100,0%** della propria luce (telai a spessore zero). Erano **esattamente** i due casi che
producevano la direzione «il nazionale promuove, la Lombardia boccia».

**Riesecuzione (v2, `python research/divergence_demo.py`).** Cambiando solo il numeratore e
imponendo una guardia di possibilità fisica:

| | v1 (anta netta) | v2 (vano lordo, il motore vero) |
|---|---|---|
| casi divergenti | 4/5 | 4/5 *(insieme diverso)* |
| motore promuove / comune boccia | 2 | **3** |
| motore boccia / comune promuove | 2 | **0** |

Il conteggio «4 su 5» sopravvive per coincidenza, con casi diversi. **La bidirezionalità no.**
L'errore è **a senso unico**: il motore promuove ciò che il comune boccia, mai il contrario.

*(Nota di precisione: la revisione avversariale sosteneva anche che il conteggio 4/5 crollasse.
Non è vero, e l'ho verificata invece di ripeterla. Crolla la direzione, non il numero.)*

## 2. Il difetto che resta, e che è reale

Non è la giurisdizione. È che **il motore ha scelto in silenzio una convenzione di misura che
nessuna fonte nazionale gli dà.**

Il DM 5/7/1975 art. 5 dice «superficie finestrata apribile» e **non definisce come si misura**.
Il motore misura il vano lordo, telai inclusi, senza detrazione della fascia bassa. È una scelta
legittima e difendibile, ma è **una scelta**, e non è dichiarata da nessuna parte: né nel report
HTML, né nella riga di verdetto della CLI, né nell'inviluppo dell'API. Questo difetto esiste
**anche restando interamente dentro l'Italia**, e la giurisdizione non c'entra.

Ed è la direzione peggiore in cui sbagliare: la permissività sistematica produce «conforme» su
stanze che non lo sono.

## 3. Perché il rimedio proposto era sbagliato (le tre obiezioni che ho verificato)

1. **Avrebbe azzerato il prodotto.** Il motore ha esattamente due controlli
   (`checker.py:836-839`: `acc:heightM`, `acc:aeroRatio`) ed **entrambi** sono sensibili alla
   giurisdizione secondo il nostro stesso studio. `SpaceFinding.compliant` (`checker.py:269-280`)
   collassa a `None` se un controllo applicabile è `None`. Con la giurisdizione non dichiarata,
   **ogni** stanza esce non determinabile: sui fixture spediti, 89 righe determinate diventano 0.
   Il §4 della v1 la chiamava «nessuna rottura» perché la firma dell'API sopravvive. Sopravvive
   la firma, non il prodotto.
2. **Non si poteva costruire dove la proposta lo metteva.** `orchestrator._tri` restituisce `None`
   **solo** via `SH.MinCountConstraintComponent` e solleva su qualunque altro componente;
   `load_shacl_shapes` rifiuta `sh:sparql`. Produrre «non determinabile per regola ignota» avrebbe
   richiesto un quarto passaggio Python dopo `_shacl_verdict`, cioè **rimettere logica giuridica
   dentro `checker.py`**, disfacendo in parte ADR-008/009. Chirurgia sulla chiave di volta,
   presentata come un parametro.
3. **Il criterio di accettazione avrebbe costretto il gate a certificare una menzogna.** Ho letto
   le georeferenze dei tre fixture congelati: AC20-FZK-Haus `IFCSITE` 49°6'1" N, 8°26'11" E =
   **Karlsruhe**; AC20-Institute 49°9' N, 8°43' E = **Germania**; Duplex 41°52'27" N, −87°38'21" W
   più `IFCPOSTALADDRESS(...,'Chicago','','','IL')` = **Chicago**. Il §7 della v1 imponeva di
   dichiarare l'ambito italiano su due edifici tedeschi e uno americano. Una ADR il cui scopo è
   rendere oneste le dichiarazioni di giurisdizione avrebbe iniziato cablandone una falsa nel
   corpus di regressione, per sempre.

Aggiungo un difetto **della revisione stessa**, non della proposta: la sua prescrizione chiede di
cambiare intestazione e badge del report HTML, e contemporaneamente vieta di toccare il layout del
report finché P0-A non ha risposto. Le due cose non stanno insieme. Vince il divieto: il report
campione è già partito, cambiarlo a metà volo distrugge l'unico test in corso.

## 4. Cosa sopravvive della v1

* **L'osservazione di apertura è corretta**: `checker.run()` non ha, in nessun punto, il concetto
  di dove si trova l'edificio, e nessuna delle tre superfici dichiara il dominio di validità.
* **Il rifiuto di dedurre la giurisdizione dall'`IfcSite`** è giusto, e va registrato come
  decisione permanente perché non venga riaperto. Le georeferenze di §3.3 lo confermano al volo.
* **Lo studio di divergenza regge sui suoi termini.** Firenze «al lordo dei telai» e il conflitto
  Milano 150 cm / Codogno 120 cm sono verbatim, puliti e cambiano i verdetti. La divergenza locale
  è reale; ciò che era sbagliato è **dove** la proposta la collocava e **quanto** diceva costasse.

## 5. Cosa NON si costruisce, e fino a quando

Nessuna di queste cose finché non rientrano P0-A e P0-B (spediti il 25/07, scadenza una settimana):

* astensione condizionata alla giurisdizione (§3.3 della v1);
* `NotCertifiableError` su giurisdizione fuori ambito (§3.4);
* qualunque parametro giurisdizione obbligatorio su CLI o API — imporre un campo con **un solo**
  valore accettato non è onestà, è cerimoniale;
* qualunque rule-pack comunale reale: bloccato al caricamento e non validato da nessuno;
* qualunque nuovo `acc:` path o estrattore (profondità, davanzale, aggetto, azimut, media
  ponderata): ADR-004 ha già sondato e declinato le grandezze derivate dalla geometria;
* qualunque modifica al layout del report finché P0-A non ha risposto.

## 6. Cosa decide P0, e perché aspettare non è procrastinare

**P0-A (Campagna, report campione con una riga «non determinabile»)** risponde alla domanda che il
§6 della v1 ammetteva aperta: un tecnico vuole l'astensione, o un verdetto nazionale chiaramente
etichettato come tale? Se vuole il secondo, §3.2-3.3 sono morti e la correzione è solo la
dichiarazione della convenzione.

Su questo c'è già un indizio contrario alla v1, agli atti: Nigra, `research/interviews/LOG.md:16`,
[14:30-14:46] — *«si può fare un check generico che parte dalla legge nazionale e dà risposte
sulla legge nazionale, quello lo attenzionano»*, codificato FOR. Non è una risposta diretta alla
domanda sull'astensione, ed è onesto dire che è adiacente e non equivalente; ma punta dall'altra
parte rispetto alla proposta.

**P0-B (Beltrami, confronto cieco su una pratica reale)** dice (a) se le codifiche Milano/Codogno
sono vicine al vero, cosa che la v1 stessa ammetteva ignota, e (b) se il dolore vero è la
giurisdizione o l'altezza media del sottotetto, il candidato che sia Nigra sia la pratica di
Beltrami indicano. **Implementare §3 prima della risposta rende P0-B non rispondibile per
costruzione**: il verdetto promesso per iscritto diventerebbe «non determinabile» o uscita 2, che
un tecnico non distingue da «rotto», e il progetto brucerebbe la sua unica pista milanese calda.

## 7. Le due verifiche a costo zero che vanno chiuse comunque

* **La vigenza del testo milanese** è ancora inferita dal frontespizio del PDF (il sito del comune
  ha risposto 403). La v1 la chiamava «la verifica più economica ancora da fare» ed era ancora da
  fare mentre la v1 veniva scritta.
* **Le estrazioni dei testi non sono nel repo** (RE Milano, Codogno, Limbiate, Firenze, Torino,
  Rimini). `CLAUDE.md` impone una URL di fonte per ogni affermazione di ricerca: finché non sono
  committate con URL, data di prelievo e hash, il divisore 1/8 di Codogno e il tetto di profondità
  3,5× non sono verificabili da nessuno, me compreso.

---

# APPENDICE — testo integrale della v1 (respinta)

> Conservato verbatim. Le affermazioni marcate qui sotto sono quelle falsificate sopra.

## 1. Il difetto (osservazione, non interpretazione)

`checker.run()` non ha, in nessun punto, un concetto di **dove si trova l'edificio**: accetta un
`.ifc`, un `.ttl` opzionale e delle soglie, e in assenza di indicazioni applica il DM 5/7/1975.
Il verdetto viene emesso senza che nulla, nel motore o nel report, dichiari che quel verdetto
vale solo dentro un dominio normativo preciso.

Evidenza raccolta su **testo normativo primario pubblico** (`research/DIVERGENCE_STUDY_LOCAL.md`)
e convertita in aritmetica eseguibile (`research/divergence_demo.py`, 4 casi su 5 divergenti):

* **Milano, RE art. 105**: rapporto **1/10** (non 1/8), misurato sulla *luce architettonica*
  detratta la fascia sotto i 60 cm; 1/8 solo nella fascia profonda 2,5x–3,5x l'architrave; oltre
  3,5x **nessuna dimensione di finestra rende il locale conforme**; aggetti > 150 cm derano la
  porzione in ombra a 1/3, oppure 1/2 se la parete guarda a sud entro ±60°.
* **Milano, RE art. 95**: altezza **media** con minimo assoluto **2,10 m**, e ribassamenti
  strutturali/impiantistici esclusi dal calcolo fino a 1/3 della superficie.
* **RLI Codogno art. 3.4.10 / RLI Limbiate art. 3.4.11**: stessa costruzione dell'ombra ma soglia
  aggetto **120 cm** (contro i 150 di Milano — due strumenti lombardi che divergono *tra loro*), e
  base di misura dichiarata come **vuoto architettonico, espressamente non l'anta apribile**.
* **Firenze, RE art. 41**: mantiene 1/8 ma misura **«al lordo dei telai»**.

Il DM 1975 art. 5 dice «superficie finestrata apribile» e **non definisce come si misura**: ogni
testo locale che colma quella lacuna sceglie una convenzione *lorda*. Qualunque convenzione il
motore abbia implicitamente adottato, non può citare una fonte nazionale a sostegno.

> **[FALSIFICATO — §1 sopra]** **La conseguenza che rende questo un difetto e non una limitazione:**
> l'errore è **bidirezionale**. Il differenziale mostra sia una stanza che il nazionale boccia e
> Milano promuove, sia una che il nazionale promuove e la Lombardia boccia. Un motore che applica
> il DM fuori dal suo dominio non è prudente: è **non informato**, e non può nemmeno essere difeso
> come conservativo.

**E contraddice il principio su cui il progetto è costruito.** L'intervistato che più ha apprezzato
il motore lo ha detto così: *«se l'elemento non c'è è cruciale che si dica l'elemento manca, cioè
non inventarlo, non integrarlo, non calcolarlo diversamente»*. Applicare in silenzio il DM 1975 a
una stanza milanese è esattamente quel fallimento, spostato dal **dato** alla **regola**.

## 2. Cosa NON è in discussione qui

* **Non si propone di spedire un pacchetto Milano o Codogno.** Le codifiche in `divergence_demo.py`
  sono una nostra lettura di testi citati, **non verificate** da un tecnico né da un ufficio
  comunale. Servono a dimostrare che la divergenza è reale; non sono pronte per decidere pratiche.
* **Non si propone di dichiarare sbagliato il baseline nazionale.** Roma (art. 40) e Torino
  (art. 77) **ricopiano il DM alla lettera**: su un locale a soffitto piano in un piano ordinario
  il motore è semplicemente corretto. E il Regolamento Edilizio Tipo 2016 standardizza a livello
  nazionale la definizione di *altezza utile*: sulle altezze la variabilità locale sta diminuendo.
  Il caos residuo è concentrato sull'**aeroilluminante**, dove la lacuna nazionale è reale.

## 3. La proposta

**La giurisdizione diventa un fatto dichiarato, e il motore rifiuta di dedurla.**

1. **Ogni rule-pack dichiara il proprio ambito** (`scope`): p.es. `IT` per il DM 1975,
   `IT-LO-Milano` per un eventuale pacchetto milanese. Il pacchetto sa a cosa si applica.
2. **La giurisdizione dell'edificio è un input dell'operatore**, esattamente come lo è già il
   regime Salva Casa: il motore non la indovina dal modello (l'`IfcPostalAddress` esiste ma è
   spesso assente o inaffidabile, e una deduzione silenziosa ricreerebbe il difetto).
3. > **[VIETATO — §5 sopra]** **Se la giurisdizione non è dichiarata**, i controlli sensibili alla
   > giurisdizione non vengono emessi come conformi o violati: diventano **non determinabili**, con
   > la motivazione esplicita («regola applicabile non determinata: il verdetto dipende dal
   > regolamento comunale»). Il report continua a mostrare **le misure**, che restano vere a
   > prescindere.
4. > **[VIETATO — §5 sopra]** **Se la giurisdizione dichiarata è fuori dall'ambito del pacchetto**,
   > il motore **rifiuta** (`NotCertifiableError`, uscita 2), invece di applicare il pacchetto per
   > approssimazione.

**Perché questa forma e non un'altra:** è la stessa ternaria che il motore già implementa,
estesa dal dato alla norma. Non introduce un concetto nuovo, ne applica uno esistente dove
mancava. E preserva il valore nei casi in cui il motore è corretto: chi dichiara `IT` ottiene
esattamente il comportamento di oggi, ma **dichiarandolo**, non subendolo.

## 4. Cosa costa

* **I controlli congelati richiedono una dichiarazione esplicita.** Le run sui tre fixture
  dovranno dichiarare l'ambito nazionale. È un cambiamento di *interfaccia*, non di verdetto: i
  numeri congelati (FZK 5/1, Institute 2/2, Duplex 0/21) devono restare identici, ed è il gate a
  doverlo dimostrare.
* **L'API e la CLI acquisiscono un parametro.** Va deciso se sia obbligatorio (rottura) o se
  l'assenza produca il non-determinabile del punto 3 (compatibile). La proposta raccomanda la
  seconda: nessuna rottura, ma nessun verdetto silenzioso.
* **Il report deve dichiarare l'ambito applicato** in testata, accanto alle soglie.

## 5. Alternative considerate e scartate

* **Dedurre la giurisdizione dall'IFC** (`IfcSite.SiteAddress`): ricrea il difetto in forma più
  subdola, perché un indirizzo assente o errato produrrebbe un verdetto sbagliato *con l'apparenza
  della verifica*. Se mai, potrà essere un suggerimento da confermare, mai una deduzione.
* **Continuare col fallback nazionale, aggiungendo un avviso nel report.** Un avviso non impedisce
  di leggere «conforme» accanto a una stanza che nel suo comune non lo è: l'errore resterebbe
  emesso, solo con una nota a piè di pagina. Il progetto ha già rifiutato questa forma di
  laundering per i dati (ADR-003/004).
* > **[RIABILITATA — la sua bocciatura si reggeva sulla bidirezionalità, che è morta]**
  > **Restringere lo scopo dichiarato a «solo DM 1975» senza altre modifiche.** È onesto ma non
  > risolve nulla: il motore continuerebbe a emettere verdetti su edifici milanesi senza sapere di
  > non poterlo fare.

## 6. Cosa resta non verificato (da dichiarare, non nascondere)

* Le codifiche Milano/Codogno **non sono validate** da un professionista né confrontate con una
  pratica reale approvata. Il test P0-B inviato il 25/07 serve esattamente a questo.
* La **vigenza** del testo milanese usato nello studio è inferita dal frontespizio del PDF (il
  sito del comune ha risposto 403): è la verifica più economica ancora da fare.
* Non sappiamo se un professionista **voglia** un verdetto non determinabile per giurisdizione
  mancante, o preferisca un verdetto nazionale etichettato. È una domanda aperta per le interviste,
  e nessuno l'ha ancora ricevuta.
  > **[PARZIALMENTE FALSO]** Nigra l'ha ricevuta in forma adiacente e ha risposto:
  > `research/interviews/LOG.md:16`.

## 7. Criterio di accettazione

> **[FALSIFICATO — §3.3 sopra: imporrebbe di dichiarare l'Italia su Karlsruhe e Chicago]**

La proposta è accettabile solo se, dopo l'implementazione:
* i tre controlli congelati restano **byte-identici** quando l'ambito nazionale è dichiarato;
* esiste un test che dimostra che, **senza** dichiarazione, i controlli sensibili alla
  giurisdizione escono non determinabili e **nessun** verdetto conforme/violazione viene emesso;
* esiste un test che dimostra il **rifiuto** quando la giurisdizione dichiarata è fuori ambito;
* il gate resta verde.
