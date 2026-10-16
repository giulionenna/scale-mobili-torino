# Frontend collegato alle API

15 ottobre 2026. Frontend collegato alle API AWS e pubblicato sul sito Sites
privato esistente. Login/rinnovo Cognito, invio dal browser con upload S3 reale,
moderazione e persistenza sono collaudati; [esiti e limiti](collaudo-aws.md).
La CI usa emulatori e non riceve credenziali AWS.

## Avvio interattivo nel cloud

Da un terminale dell’ambiente cloud, per una prova veloce in memoria:

```bash
uv sync --project backend --frozen
SMT_MODE=demo uv run --project backend uvicorn scale_mobili.app:app --host 127.0.0.1 --port 8000
```

Da un secondo terminale, sempre nel cloud:

```bash
cd frontend
npm ci
PUBLIC_BROWSER_DEMO=false PUBLIC_DEV_LOGIN=true npm run dev -- --port 5173 --strictPort
```

Vite inoltra `/api` al backend sulla porta 8000. `SMT_API_PROXY` permette un indirizzo
diverso. Gli indirizzi loopback non sono link pubblici apribili dal PC dell’utente;
per un’anteprima esterna occorre il forwarding supportato dall’ambiente oppure il
successivo hosting. Non occorre installare il progetto sul PC.

