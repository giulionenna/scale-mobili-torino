# Sviluppo e verifiche del primo incremento

14 ottobre 2026. Codice e verifiche nell'ambiente cloud; nessuna installazione
richiesta sul PC dell'utente. Questo incremento prepara la fase 2 e parte del
percorso funzionale della fase 3, con un'interfaccia dimostrativa anticipata.

## Cosa funziona

- Backend FastAPI e cinque strumenti MCP sullo stesso servizio Python: elenco
  stazioni/impianti, stato, storico e invio segnalazione.
- Una stazione e due impianti fittizi; nessun gestore o ID ufficiale inventato.
- Demo in memoria con identità di prova, dati temporanei e banner esplicito.
- Segnalazioni, conferme e rettifiche; originale conservato e autore ricavato
  dall'identità; un utente comune non rettifica segnalazioni di altri.
- Idempotenza applicativa di 24 ore, transazioni nell'adattatore DynamoDB,
  versione della proiezione, ritentativi limitati, storico per registrazione
  con limite superiore e cursori firmati legati all'impianto.
- Osservazioni tardive e rettifiche ricalcolano lo stato community usando il
  momento osservato; conferme e report non sono conteggiati come guasti distinti.
- Frontend statico con consultazione, invio, storico, conferma e rettifica;
  schermate responsive e messaggi di errore/invio.
- Validatore JWT per il futuro percorso Cognito: firma RS256, issuer, audience
  vincolata alla risorsa MCP, scadenza, tipo access token, client e scope. Gruppo
  moderatore derivato dal token. La demo viene rifiutata nel runtime Lambda.
- Preparazione browser OAuth con PKCE S256, state e rinnovo; **non verificata con
  Cognito reale**. Metadati della risorsa protetta presenti; discovery del server
  OAuth e callback reali vanno convalidate prima dell'attivazione MCP.

L'archivio dimostrativo è volatile. L'adattatore DynamoDB è verificato con Moto;
persistenza AWS, consumi, coerenza effettiva e throttling non sono ancora provati.

## Comandi verificati

Dalla radice della repository:

```bash
uv sync --project backend --frozen
uv run --project backend ruff check backend scripts
uv run --project backend ruff format --check backend scripts
uv run --project backend pytest backend/tests -q
uv build --project backend --out-dir /tmp/scale-mobili-packages
uv run --project backend uvicorn scale_mobili.app:app --host 127.0.0.1 --port 8000 --no-access-log
```

In un secondo terminale cloud:

```bash
cd frontend
cp .env.example .env
npm ci
npm run check
npm run build
npm run dev -- --port 5173 --strictPort
```

Vite inoltra `/api` e `/health` al backend. I due server vengono eseguiti nello
stesso ambiente; gli indirizzi localhost non sono URL pubblici accessibili dal PC.
Per pubblicare servirà il deploy e la verifica economica. La build produce file
statici; `/callback` e `/impianto` sono pagine prerenderizzate.

Con i server avviati, il collaudo browser verificato usa Chromium del runtime:

```bash
uv run --project backend python scripts/browser_smoke.py
```

Il collaudo scrive soltanto dati sintetici e verifica invio, rettifica negata a un
altro utente, rettifica dell'autore, conferma e assenza di overflow a 375 px.
La schermata viene salvata in `/tmp/scale-mobili-prototipo.png`; nessuna immagine
o backup privato viene aggiunto alla repository. Se Chromium non è presente,
installarlo nell'ambiente cloud prima del collaudo, verificando i domini necessari.

### Anteprima privata apribile dal browser

La modalità opzionale `PUBLIC_BROWSER_DEMO=true` prepara una build statica interattiva
senza chiamate al backend: dati fittizi e segnalazioni rimangono in `sessionStorage`
del browser e l'accesso è simulato. È destinata all'anteprima privata; non verifica
autenticazione, persistenza AWS o MCP. Con `PUBLIC_BROWSER_DEMO=false` (default),
l'interfaccia continua a usare il backend Python previsto dal progetto.

