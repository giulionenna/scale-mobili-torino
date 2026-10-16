# Scale Mobili Torino — chiavi e accessi DynamoDB

14 ottobre 2026. DynamoDB è la scelta confermata dall'utente. Questo è il disegno iniziale da verificare nella prova, non uno schema già distribuito. Gli esempi `s`, `e`, `u` e `x` rappresentano ID interni astratti; non sono identificativi di impianti reali.

## Decisioni

- Due tabelle Standard: `core` per documenti correnti e risultati derivati; `events` per evidenze e audit.
- In entrambe: chiave composta `PK` + `SK`, entrambe stringhe. Il prefisso indica il tipo del documento.
- Tre GSI iniziali: stazione, coda di moderazione, autore degli eventi. Nessun LSI.
- Capacità provisioned iniziale, dimensionata dopo la verifica della quota residua nell'account; nessuna crescita automatica oltre i limiti economici concordati.
- Query paginata o lettura puntuale per ogni funzione del sito. Scan riservate a operazioni amministrative controllate, come una migrazione, con permessi e consumo separati.

La flessibilità degli attributi non elimina la progettazione degli accessi. I tipi delle chiavi, i loro valori e il modo in cui i documenti sono raggruppati sono contratti applicativi. Aggiungere un attributo non indicizzato è semplice; cambiare l'identità fisica di un record richiede una migrazione.

## Chiavi della tabella core

| Documento | PK | SK | Note |
| --- | --- | --- | --- |
| Stazione | `CATALOG#STATIONS` | `STATION#s` | Directory piccola, ordinata per ID; nome e ordine geografico sono attributi |
| Scheda impianto | `ESC#e` | `META` | Identità stabile; stazione, gestore, posizione e verifica sono attributi |
| Stato corrente | `ESC#e` | `STATE` | Evidenze ufficiali/community/stima separate e versione della proiezione |
| Fotografia | `ESC#e` | `PHOTO#x` | Metadati privati, moderazione e riferimento S3; nessun file binario |
| Proposta di censimento | `PROPOSAL#x` | `META` | Rimane distinta dall'impianto confermato |
| Fonte monitorata | `SOURCE#x` | `META` | URL, significato della fonte e configurazione verificati |
| Contenuto archiviato | `BLOB#sha256` | `META` | Puntatore ai byte originali su S3, dimensione e tipo |
| ID ufficiale verificato | `OFFICIAL#gestore#id` | `CLAIM` | Assegnazione univoca all'impianto tramite scrittura condizionata |
| Statistica corrente | `STATS#scope#id` | `DAY#data` oppure `MONTH#mese` | Metodo/versione, evidenze, copertura e periodo nel contenuto |
| Idempotenza | `IDEMP#digest` | `WRITE` | Digest di utente e chiave richiesta, digest del contenuto, risultato e scadenza |
| Ricalcolo richiesto | `WORK#AGGREGATES` | `scope#id#periodo` | Lavoro derivato, con versione per non perdere invalidazioni concorrenti |

Ogni documento ha `entity_type`, `schema_version` e timestamp pertinenti. L'ID ufficiale è normalizzato con una regola specifica del gestore, senza alterarne arbitrariamente il significato; si conserva anche il valore originale verificato.

Un cambio di nome o stato non modifica `ESC#e`. Una rettifica dell'associazione alla stazione modifica `station_id` e gli attributi dell'indice, con un evento di audit. Le statistiche devono distinguere l'associazione registrata all'epoca da una successiva correzione verificata.

La partizione della directory stazioni è intenzionalmente piccola. Gli eventi crescenti sono distribuiti per impianto o fonte; non finiscono sotto una sola chiave globale. Immagini e originali restano su S3, mantenendo piccoli gli item DynamoDB.

## Chiavi della tabella events

| Evidenza/evento | PK | SK |
| --- | --- | --- |
| Segnalazione, conferma o rettifica | `ESC#e` | `EVENT#recorded_at#event_id` |
| Interpretazione ufficiale verificata | `ESC#e` | `EVENT#recorded_at#event_id` |
| Acquisizione riuscita o fallita | `SOURCE#x` | `EVENT#recorded_at#event_id` |
| Audit di censimento/foto | `ESC#e` o `PROPOSAL#x` | `EVENT#recorded_at#event_id` |

