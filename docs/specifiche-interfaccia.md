# Interfaccia e flussi aggiornati

Richiesta dell'utente del 14 ottobre 2026. Queste specifiche aggiornano la prima
interfaccia: la piattaforma copre **scale mobili e ascensori**. DynamoDB rimane
il database scelto. La demo privata permette di provare i nuovi flussi; accesso,
moderazione, conservazione delle foto e confronto ufficiale sono dimostrativi.

## Identità visiva e pagine

- Blu desaturato `#263f63` e giallo caldo `#e8c66b`, con sfondi chiari e testi
  leggibili. Richiamo cromatico a GTT senza usare il marchio o dichiarare affiliazione.
- Landing `/`: finalità civica del servizio, percentuale di impianti osservati
  funzionanti e percorso diretto alla panoramica senza accesso.
- Home `/home/` aperta anche agli ospiti: overview di più stazioni, impianti e
  stati per singolo impianto, ricerca/filtri e stream di segnalazioni. Le altre
  statistiche e il confronto GTT/community si sbloccano dopo l'accesso.
- Pulsante giallo ben visibile **Invia una segnalazione**, anche su mobile.
- Pagine `/segnala/`, `/proponi/` e `/moderazione/`, con ritorno alla panoramica.

## Segnalazione

Accesso obbligatorio. Stazione, impianto preciso e stato osservato sono richiesti.
L'elenco degli impianti dipende dalla stazione selezionata e comprende entrambi i
tipi: `scala_mobile` e `ascensore`. Foto e descrizione sono facoltative. Il modulo
offre il percorso **Non trovi l'impianto? Proponilo al censimento**.

Nella demo, l'invio aggiorna lo stream e la proiezione corrente e conserva autore,
momento osservato e momento registrato. La foto viene controllata, ridimensionata
e ricodificata in JPEG, senza conservare il file originale. Restano i limiti
proposti di 5 MB e 20 megapixel. La foto pending non viene mostrata nello stream:
la revisione fotografica del moderatore è distinta dalla segnalazione.

Nell'app AWS il server dovrà verificare associazione stazione/impianto, identità,
idempotenza, autorizzazioni e file reali. I controlli eseguiti nel browser non
costituiscono sicurezza server. Upload autorizzato S3, elaborazione privata e
pubblicazione dopo moderazione restano da integrare.

## Proposta di nuovo impianto

Accesso obbligatorio. Richiedere stazione, tipo, nome/identificazione e posizione
con percorso servito; permettere foto e descrizione facoltative. Dopo l'invio:

1. La proposta resta `pending`, separata dagli impianti confermati.
2. L'autore vede che è in attesa di approvazione.
3. Il moderatore verifica posizione, identificazione ed eventuali duplicati.
4. Solo l'approvazione aggiunge un'identità interna stabile al censimento.
5. Un rifiuto conserva proposta e decisione senza pubblicare l'impianto.

Non attribuire al nuovo impianto uno stato di funzionamento in assenza di una
segnalazione: la prima scheda indica **Senza dati**. L'eventuale foto segue una
revisione separata, possibile soltanto dopo l'approvazione dell'impianto.

Il ruolo del proprietario/moderatore nella versione AWS sarà controllato sul
server dall'identità autenticata, con aggiornamento condizionato della proposta,
creazione del censimento e audit. La scelta di persona della demo non equivale a
questa autorizzazione reale.

## Fonti e dati dimostrativi

La scheda di confronto mantiene due colonne distinte e segnala le differenze.
La demo visualizza esempi **esplicitamente etichettati**, senza attribuirli a un
report GTT realmente acquisito. La fonte è collegata; il suo report riguarda
manutenzioni straordinarie: l'assenza di un impianto non dimostra funzionamento.

I nomi Porta Nuova, Porta Susa, Re Umberto e Vinzaglio sono stati verificati su
fonti GTT. Le posizioni, gli impianti e gli stati del campione sono sintetici,
con ID `demo-*`, senza gestori o identificativi ufficiali inventati.

