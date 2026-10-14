# Piano per il prototipo funzionante

14 ottobre 2026. Piano operativo basato su [architettura e prova iniziale](architettura-e-prova-iniziale.md), [modello DynamoDB](modello-dynamodb.md) e [istruzioni di sviluppo](../AGENTS.md). Le fasi sono sequenziali, salvo le verifiche AWS in sola lettura, che possono procedere durante la preparazione del codice.

## Risultato da raggiungere

Un prototipo raggiungibile dal browser, distribuito su AWS, con una stazione e due impianti **interamente fittizi**, due utenti di prova e un moderatore. Deve consentire:

- consultare impianti, stato e storico, distinguendo community, ufficiale, stima e assenza di informazioni;
- autenticarsi, inviare una segnalazione, confermarla e rettificarla senza perdere l'originale;
- caricare una foto privata e renderla visibile soltanto dopo elaborazione e moderazione;
- registrare acquisizioni di una fonte ufficiale, conservando provenienza e originali privati;
- leggere stato e storico e inviare una segnalazione tramite MCP, verificando OAuth nel client reale;
- esportare e ripristinare i dati di prova, misurare consumi e disattivare la prova.

Non è ancora il censimento reale né la prima release pubblica. Dominio definitivo, licenze, OCR, attendibilità numerica, statistiche di disponibilità e ricerca di foto simili restano ai passaggi successivi. Le statistiche iniziali possono esporre conteggi e copertura; se i dati non consentono un calcolo, restituiscono la motivazione.

## Stato iniziale verificato

- [x] Letti README, AGENTS e i due documenti tecnici.
- [x] Confermato che la repository contiene documentazione e nessun codice applicativo o infrastruttura.
- [x] Verificata l'identità AWS con una chiamata reale `STS GetCallerIdentity` il 14 ottobre 2026. Non sono state create risorse AWS.
- [ ] Verificati permessi sui servizi, abilitazione di Milano, risorse esistenti, quote residue e copertura economica.

Le credenziali disponibili consentono l'identificazione: non dimostrano accesso amministrativo né diritto al Free Tier. La policy di rete attuale consente `sts.amazonaws.com` e i domini di sviluppo predefiniti; gli altri endpoint AWS e GTT richiedono la configurazione di rete supportata prima delle relative verifiche. Non inserire identità dell'account o credenziali nei documenti pubblici.

## 1. Verificare le condizioni della prova AWS

**Lavoro:** ispezionare in sola lettura account, regione proposta `eu-south-1`, IAM/OIDC e utilizzo esistente. Individuare gli endpoint necessari e predisporre la configurazione della rete. Verificare tariffe e benefici effettivi per DynamoDB, CloudFront, Cognito, HTTP API, S3, Lambda, Scheduler, log, stato Terraform e recupero dati. Distinguere limiti di servizio, quote gratuite e crediti: una quota tecnica non prova la gratuità.

Preparare una stima sia per il lotto di prova (circa 100 letture, 10 segnalazioni e 3 foto) sia per lo scenario mensile documentato. Sommare capacità di entrambe le tabelle e tutti i GSI, storage, richieste e risorse già presenti. Documentare ciò che non è verificabile con i permessi disponibili.

**Consegna:** rapporto di fattibilità, endpoint necessari, permessi mancanti, dimensionamento iniziale e tabella dei costi con ipotesi e fonti.

**Criterio di completamento:** sappiamo dove e con quali permessi distribuire la prova e quali voci sono coperte o possono essere fatturate. Il budget resta zero: nessuna attivazione con costi non concordati. Se la verifica economica resta incompleta, il codice continua a essere preparato e il deploy resta pendente.

## 2. Preparare il progetto e verificare gli adattatori

**Lavoro:** creare struttura backend Python, frontend SvelteKit statico, infrastruttura Terraform, test e CI; bloccare le dipendenze. Proporre cartelle `backend/`, `frontend/`, `infra/` e `tests/`, mantenendo la documentazione esistente.

Fare una prova minima di FastAPI e SDK MCP ufficiale sullo stesso servizio applicativo: avvio e arresto, handshake, discovery, richieste e notifiche, risposte JSON su Streamable HTTP stateless e adattamento a Lambda. Verificare build statica e percorso OAuth previsto, senza dichiarare già la compatibilità con ChatGPT.

**Consegna:** progetto eseguibile nell'ambiente cloud, build verificata e CI senza credenziali AWS per le contribuzioni; annotazione delle versioni e dei limiti degli adattatori.