La variante browser è stata verificata su un server statico: invio, conferma,
rettifica autorizzata/negata, conservazione al ricaricamento e viewport mobile,
senza richieste API o health esterne. Nessuna risorsa AWS è stata creata per renderla
accessibile. La pubblicazione privata usa [Sites](skill://plugin_connector_1p_689987207de08191979cf68eca2941c6/sites/SKILL.md)
e una copia sanitizzata del frontend, separata dal progetto AWS.

Pubblicazione privata riuscita il 14 ottobre 2026:
[apri la demo](https://scale-mobili-torino-prototipo.tender-tapir-0169.chatgpt.site). L'accesso è riservato al proprietario; se viene richiesto il login,
usare lo stesso account ChatGPT. Questa pubblicazione non costituisce un deploy AWS.

## Evidenze

| Verifica | Esito | Ambito |
| --- | --- | --- |
| Test backend | 35 test riusciti | Python e Moto, credenziali sintetiche nei test |
| Pacchetto Python | Wheel e distribuzione sorgente costruite | Pacchetto applicativo; non ancora un bundle Lambda |
| API/MCP | Handshake, notifiche, discovery, lettura e invio autenticato riusciti | Test ASGI e SDK MCP ufficiale su HTTP loopback |
| Negoziazione SDK HTTP | Protocollo 2025-11-25, cinque strumenti | SDK Python installato; non ChatGPT |
| Lambda | Eventi HTTP API v2 e invocazioni ripetute riusciti | Adattatore Mangum simulato; non Lambda AWS |
| Frontend | Check senza errori/warning e build statica riuscita | Node/Vite/SvelteKit nel cloud |
| Browser | Flusso funzionale e viewport mobile riusciti | Chromium nel cloud, demo sintetica |
| Terraform | fmt, init senza backend e validate riusciti | Modulo tabelle/GSI; nessun plan/apply su AWS |
| GitHub Actions | Workflow CI e plan manuale preparati, YAML verificato | Non eseguiti sui runner GitHub |
| AWS | Identificazione STS riuscita | Servizio reale; gli altri endpoint sono in attesa della rete |

Versioni bloccate nei file `backend/uv.lock`, `frontend/package-lock.json` e
`infra/.terraform.lock.hcl`. Runtime verificati: Python 3.12.14, Node 24.19.0,
uv 0.12.23, Terraform 1.14.6, provider AWS 6.68.0, MCP SDK 1.30.0, Mangum 0.22.0.
I test segnalano due deprecazioni upstream (TestClient/httpx ed event loop Mangum);
non impediscono questi esiti, ma non vanno nascoste.

## Decisione sull'adattatore MCP/Lambda

La prova ha riprodotto un errore alla seconda invocazione: il manager HTTP MCP
dell'SDK può essere avviato una sola volta per istanza. L'handler costruisce una
nuova app/MCP per ciascuna invocazione e condivide configurazione e archivio.
Il test ripete le invocazioni per verificarne avvio e arresto. Misurare l'effetto
sulla latenza quando Lambda sarà disponibile; non si promettono prestazioni AWS.

## Lavoro ancora necessario

- Completare fase 1: rete, Milano, IAM/OIDC, inventario completo, tariffa e budget.
- Completare fase 3: censimento e moderazione, contributi privati per autore,
  correzioni dell'associazione, fusione duplicati, accessi rimanenti e statistiche.
- Il ricalcolo sincrono è limitato a 1.000 eventi per impianto per la prova; oltre
  il limite serve elaborazione asincrona e coda di invalidazioni. Non dichiarare
  questa implementazione pronta al volume della release pubblica.
- Preparare controllo antiabuso distribuito prima di esporre scritture pubbliche;
  il limite del body JSON e i controlli di autenticazione non lo sostituiscono.
- Completare fase 4: bootstrap OIDC, app/storage/identità/frontend Terraform,
  permessi minimi, pacchetto Lambda e apply manuale su piano revisionato.
- Il workflow plan salva un piano privato su S3 per revisione e ripulisce le copie
  locali; non fa apply. Richiede ruolo OIDC, backend privato ed environment GitHub
  `aws-prototype` configurati prima dell'uso.
- Login Cognito, discovery OAuth, callback, audience, rinnovo e client ChatGPT
  reali restano da provare; Gemini richiede una prova indipendente.
- Foto, fonti GTT, pannello/coda moderatore, export/ripristino, misure di costo e
  prestazioni restano alle successive fasi del piano.

Le fonti ufficiali e la stima restano assenti: l'interfaccia non riempie i vuoti
con stati inventati. Il risultato attuale è un **prototipo dimostrativo nel cloud**,
non una piattaforma già distribuita su AWS o un censimento reale.
