# Frontend collegato alle API

15 ottobre 2026. Implementazione nella repository, senza deploy AWS. La CI della
PR sul precedente commit `8f275c2` è riuscita su GitHub. Questo incremento aggiunge
il collaudo browser delle API alla CI, senza credenziali AWS.

Il sito Sites già pubblicato resta la demo precedente. La nuova versione viene
verificata nell’ambiente cloud di sviluppo e pubblicata come codice nella PR.

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

Verificati anche 64 test backend, Ruff, controllo Svelte senza errori o warning e
build statica. La demo browser mantiene i collaudi della home pubblica e dei flussi
di segnalazione/moderazione, con attese aggiornate per le operazioni asincrone.

DynamoDB/S3 reali, login e rinnovo Cognito reali, coerenza degli indici, latenza e
consumi restano da provare dopo l’attivazione AWS concordata. La CI non esegue deploy.


Il callback Cognito usa `/auth/cognito`: Sites riserva `/callback` al proprio
accesso ChatGPT. Le due autenticazioni mantengono funzioni distinte: accesso
privato al sito e autorizzazione alle API AWS. Il callback applicativo non
intercetta né sostituisce le rotte di accesso gestite da Sites.

Il resource server Cognito usa l'URL MCP come identificatore. Gli scope custom
hanno quindi prefisso `<api_url>/mcp/`: il frontend li legge da `/api/config`,
la discovery MCP pubblica gli stessi valori e il backend riconosce soltanto
quelli della propria risorsa. Managed login rifiuta scope appartenenti a un
altro identificatore quando viene richiesto il binding `resource`.