**Criterio di completamento:** API e MCP chiamano la stessa funzione, il trasporto funziona nel client di test e frontend/backend si costruiscono con comandi documentati. Se l'adattatore fallisce, correggerlo prima di sviluppare tutte le funzionalità.

## 3. Realizzare il flusso dati essenziale

**Lavoro:** implementare modelli e validazione, costruzione centralizzata delle chiavi, repository DynamoDB e servizi applicativi. Usare due tabelle e i tre GSI proposti, verificandoli contro la matrice degli accessi. Preparare un seed idempotente esclusivamente sintetico e separato dai dati reali.

Implementare stazioni e impianti, stato con fonti separate, storico paginato, segnalazioni, conferme e rettifiche. Conservare i tempi distinti e riferimenti completi agli eventi. Gestire transazioni, versioni, invii ripetuti, conflitti, osservazioni tardive e ricalcoli. La finestra di idempotenza è controllata dal codice; TTL serve solo alla pulizia.

Prevedere moderazione del censimento e audit; verificare che una proposta non sia pubblicata come impianto confermato. Testare correzione della stazione e fusione di duplicati prima di aprire contributi sul censimento reale.

**Consegna:** API del percorso essenziale, servizi condivisi con MCP e test significativi di paginazione, autorizzazione, idempotenza, concorrenza, indici arretrati e dati incompleti.

**Criterio di completamento:** il percorso segnalazione → storico → rettifica funziona nei test senza duplicazioni, perdita dell'originale o Scan dello storico nelle richieste pubbliche. Questi esiti restano simulati fino alla prova su DynamoDB reale.

## 4. Preparare il deploy e fare la prima verifica reale

**Lavoro:** preparare Terraform, bootstrap dedicato e workflow manuali GitHub Actions con OIDC. Ispezionare l'eventuale provider OIDC esistente; usare ruoli, trust policy, stato e risorse dedicati al progetto. Confrontare il metodo con `giulionenna/mcp-serverless-kit`, senza ereditarne automaticamente risorse o autenticazione.

Il deploy parte dal ramo autorizzato e applica il piano del commit verificato; stato e piani Terraform restano privati. Predisporre un inventario delle risorse, retention dei log, limiti di consumo e comandi di rimozione della sola prova.

Completata la verifica economica della fase 1, distribuire l'ambiente minimo: DynamoDB, API/Lambda, Cognito e storage necessario. Verificare subito login, persistenza, transazioni e costo del percorso minimo. Provare presto MCP nel client ChatGPT reale: discovery, lettura, scrittura, PKCE S256, issuer, audience, scope e rinnovo. Configurare callback e client OAuth sulla base del client effettivo.

**Consegna:** infrastruttura ripetibile, endpoint di prova e rapporto delle verifiche AWS/MCP reali.

**Criterio di completamento:** il login e una segnalazione persistente funzionano realmente; MCP supera le prove del client oppure le incompatibilità sono risolte prima di dichiararlo completato. CI riuscita, deploy, login e rinnovo sono esiti distinti.

## 5. Rendere utilizzabile il prototipo dal browser

**Lavoro:** realizzare elenco stazioni, scheda impianto, stato con provenienza e freschezza, storico, login, invio, conferma/rettifica e pannello moderatore. Collegare il frontend alle API reali; distribuire la build statica su S3 privato e CloudFront, verificando la copertura economica del piano scelto.

Gestire caricamento, errori, dati assenti, conflitti e conferma dell'invio. Mostrare UTC con fuso Europe/Rome nell'interfaccia. Evidenziare sempre che l'ambiente contiene dati sintetici. Non condividere cache di risposte autenticate; mostrare la freschezza delle letture pubbliche.

**Consegna:** URL navigabile e flusso completo dal browser con due utenti e un moderatore.

**Criterio di completamento:** un utente può consultare, autenticarsi, segnalare e rettificare; un altro può confermare; un utente comune non può accedere alle operazioni del moderatore. A questo punto esiste il primo prototipo utilizzabile, ancora da completare con foto e fonti.

## 6. Aggiungere fotografie e acquisizioni ufficiali

**Lavoro foto:** upload autorizzato verso S3 privato, controllo tipo reale/dimensioni/pixel, ricodifica senza EXIF e miniatura, rimozione dell'originale non sanitizzato dopo il successo. La copia sanitizzata resta privata fino all'approvazione. Gestire rifiuto, rimozione e scelta della foto principale con controlli sul record corrente e audit.