La modalità backend `demo` perde i dati al suo riavvio. Per usare DynamoDB/S3
persistenti negli emulatori, seguire la [configurazione local del backend](backend-deployabile.md#persistenza-nello-sviluppo),
poi avviare lo stesso frontend con `PUBLIC_DEV_LOGIN=true`. Il collaudo automatico
qui sotto mantiene i servizi emulati mentre riavvia l’API; non verifica persistenza
dopo il riavvio dell’emulatore Moto, che usa memoria.

## Modalità

| Configurazione frontend | Origine dati e identità |
| --- | --- |
| `PUBLIC_BROWSER_DEMO=true` | Demo esplicita in `sessionStorage`, senza API; ruoli simulati |
| `PUBLIC_BROWSER_DEMO=false`, `PUBLIC_DEV_LOGIN=true`, API `demo`/`local` | API reali del progetto, identità di sviluppo verificate da `/api/me`; archiviazione secondo il backend |
| `PUBLIC_BROWSER_DEMO=false`, `PUBLIC_DEV_LOGIN=false` | API e login Cognito con PKCE; configurazione pubblica da `/api/config` |

Entrambi i flag sono `false` per default. In modalità AWS il frontend non mostra
mai la scelta di identità di sviluppo, anche se il flag fosse abilitato. Il server
AWS rifiuta comunque i token di prova. Le autorizzazioni dipendono da `/api/me` e
dalle verifiche di ogni endpoint, non dal ruolo scelto nell’interfaccia.

`PUBLIC_API_URL` indica l’URL dell’API nella build statica; vuoto usa la stessa
origine e, durante lo sviluppo, il proxy Vite. Dominio e client Cognito vengono da
`/api/config`, con eventuali override pubblici `PUBLIC_COGNITO_DOMAIN` e
`PUBLIC_COGNITO_CLIENT_ID`. Il backend deve avere `SMT_PUBLIC_URL` e
`SMT_FRONTEND_URL` coerenti; Cognito deve consentire il callback `/auth/cognito`.

L’accesso usa authorization code, PKCE S256 e state. La callback ripulisce il codice
dalla cronologia e torna solo a una pagina interna consentita. I token rimangono
in `sessionStorage`; il rinnovo contemporaneo viene condiviso. La disconnessione
rimuove la sessione dell’app e le schede riservate; non termina la sessione SSO del
provider Cognito. Un successivo login può quindi riutilizzare quella sessione.

## Flussi collegati

- Landing e home leggono il censimento e lo stato community corrente da
  `/api/overview`. La percentuale usa tutti gli impianti censiti; uno stato mancante
  non diventa funzionante. Le letture conservano l’indicazione di coerenza eventuale.
- Lo stream legge `/api/feed`, può caricare altre pagine ed espone solo le foto
  approvate. Il suo numero di righe non determina la disponibilità globale.
- Confronto GTT, nuovi fermi e streak leggono `/api/stats/private` solo dopo login.
  Il confronto usa le stesse evidenze della snapshot, anche se arriva un report più
  recente. Snapshot vecchie, ricalcolo pendente o dati indisponibili sono espliciti.
- Il form richiede stazione, impianto e stato. Descrizione e fotografia restano
  facoltative. Ogni invio conserva la chiave di idempotenza durante il ritentativo.
- La fotografia viene ricodificata per l’anteprima, caricata nel deposito privato
  e ricontrollata dal server. Il form S3 riceve soltanto i suoi campi firmati, mai il
  bearer token delle API. Le anteprime del moderatore richiedono autorizzazione e
  usano URL locali temporanei, revocati alla chiusura della scheda.
- La proposta viene salvata prima dell’eventuale foto. Se il caricamento fallisce,
  il messaggio dichiara che la proposta esiste già e invita a ritentare con gli stessi
  dati. Il nuovo impianto entra nel censimento solo dopo approvazione, senza uno
  stato inventato. La foto richiede un’approvazione distinta.
- Il pannello del moderatore legge le code paginate, richiede motivo e versione e
  salva le decisioni sul backend. I contributi personali vengono riletti dalle API
  e rimangono disponibili fra sessioni e riavvii API. L’elenco generale delle
  decisioni precedenti resta nella sola demo browser: l’audit backend è conservato,
  ma non è esposto da questo nuovo pannello.

## Verifiche

Con Chromium nel runtime o il browser Playwright installato nel cloud:

```bash
uv run --project backend python scripts/frontend_api_check.py
```

Il comando avvia e arresta API, Vite e servizi HTTP Moto con credenziali fittizie,
crea soltanto dati sintetici e verifica:

- accesso pubblico, nove impianti senza osservazioni inventate e statistiche protette;
- login di prova, invio con foto e percentuale aggiornata;
- risposta persa dopo salvataggio e ritentativo senza report o foto duplicati;
- proposta con foto fuori dal censimento fino alla revisione, motivazione obbligatoria;
- foto private prima dell’approvazione e visibili a un visitatore indipendente dopo;
- persistenza fra riavvii API e nuove sessioni del browser, logout e layout a 390 px;
- client OAuth con endpoint intercettati: PKCE, state, ritorno alla pagina richiesta,
  rinnovo e rifiuto di callback non richieste. Non equivale a Cognito reale.

Verificati anche 71 test backend, Ruff, controllo Svelte senza errori o warning e
build statica. La demo browser mantiene i collaudi della home pubblica e dei flussi
di segnalazione/moderazione, con attese aggiornate per le operazioni asincrone.

DynamoDB/S3 reali, login/rinnovo Cognito, API e SDK MCP sono verificati anche
in AWS. Misure di latenza iniziali e limiti del collaudo sono nel [rapporto reale](collaudo-aws.md).
Non sono prove di carico o di failover; la CI non esegue deploy.


Il callback Cognito usa `/auth/cognito`: Sites riserva `/callback` al proprio
accesso ChatGPT. Le due autenticazioni mantengono funzioni distinte: accesso
privato al sito e autorizzazione alle API AWS. Il callback applicativo non
intercetta né sostituisce le rotte di accesso gestite da Sites.

Il resource server Cognito usa l'URL MCP come identificatore. Gli scope custom
hanno quindi prefisso `<api_url>/mcp/`: il frontend li legge da `/api/config`,
la discovery MCP pubblica gli stessi valori e il backend riconosce soltanto
quelli della propria risorsa. Managed login rifiuta scope appartenenti a un
altro identificatore quando viene richiesto il binding `resource`.

## Preferiti e verifica all’accesso

Nella panoramica, «Le tue stazioni preferite» permette di scegliere e modificare
le stazioni. Nel sito AWS la lista privata è salvata in DynamoDB per account e
ritrovata su altri dispositivi. Il login sviluppo usa lo stesso backend; soltanto
la vecchia modalità browser-demo conserva la lista nella sessione locale.

Dopo ogni login viene aperta prima la verifica degli impianti dei preferiti, oppure
la scelta iniziale se la lista è vuota. Una nuova sessione browser autenticata la
propone di nuovo; navigazione, ricaricamento e rinnovo del token nella stessa
sessione non la ripetono dopo «Salta e continua» o «Fatto, continua».

La scelta dei preferiti e il salto non inviano segnalazioni. Per ogni impianto
si selezionano esplicitamente stato e momento osservato (ora locale del browser),
poi «Invia osservazione». Il backend conserva l’istante UTC e applica gli stessi
controlli e la stessa idempotenza del modulo ordinario. «Non l’ho osservato» non
è uno stato e non viene inviato. Sono disponibili tutti i quattro stati; nessuno
è preselezionato. I contributi del censimento dimostrativo restano sintetici.

Verifiche: isolamento tra account, persistenza tra istanze del servizio,
concorrenza e retry in memoria/DynamoDB emulato; Chromium con API ed emulatori
prova scelta, verifica all’accesso, salto senza scritture, invio esplicito,
ricaricamento, mobile e colore della scheda disponibilità al passaggio del mouse.

## Registrazione e amministrazione

Il login del sito privato Sites e l’account applicativo sono distinti. Nel dialogo
«Accedi» sono disponibili «Accedi al tuo account» e «Crea un account». La creazione
apre il modulo Cognito con lo stesso flusso PKCE e callback; richiede la conferma
dell’email tramite codice. Il recupero password è nella pagina di accesso Cognito.
Le modifiche all’indirizzo email richiedono una nuova verifica.

Gli utenti registrati sono cittadini. Il gruppo Cognito `administrators`, assegnato
solo tramite accesso operativo AWS, abilita l’area «Amministrazione» e le revisioni
già disponibili ai moderatori: censimento, foto e fonti tramite API. I gruppi sono
letti dal token firmato; email, parametri URL o dati nel browser non assegnano ruoli.
L’interfaccia attuale gestisce proposte e fotografie; non comprende una console
per modificare gli account degli altri utenti.

Per assegnare l’accesso iniziale, dopo registrazione e verifica dell’email:

```bash
uv run --project backend python scripts/grant_admin.py --user-pool-id <pool-del-prototipo>
```

L’indirizzo viene richiesto con input nascosto, senza password o inviti automatici.
Lo script richiede un account attivo, confermato, con email verificata e corrispondente;
usa l’identità immutabile restituita da Cognito per l’assegnazione. `--check-only`
verifica la preparazione senza assegnare il ruolo. Non inserire email reali in Git.
Dopo l’assegnazione uscire e accedere di nuovo per ottenere il token aggiornato.