Fonti verificate il 14 ottobre 2026: [aggiornamenti GTT](https://www.gtt.to.it/cms/en/19-linee-e-orari/urbana/12186-metropolitana-aggiornamento-ascensori-e-scale-mobili)
e [percorso Metro M1](https://www.gtt.to.it/cms/percorari/urbano?bacino=U&linea=METRO&percorso=M1R4&verso=Di&view=percorso).

## Codice e prove

Il frontend conserva la modalità di prova del backend Python quando
`PUBLIC_BROWSER_DEMO=false`; con `true` usa i nuovi flussi dimostrativi di
`Platform.svelte` e `platform-demo.ts`. La copia pubblicata con Sites è sempre
una demo browser, in una repository separata con l'identità Sites già esistente.
Nessuna nuova risorsa AWS viene creata per questa iterazione.

I dati sono nella sessione del browser. Il collaudo
`scripts/platform_browser_smoke.py` verifica accesso richiesto, campi obbligatori,
foto valide/errate, stream, proposta non pubblicata, approvazione e rifiuto,
moderazione fotografica distinta, ruoli simulati, ricaricamento e layout mobile.

Prossimi passi del piano: estendere i contratti API al tipo impianto, aggiungere
descrizione e riferimenti a foto, implementare proposte e decisioni in DynamoDB,
collegare i nuovi flussi al login Cognito e alle acquisizioni GTT reali. Il nuovo
tipo è un attributo del documento; non richiede rinominare ID pubblici già esistenti.

## Esiti del collaudo dell'iterazione

Controllo Svelte/TypeScript senza errori o warning e build statica riusciti sia
nel progetto Sites sia nel frontend della repository principale. Il collaudo
Chromium è riuscito per tutti i flussi elencati, con viewport di 375, 768 e 950 px
senza overflow orizzontale. Foto in attesa non visibili nello stream, rifiuti
conservati nell'audit, nuovo impianto pubblicato soltanto dopo approvazione e
assenza di stato operativo inventato per l'impianto appena aggiunto.

Questi esiti riguardano la demo browser. Login, autorizzazioni, moderazione,
DynamoDB e acquisizioni GTT reali rimangono da integrare e collaudare su AWS.

La nuova versione è stata pubblicata privatamente con Sites sullo stesso URL
della demo. Commit della fonte Sites: `fe202620fd25ac13c6a43b384eb2b8695561d632`.
La risposta del servizio di pubblicazione ha confermato esito riuscito.

## Tipografia e statistiche

Font dei testi e delle etichette leggermente maggiorati. Overview con quattro
riquadri: totale degli impianti, quota osservata funzionante, quota con criticità
e quota da verificare. Numeri e percentuali sono prioritari, con etichette brevi
e conteggi espliciti (`6 su 9`).

Le percentuali sono arrotondate all'intero e calcolate sul totale degli impianti
del campione, usando l'ultima osservazione per impianto. Gli impianti senza
osservazioni sono inclusi tra quelli da verificare. Non rappresentano
disponibilità temporale o attendibilità. Con campione vuoto compare un trattino.

Verificati il campione iniziale (9 impianti: 67%, 22%, 11%), l'aggiunta di un
impianto senza dati (10 impianti: 60%, 20%, 20%), il campione vuoto e il layout
a 375, 768, 950 e 1100 px. Check Svelte/TypeScript senza errori o warning; build
statica riuscita.

Aggiornamento pubblicato con esito riuscito sullo stesso URL privato.
Commit Sites: `a963d7fbf967e92f64539e952a58a1b0fa02ac63`.

## Home con tre indicatori prioritari

Questa iterazione sostituisce i quattro riquadri precedenti con tre blocchi,
nell'ordine richiesto:

1. Percentuale di impianti osservati funzionanti, a tutta larghezza. Il pulsante
   apre e chiude il dettaglio, anche da tastiera: conteggi per stato e stazione,
   copertura e metodo. Il denominatore resta il totale del campione; le quote
   non descrivono la disponibilità continua nel tempo.
2. Allineamento GTT/community: stati esattamente identici diviso gli impianti
   con stato verificabile in entrambe le fonti. Guasto e manutenzione restano
   stati distinti. Assenza di fonte o `non_verificabile` escludono l'impianto
   dal confronto. Sono mostrati conteggio confrontabile, differenze e impianti
   esclusi; in assenza di confronti la percentuale è un trattino.
3. Banner con selezione tra **Nuovi fermi** e **Streak**. I nuovi fermi hanno
   la prima osservazione della sequenza corrente nelle ultime 24 ore. In assenza
   di uno stato precedente si parla di primo fermo osservato. Le streak sono
   almeno due osservazioni consecutive di guasto/manutenzione nello storico
   disponibile. Una segnalazione di funzionamento o non verificabilità interrompe
   la sequenza; un ritorno al funzionamento rimuove l'impianto dal banner.
   Le righe aprono la scheda dell'impianto.

Gli eventi sono ordinati per momento osservato, con registrazione come spareggio.
Le streak contano osservazioni, senza dedurre durata o continuità di un guasto.
Il confronto GTT è ancora etichettato come demo e utilizza soltanto esempi fittizi:
non è una misura dell'allineamento del sito GTT reale. Il campione iniziale ha
67% osservati funzionanti e 0% di stati identici su 3 confrontabili, con 6 esclusi.

Il collaudo `scripts/platform_overview_smoke.py` verifica accordion da tastiera,
scheda e link di dettaglio, fonti mancanti/non verificabili, campione vuoto,
sequenze interrotte, ritorno al funzionamento, fermi oltre 24 ore, ordine distinto
di osservazione/registrazione e aggiornamento immediato dopo gli invii nella demo.
Verificato il layout chiuso ed espanso a 375, 768, 950, 1100 e 1440 px senza
overflow orizzontale. Le verifiche restano riferite alla demo browser.

Check Svelte/TypeScript senza errori o warning e build statica riusciti nel
progetto Sites e nel frontend principale. Aggiornamento pubblicato sullo stesso
URL privato con esito `succeeded`; commit della fonte Sites:
`b683ca70af0353703c4197b49ebc189da85e18c5`.

## Landing e panoramica senza accesso

La stessa scheda di funzionamento (`AvailabilityCard.svelte`) è presente nella
parte iniziale della landing e come prima statistica della home. È leggibile
senza accesso e si espande con conteggi di funzionamento per stazione e metodo.
I conteggi secondari di criticità e non verificabilità si mostrano dopo l'accesso.

La navigazione verso `/home/` non apre il login. Stazioni, ricerca, filtri,
schede degli impianti e stream restano consultabili. Allineamento GTT, banner
fermi/streak e confronto dettagliato usano `StatisticGate.svelte`: per gli ospiti
compaiono anteprime grafiche sfocate e un pulsante **Accedi e sblocca**. I valori
riservati non vengono renderizzati nel DOM anonimo; le anteprime sono inerti e
escluse dai lettori di schermo. Dopo l'accesso dalla home lo sblocco avviene nella
stessa pagina, mantenendo filtri e posizione. Il logout ripristina le anteprime
e nasconde le proposte personali senza chiudere la panoramica pubblica.

Segnalazioni, proposte e moderazione conservano l'accesso obbligatorio. Un link
diretto a una pagina riservata apre il login sulla home; annullarlo lascia una
home consultabile. Completare l'accesso riprende il percorso richiesto, con la
moderazione sempre riservata al ruolo moderatore simulato.

Il collaudo `scripts/platform_public_home_smoke.py` copre landing, accesso diretto
alla home, dettaglio pubblico della prima statistica, riquadri sfocati senza
valori nel DOM, contributi protetti, sblocco, ricaricamento, logout con una proposta
pendente e layout mobile. I collaudi esistenti delle statistiche e dei flussi
di contribuzione sono mantenuti. Questi controlli riguardano la demo browser:
la versione AWS dovrà applicare il controllo di accesso alle statistiche riservate
nel backend, oltre a mantenere le verifiche server per scritture e moderazione.
L'audience privata dell'hosting Sites rimane quella già configurata.

Check Svelte/TypeScript senza errori o warning e build statiche riusciti in
entrambi i frontend. Superati i collaudi della home pubblica, delle statistiche
e dei flussi completi di segnalazione/proposta/moderazione. Corrette la chiusura
rapida del login con Esc e la larghezza del menu ospite a 375 px. Pubblicazione
Sites riuscita (`succeeded`) sullo stesso URL; commit della fonte:
`3dcfb4431ace28a88602ef2581c542458c27c379`.


## Collegamento alle API — 15 ottobre 2026

Il frontend della repository usa ora gli endpoint Python con
`PUBLIC_BROWSER_DEMO=false`. La landing mantiene la stessa interfaccia; la home
legge censimento e stati correnti da `/api/overview` e lo stream paginato da
`/api/feed`. La prima percentuale usa il totale del censimento; informazioni
mancanti restano distinte dagli impianti funzionanti. Il confronto e gli incidenti
usano le statistiche server, dopo login. Le schede protette non sono scaricate né
renderizzate per un visitatore anonimo.

Segnalazioni, foto, proposte e decisioni passano alle API. Il moderatore indica una
motivazione privata; il server verifica ruolo, versione e stato corrente. Il login
Cognito usa PKCE e torna alla pagina richiesta; identità simulate sono disponibili
solo per demo browser oppure con flag esplicito su backend non AWS.

Il collaudo browser copre DynamoDB/S3 emulati, riavvio API, una nuova sessione,
ritentativo di una risposta persa senza duplicazione e foto private/pubbliche.
Il percorso OAuth è verificato con endpoint intercettati; Cognito reale resta da
collaudare dopo l’attivazione AWS. Questa modifica non ripubblica la demo Sites.
Dettagli e comandi in [frontend-collegato.md](frontend-collegato.md).