`recorded_at` usa un formato UTC a lunghezza fissa, ad esempio `2026-10-14T12:00:00.000000Z`. È assegnato una volta dal server e mantenuto nei ritentativi; `event_id` distingue eventi registrati nello stesso istante. Gli attributi `observed_at`, `published_at` quando noto e `acquired_at` sono separati.

Lo storico paginato iniziale è **ordinato per registrazione**, e lo dichiara. Una segnalazione arrivata tardi appare come nuova registrazione con un momento osservato precedente. Le analisi usano i timestamp pertinenti e le rettifiche, senza equiparare ordine di inserimento e sequenza effettiva dei guasti.

La chiave della rettifica non sostituisce quella originale. L'evento contiene `target_pk` e `target_sk` dell'evidenza rettificata, motivazione e tipo. Le conferme riferiscono allo stesso modo la segnalazione. Le interpretazioni ufficiali riferiscono acquisizione, hash del contenuto e revisore.

Per operazioni puntuali su un evento, conservare o passare un riferimento completo validato dal server; non cercare un `event_id` con una Scan. Le risposte pubbliche possono esporre un riferimento opaco che il backend risolve.

## Indici secondari

| Indice | Documenti indicizzati | Chiave partizione | Chiave ordinamento | Proiezione iniziale |
| --- | --- | --- | --- | --- |
| `core.by_station` | Solo `META` di impianti confermati | `station_pk = STATION#s` | `station_sk = ESC#e` | `KEYS_ONLY` |
| `core.review_queue` | Solo foto/proposte/interpretazioni in revisione | `review_pk = REVIEW#tipo#PENDING` | `review_sk = created_at#id` | `KEYS_ONLY` |
| `events.by_actor` | Eventi con autore interno identificato | `actor_pk = USER#u` | `actor_sk = EVENT#recorded_at#event_id` | `KEYS_ONLY` |

Le chiavi principali vengono incluse automaticamente nelle proiezioni GSI. Con `KEYS_ONLY`, il backend recupera i documenti necessari dalle tabelle base; le eventuali proiezioni `INCLUDE` saranno aggiunte solo se le misure dimostrano un beneficio. Foto, testi lunghi e cronologie non sono replicati negli indici. Gli indici sono sparsi: un documento entra solo quando possiede gli attributi delle rispettive chiavi. [GSI DynamoDB](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GSI.html).

Gli attributi della coda vengono rimossi quando l'elemento esce dalla revisione. Un risultato dell'indice può tuttavia essere ancora visibile per un breve periodo: il backend rilegge il record e controlla il suo stato corrente. Una proposta approvata non viene mostrata nel censimento finché esiste solo come proposta.

Gli LSI non sono necessari per questi accessi. Devono essere creati insieme alla tabella e introducono un limite di 10 GB per raccolta con la stessa chiave di partizione. I GSI si possono aggiungere successivamente, con un backfill da pianificare. [LSI](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/LSI.html), [confronto indici](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/SecondaryIndexes.html).

Nessun GSI iniziale per stato, gestore, ordine alfabetico o statistiche. Lo stato globale e gli impianti senza foto saranno serviti da elenchi derivati con freschezza esplicita. Aggiungere un indice richiede un accesso concreto, una frequenza attesa e la misura del suo costo.

## Accessi applicativi

| Richiesta | Accesso |
| --- | --- |
| Elencare stazioni | Query `core`, PK `CATALOG#STATIONS` |
| Leggere scheda impianto | GetItem `core`, `ESC#e` / `META` |
| Impianti di una stazione | Query `by_station`; BatchGet delle schede, verificando conferma e associazione correnti |
| Stato di un impianto | GetItem `STATE`, con lettura coerente quando necessaria |
| Stato della stazione | Indice stazione, poi BatchGet di `META` e `STATE`; fonti e tempi restano distinti |
| Storico di un impianto | Query `events`, PK `ESC#e`, intervallo di SK e paginazione |
| Confrontare fonti | Storico dell'impianto e riferimenti puntuali a interpretazioni/acquisizioni |
| Foto di un impianto | Query `core`, PK `ESC#e`, prefisso SK `PHOTO#`; controllo di pubblicabilità sul server |
| Coda moderazione | Query `review_queue` per tipo, poi lettura corrente; endpoint riservato ai moderatori |
| Contributi di un utente | Query `events.by_actor`, autore derivato dall'identità autenticata |
| Comunicazioni di una fonte in un periodo | Query `events`, PK `SOURCE#x`, intervallo di registrazione |
| Originale relativo a un'acquisizione | GetItem del `BLOB#sha256` indicato, con autorizzazione separata alla copia S3 |
| Risolvere ID ufficiale | GetItem di `OFFICIAL#gestore#id` / `CLAIM` |
| Dashboard, lista globale per stato, copertura foto | Risultati precalcolati, con `generated_at` e copertura; nessuna Scan dello storico |
| Statistiche per periodo/ambito | GetItem o Query sotto `STATS#scope#id` |
| Ricalcoli pendenti | Query `core`, PK `WORK#AGGREGATES` |