**Lavoro fonti:** registrare ciascuna acquisizione e deduplicare i byte originali per hash; conservare URL, esito, tempi e versione di estrazione. Iniziare con interpretazione manuale moderata. Non collegare fonti reali agli impianti sintetici come se fossero associazioni verificate. Provare separatamente un'acquisizione GTT reale, quando consentita, e gli scenari sintetici di duplicazione/errore. Gli originali restano privati.

Scheduler ogni quattro ore solo dopo aver verificato condizioni della fonte e costi; per il prototipo bastano acquisizioni controllate. Un errore o l'assenza di un impianto in un report non aggiornano il suo stato a funzionante.

**Consegna:** flusso fotografico completo e archivio consultabile tramite metadati e riferimenti autorizzati.

**Criterio di completamento:** file errati respinti, foto pendenti non accessibili pubblicamente, foto approvate senza EXIF; due contenuti uguali, uno diverso e un errore producono quattro acquisizioni e due originali distinti. Dichiarare quali acquisizioni sono simulate e quali reali.

## 7. Collaudare, misurare e chiudere la prova

**Lavoro:** eseguire la matrice di collaudo dell'architettura su AWS reale con il lotto limitato. Verificare token assenti/scaduti o con audience/scope errati, moderazione concorrente, indici arretrati, dati incerti, foto rifiutate, cursori e invii ripetuti. Esportare e ripristinare dati e riferimenti ai file.

Misurare latenza mediana e p95, invocazioni calde/fredde, errori, timeout, consumo e capacità allocata per tabella/GSI, throttling, durata Lambda, byte archiviati e costi disponibili. L'obiettivo iniziale di 5 secondi è da valutare con le misure. Non attribuire costo zero a una fatturazione ancora pendente.

**Consegna:** rapporto con commit, versioni, regione, esiti, consumi, limiti e istruzioni riproducibili. Annotare separatamente prove emulate, AWS reali e client MCP reali; Gemini richiede una verifica propria, se incluso.

**Criterio di completamento:** tutte le funzioni del prototipo sono provate o il risultato è esplicitamente parziale. Salvare i risultati, disattivare processi periodici e predisporre la rimozione delle sole risorse dedicate. Decidere poi la prosecuzione verso il censimento reale e la release pubblica, con licenze, backup regolari e budget verificati.

## Ordine di esecuzione e aggiornamento

Avvio: fase 1 in sola lettura e fase 2 nell'ambiente cloud. Poi fase 3, preparazione e verifica reale della fase 4, interfaccia della fase 5, integrazioni della fase 6 e collaudo della fase 7. Le prove MCP reali precedono il completamento delle integrazioni per scoprire presto eventuali incompatibilità.

Al termine di ogni fase annotare qui stato, commit, verifiche e problemi aperti. Aggiornare architettura e modello DynamoDB quando le misure richiedono una modifica. Un risultato simulato non chiude una verifica prevista su AWS o nel client reale.

| Fase | Stato |
| --- | --- |
| Lettura e identificazione AWS iniziali | Completate |
| 1. Condizioni AWS, rete e budget | STS verificato; altri servizi in attesa della rete e del controllo economico |
| 2. Progetto e adattatori | Preparazione completata nel cloud: build, test API/MCP e adattatore Lambda; CI GitHub preparata, non eseguita |
| 3. Flusso dati essenziale | Primo incremento realizzato e testato con memoria/Moto; censimento, moderazione e accessi rimanenti da completare |
| 4. Deploy e prove reali | Modulo tabelle/GSI e plan manuale preparati; bootstrap e deploy completi pendenti, subordinati a fase 1 |
| 5. Interfaccia | Demo sintetica verificata nel browser; integrazione AWS e moderazione complete pendenti |
| 6. Foto e fonti | Da avviare |
| 7. Collaudo e misure | Da avviare |

Primo incremento del 14 ottobre 2026: esiti e comandi in
[sviluppo e verifiche](sviluppo-e-verifiche.md); blocchi e domini necessari in
[verifica AWS](verifica-iniziale-aws.md). Nessuna risorsa AWS creata e nessuna prova
ChatGPT/Cognito reale già completata. Le modifiche sono nel workspace; non è stato
creato un commit né eseguito un push, quindi non si attribuisce un esito a GitHub CI.

Iterazione dell'interfaccia: adottare blu e giallo morbidi, landing separata dalla
home, panorama su più stazioni e stream, confronto GTT/community, segnalazione
autenticata con stazione/impianto e foto/descrizione facoltative, proposte moderate
sia per scale mobili sia per ascensori. La demo browser include questi flussi;
API, Cognito, censimento DynamoDB e acquisizioni reali devono essere collegati nelle
fasi 3–6. Dettagli in [specifiche aggiornate](specifiche-interfaccia.md).