Le liste globali possono essere snapshot JSON su S3, generati partendo dalla directory stazioni e dalle schede correnti. Una snapshot mancante o vecchia non significa che tutti gli impianti funzionino. Nella prova piccola si può costruire l'elenco con Query per stazione e BatchGet, misurandone il consumo.

Una Query legge solo gli item della chiave/intervallo selezionati, ma deve comunque essere limitata e paginata. `FilterExpression` può filtrare elementi già letti e non sostituisce un indice per una ricerca frequente; non riduce il consumo di lettura. [Filtri delle Query](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Query.FilterExpression.html).

I cursori devono restare associati a query, intervallo e autorizzazioni originali. Il client non può sostituire una chiave di partizione per leggere contributi privati altrui. Lo storico espone un limite temporale superiore fissato alla prima pagina e documenta che la paginazione non costituisce una snapshot transazionale.

## Coerenza, scritture e aggregazioni

I GSI offrono letture eventualmente coerenti. L'applicazione conferma una scrittura dalla risposta della transazione o dalla tabella base; le code e gli elenchi possono aggiornarsi dopo. I permessi, lo stato di moderazione e le condizioni decisive sono verificati sul record originale. BatchGet coerenti non costituiscono una fotografia atomica dell'intera stazione. [Coerenza delle letture](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadConsistency.html).

Un invio può usare `TransactWriteItems` per verificare che l'impianto esista e sia confermato, aggiungere l'evento immutabile, aggiornare una proiezione corrente con controllo di versione e registrare l'idempotenza. I conflitti richiedono rilettura e ritentativo limitato, mantenendo lo stesso ID e lo stesso contenuto della richiesta. Se l'aggiornamento dello stato è rinviato a un elaboratore, la risposta distingue evento salvato e proiezione ancora da aggiornare.

Le scritture condizionate impediscono sia la doppia creazione di un evento sia due assegnazioni dello stesso ID ufficiale. Un GSI non è un vincolo di unicità. Le operazioni di moderazione controllano versione e stato atteso per gestire due moderatori concorrenti. [Transazioni DynamoDB](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis.html).

L'idempotenza applicativa ha una finestra proposta di 24 ore: stessa chiave e contenuto restituiscono lo stesso risultato; stessa chiave con contenuto diverso genera un conflitto. Il token di idempotenza delle transazioni AWS dura 10 minuti e non basta per questa finestra. `expires_at` viene controllato dal codice: TTL è una pulizia asincrona, non una garanzia di eliminazione immediata. Gli eventi storici non hanno TTL. [Token delle transazioni](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis.html), [TTL](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html).

Le nuove evidenze e rettifiche invalidano le proiezioni pertinenti. Un elaboratore ricalcola i periodi interessati, inclusi gli effetti delle osservazioni tardive e delle correzioni del censimento. Usa risultati sostituibili con versione/metodo ed evidenze, senza incrementare ciecamente contatori a ogni ritentativo. Il dettaglio del calcolo di disponibilità e interruzioni resta una decisione successiva, basata sulla copertura.

Un lavoro ricalcolato viene rimosso dalla coda solo se la sua versione non è cambiata durante l'elaborazione. Se arriva un'altra rettifica, il lavoro rimane pendente. L'elaboratore deve poter ripartire dalle evidenze canoniche; lo stato corrente e le statistiche non le sostituiscono.

La fusione di duplicati nel censimento conserva gli ID precedenti e un rinvio al canonico. Non cancellare uno storico per far scomparire un doppione. La lettura deve poter raccogliere le evidenze delle identità riunite, evitando doppio conteggio; questo caso va verificato prima di aprire il censimento alla community.

## Evoluzione e costi

Per nuovi attributi: validazione Python, `schema_version`, lettori compatibili con le versioni precedenti e backfill solo quando necessario. Per nuovi accessi: motivazione dell'indice, scelta della proiezione, costo, test e rollout. Creare un GSI non inventa i nuovi attributi necessari sui record preesistenti; pianificare eventuale backfill, attendere l'indice attivo e verificare la copertura prima di cambiare le letture.

Un cambio di PK/SK comporta un nuovo item o un nuovo modello fisico: copia, verifica e passaggio controllato, conservando gli ID pubblici. Schemi di chiave e attributi indexati sono definiti da funzioni centralizzate e documentati; evitare che API e MCP costruiscano chiavi con regole differenti.

La quota gratuita Standard/provisioned include 25 RCU, 25 WCU e 25 GB. Verificare la disponibilità residua nel payer account e nella regione; sommare capacità di entrambe le tabelle e di tutti i GSI, compresi eventuali indici temporanei durante una migrazione. La capacità allocata occupa quota anche a traffico nullo. [Prezzi DynamoDB](https://aws.amazon.com/dynamodb/pricing/).

Misurare capacità consumata per tabella/indice, dimensioni e throttling. Anche un GSI con poche letture riceve scritture quando cambiano i documenti indicizzati; un GSI sottodimensionato può rallentare la tabella. Per questo sono sparsi e piccoli. [Capacità dei GSI](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GSI.html).

## Verifiche della prova

1. Ogni accesso della matrice funziona con dati sintetici, cursori e intervalli; le richieste pubbliche non chiamano Scan sullo storico.
2. Cambiare nome/stato non cambia l'ID dell'impianto; correggere la stazione aggiorna l'indice e conserva l'audit.
3. Un GSI temporaneamente arretrato non permette di pubblicare una foto già respinta né di approvare due volte lo stesso elemento.
4. Invii ripetuti e conflitti non duplicano eventi; idempotenza, scadenza applicativa e TTL sono distinti.
5. Conferma, rettifica e osservazione tardiva conservano tempi e riferimenti; i risultati derivati vengono invalidati e ricalcolati.
6. Aggiungere un attributo e predisporre un nuovo indice non richiede cambiare gli ID pubblici; il backfill non perde record.
7. Fusione di duplicati e confronto tra fonti conservano tutte le evidenze senza attribuire identità non verificate.
8. Report del consumo comprende entrambe le tabelle e tutti e tre gli indici, oltre agli altri servizi AWS.

La prova convalida queste scelte prima di creare il censimento reale. Numero di indici, proiezioni e capacità possono essere corretti sui risultati, mantenendo DynamoDB come database scelto.

## Estensioni implementate nel prototipo backend 0.2

Il prefisso `ESC#` rimane stabile anche per gli ascensori: `kind` distingue il tipo
senza rinominare identificativi o perdere riferimenti. Restano due tabelle e tre
GSI, con proiezioni `KEYS_ONLY`, nessun LSI e nessun permesso Scan nel runtime.

| Documento aggiuntivo | PK / SK | Accesso |
| --- | --- | --- |
| Foto canonica anche prima dell'approvazione del censimento | `PHOTO#id` / `META` | GetItem; ownership, versione, stato e parent sul record originale |
| Directory delle fonti | `CATALOG#SOURCES` / `SOURCE#id` | Query; riferimenti a `SOURCE#id` / `META` |
| Stream di osservazioni | `FEED#REPORTS` / `EVENT#recorded_at#id` | Query inversa con cursore firmato; immagine solo se il record foto corrente è approvato |
| Alias di un dispositivo | `ALIAS#canonical` / `DEVICE#alias` | Query primaria; metadata originali con `alias_of`, senza cancellare eventi |
| Snapshot riservata globale | `STATS#global` / `CURRENT` | GetItem; metodo, tempi, copertura, versione delle evidenze |
| Invalidazione globale | `WORK#AGGREGATES` / `GLOBAL` | Versione incrementata nella transazione di scrittura; completamento condizionato |
| Limite di scrittura | `RATE#hash_actor` / `minute` | Aggiornamento condizionato; finestra server, TTL soltanto per pulizia |

La chiave globale della foto aggiorna la proposta precedente `ESC#id`/`PHOTO#id`:
serve per l'upload prima che un impianto proposto esista nel censimento. I record
contengono parent, autore interno, versione e puntatori S3 privati. La lettura
pubblica è puntuale per ID, oppure referenziata dallo stream dopo approvazione;
non si usa Scan per cercare fotografie.

Le altre nuove partizioni sono limitate al volume dichiarato del prototipo. Il
ricalcolo avviene nel worker AWS, tramite Query delle evidenze, e non nelle letture
pubbliche delle statistiche. La prima quota pubblica può usare Query del piccolo
censimento e letture degli stati correnti, con copertura e coerenza eventuale
esplicite. In sviluppo le statistiche riservate vengono ricalcolate su richiesta.

La fusione aggiorna i metadata dei duplicati come alias e unifica gli eventi nelle
letture e nelle proiezioni. Correzioni della stazione preservano gli ID e lo storico
con l'associazione registrata all'epoca. Un cursore storico è vincolato anche alla
versione del censimento; non costituisce una snapshot atomica. Le code GSI e quelle
per autore rileggono il record corrente prima di autorizzare o restituire dati.

Le verifiche usano memoria, Moto e servizi HTTP emulati. Coerenza, capacità e
throttling di DynamoDB reale restano da verificare dopo il deploy autorizzato.

## Stazioni preferite per account

Accesso: leggere o sostituire al massimo 50 ID di stazioni dell’utente autenticato.
Un solo documento privato in `core`: `PK=USER#<sub Cognito>`,
`SK=FAVORITE_STATIONS`, `schema_version=1`, lista `station_ids`, `version`, `updated_at`.
GetItem coerente; nessuna Scan, nuovo indice, tabella o servizio. Nessun ID utente
accettato dal client. GET/PUT `/api/me/favorite-stations` richiedono autenticazione;
PUT richiede scope di scrittura e Idempotency-Key. Transazione con versione attesa,
controllo delle stazioni esistenti, ricevuta di idempotenza e limite antiabuso.
Due sessioni concorrenti ricevono un conflitto, evitando sovrascritture silenziose.
Le preferenze non producono osservazioni, feed, audit pubblico o invalidazioni
statistiche. Il record privato va incluso nell’eventuale cancellazione dei dati dell’account.

## Censimento documentale M1 (16 ottobre 2026)

Accessi: importazione additiva amministrativa, verifica delle matricole prima
dell'import, attivazione della directory completa, panoramica dei 215 impianti.
I metadata usano le stesse chiavi stazione/ESC esistenti, con ID UUID immutabili,
`inventory_dataset`, digest e provenienza documentale (URL, PDF, pagina, hash,
pubblicazione/acquisizione/registrazione distinti). Nessun record STATE viene
creato dal censimento. Gli originali rimangono privati.

| Documento | PK / SK | Accesso |
| --- | --- | --- |
| Riserva di una matricola da documento GTT | `INVENTORY_ID#sha256` / `CLAIM` | GetItem e Put condizionata insieme al metadata; hash su perimetro GTT M1, tipo e matricola normalizzata |
| Manifest di importazione | `CATALOG#IMPORTS` / `DATASET#id` | GetItem, digest del dataset, conteggi, data; nessuna sovrascrittura di una revisione già registrata |
| Puntatore di attivazione | `CATALOG#ACTIVE` / `CURRENT` | GetItem; attivazione transazionale col manifest dopo riscontro dell'indice delle stazioni |

La directory pubblica esclude dataset non ancora attivati. Se esistono stazioni
reali attive, seleziona queste per home, feed e aggregazioni; i record demo e gli
eventi preesistenti non vengono cancellati. I preferiti conservano gli ID salvati;
il frontend propone nuove scelte quando questi non sono nella directory corrente.

BatchGet coerenti con gruppi fino a 100 sostituiscono le letture individuali dei
metadata elencati dal GSI e degli stati della panoramica. Ogni metadata corrente
deve ancora essere confermato e appartenere alla stazione richiesta. Retry limitati
sulle sole chiavi non elaborate; fallimento esplicito invece di trattare una
lettura incompleta come assenza di evidenza. Nessuna Scan, tabella o GSI aggiuntivo.
