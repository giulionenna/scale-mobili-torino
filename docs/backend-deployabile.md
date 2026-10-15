# Backend del prototipo e percorso di deploy

14 ottobre 2026. Backend Python 0.2.0, API FastAPI e MCP, adattatori DynamoDB/S3,
Terraform e workflow manuali. **Nessuna risorsa applicativa AWS è stata creata.**
La demo Sites già pubblicata rimane una simulazione browser. Il frontend nella
repository è collegato a queste API: vedi [configurazione e collaudo](frontend-collegato.md).

## Avvio immediato nell'ambiente cloud

```bash
uv sync --project backend --frozen
SMT_MODE=demo uv run --project backend uvicorn scale_mobili.app:app --host 127.0.0.1 --port 8000
```

Swagger è su `/docs`, il contratto JSON su `/openapi.json`, MCP su `/mcp`.
Gli indirizzi localhost indicano l'ambiente cloud, non il PC dell'utente.
La modalità demo usa quattro stazioni e nove impianti fittizi in memoria.
Non inventa osservazioni iniziali né dati GTT. I dati spariscono al riavvio.

Header di prova, **accettati soltanto fuori da AWS**:

- cittadino: `Authorization: Bearer demo-user-1` oppure `demo-user-2`;
- moderatore: `Authorization: Bearer demo-moderator`;
- ogni scrittura richiede `Idempotency-Key`, 8–128 caratteri: conservare la stessa
  chiave e lo stesso corpo nei ritentativi.

La modalità `demo` o `local` è rifiutata all'avvio su Lambda. Terraform configura
sempre `SMT_MODE=aws`, con JWT Cognito verificati sul server.

## Flussi e contratti

| Operazione | Endpoint principale | Accesso |
| --- | --- | --- |
| Home pubblica: catalogo, stati e disponibilità | `GET /api/overview` | Pubblico; nessuna statistica riservata |
| Stazioni e impianti | `GET /api/stations`, `/api/stations/{id}/devices` | Pubblico |
| Scheda, stato e storico | `GET /api/devices/{id}`, `/status`, `/history` | Pubblico |
| Stream | `GET /api/feed` | Pubblico; foto solo approvate |
| Prima statistica | `GET /api/stats/availability` | Pubblico |
| Allineamento, nuovi fermi, streak | `GET /api/stats/private` | JWT e `stats:read` |
| Segnalazione | `POST /api/devices/{id}/reports` | JWT e `reports:write` |
| Conferma / rettifica | `POST /api/devices/{id}/confirmations`, `/corrections` | JWT; rettifica dell'autore o moderatore |
| Proposta | `POST /api/proposals`, `GET /api/me/proposals` | JWT; elenco personale isolato per autore |
| Coda e approvazione | `/api/moderation/{kind}/queue`, `/proposals/{id}/review` | Moderatore |
| Upload fotografico | `POST /api/photos/uploads`, `/api/photos/{id}/complete` | JWT; ownership e parent verificati |
| Foto pubblica / anteprima | `/api/photos/{id}/image`, `/preview` | Pubblica dopo approvazione / autore o moderatore |
| Revisione e ritiro foto | `/api/moderation/photos/{id}`, `/review` | Moderatore, versione e motivo obbligatori |
| Correzione stazione / fusione | `/api/moderation/devices/{id}/station`, `/merge` | Moderatore; versioni e audit |
| Fonti e interpretazione | `/api/sources`, `/api/moderation/sources`, `/interpretations` | Metadati pubblici; scritture moderate |
| Originale archiviato | `GET /api/moderation/sources/original?reference=...` | Moderatore; download privato breve |
| Ricalcolo manuale | `POST /api/moderation/statistics/rebuild` | Moderatore |

Le vecchie rotte `/api/escalators/...` rimangono compatibili. I nuovi contratti
usano `devices` per includere entrambi i tipi di impianto. La segnalazione richiede
stazione e stato; il dispositivo è identificato dal percorso. Descrizione e
`photo_id` sono facoltativi. Il server verifica l'associazione alla stazione.

Le proposte restano fuori dal censimento fino all'approvazione. Un nuovo impianto
non riceve uno stato senza osservazioni. Versioni e transazioni impediscono doppie
approvazioni. Correggere la stazione conserva l'ID e i riferimenti storici; la
fusione conserva metadata ed eventi dei duplicati, crea alias e unifica letture,
rettifiche e proiezioni. Nessuna cancellazione dello storico per eliminare un doppione.

Gli strumenti MCP aggiungono `list_devices`, `get_working_percentage`,
`get_private_statistics`, `submit_device_report` e `propose_device` agli strumenti
precedenti. Usano gli stessi servizi e controlli dell'API.

## Fotografie

1. Riservare l'upload per un dispositivo oppure una proposta propria.
2. Su AWS usare il form S3 autorizzato restituito dal server, con dimensione e
   `Content-Type` vincolati. In demo l'upload usa la rotta PUT indicata nella risposta.
3. Completare l'upload: il server legge i byte, controlla formato reale, 5 MB,
   20 megapixel e assenza di animazione; ricodifica in JPEG, massimo 1200 px,
   senza EXIF. La copia sanitizzata usa un percorso contenente l'hash dei byte.
4. La foto resta privata. Quella di una segnalazione entra nella coda quando
   viene collegata al report; quella di una proposta attende anche l'approvazione
   dell'impianto. La revisione della foto è distinta dal censimento.
5. Solo l'approvazione rende disponibile `/image`. Ogni lettura verifica il
   record corrente e non usa cache condivise. Il moderatore può ritirare una foto
   già approvata, conservando l'audit. L'originale non sanitizzato viene eliminato
   dopo il completamento; gli upload abbandonati scadono nello storage.

Non esistono ACL pubbliche S3. Il bucket è privato anche per le immagini approvate.

## Fonti e statistiche

Il collector recupera soltanto URL HTTPS sul dominio GTT verificato; niente
redirect o URL arbitrari. Ogni tentativo produce un'acquisizione, anche senza
variazioni o in caso di errore. Gli originali privati sono deduplicati per SHA-256.
Inizio acquisizione, completamento, registrazione e pubblicazione quando nota
sono distinti. L'interpretazione è manuale e riservata al moderatore, riferita a
un originale archiviato. Un errore o un impianto assente dal report non diventano
uno stato funzionante. Fonti reali non si associano a impianti sintetici.

La rotta `/api/moderation/sources/{id}/fixture` permette contenuti di prova solo
per fonti sintetiche fuori da AWS; è rifiutata nel runtime AWS.

La prima statistica usa l'ultima osservazione community sul totale del censimento,
con numero di impianti osservati e metodo. Non è disponibilità continua nel tempo.
L'allineamento considera stati esattamente identici tra le due fonti e dichiara
quanti impianti sono confrontabili o esclusi. Nessun confronto produce `null`.
Le percentuali arrotondano mezzo punto verso l'alto, come nel frontend.

Il worker ricalcola confronti e sequenze dalle evidenze, includendo rettifiche,
osservazioni tardive e alias. Le conferme non aggiungono guasti. Una streak conta
osservazioni consecutive di guasto/manutenzione; funzionamento e non verificabilità
la interrompono. Un nuovo fermo ha la prima osservazione nelle 24 ore precedenti
la generazione della snapshot. Intervalli non osservati e durata continua restano
sconosciuti. La snapshot espone freschezza e ricalcolo pendente. Una revisione delle
evidenze durante il ricalcolo impedisce di riconoscere come completato il lavoro vecchio.

## Persistenza nello sviluppo

`compose.yaml` prepara DynamoDB Local e MinIO su porte loopback e volumi dedicati.
Usa credenziali pubbliche di prova e non contatta AWS. Il download delle immagini
è stato rifiutato dal registry nell'ambiente corrente, quindi il loro avvio non
è dichiarato verificato. Per una prova HTTP riproducibile senza Docker:

```bash
uv run --project backend python scripts/emulated_http_check.py
```

Il comando avvia servizi HTTP Moto e una vera API Uvicorn in modalità `local`,
inizializza le tabelle e lo storage sintetici, prova tutti i flussi e riavvia l'API.
I servizi emulati rimangono attivi durante il riavvio: la prova dimostra persistenza
esterna al processo API, non durabilità o prestazioni dei servizi AWS reali.

Per mantenere i servizi di sviluppo aperti, avviare `moto_server -H 127.0.0.1 -p 5001`
con `uv run --project backend`, poi impostare le variabili dell'esempio backend
per `SMT_MODE=local`, con entrambi gli endpoint a `http://127.0.0.1:5001`.
Eseguire `smt bootstrap-local`, `smt seed --synthetic`, quindi Uvicorn, sempre con uv.
Il bootstrap CLI rifiuta ogni modalità diversa da `local`; il seed non sovrascrive
record reali e non inventa stati. Gli emulatori usano una sessione SDK con credenziali
di prova esplicite, senza inoltrare quelle dell'ambiente.

## Verifiche e pacchetto Lambda

```bash
uv run --project backend ruff check backend scripts
uv run --project backend ruff format --check backend scripts
uv run --project backend pytest backend/tests -q
uv run --project backend python scripts/emulated_http_check.py
python scripts/build_lambda.py
python scripts/check_lambda.py
```

Il bundle `dist/backend-lambda.zip` contiene il codice e le dipendenze di produzione
da `uv.lock`, per Python 3.12/x86_64 e glibc compatibile con Amazon Linux 2023.
Esclude dipendenze di sviluppo, credenziali, `.env`, dati e fotografie.
Il controllo lo importa senza site-packages esterni e ripete invocazioni simulate.
Il manifest lega SHA-256 del piano e del bundle al commit usato dal workflow.

Terraform viene verificato con `fmt`, `init -backend=false`, `validate` e `test`.
I test usano **mock_provider aws**: anche il loro comando `apply` è simulato e non
contatta AWS. Il bootstrap ha una validazione separata. Le CI GitHub sono preparate;
non si attribuisce loro un esito prima dell'esecuzione sui runner.

Esiti nell'ambiente cloud: 64 test Python passati; controllo e formattazione Ruff
riusciti; API HTTP con DynamoDB/S3 emulati e riavvio API riusciti; bundle isolato
importato e invocato ripetutamente; validazioni Terraform e cinque test simulati
tra stack e bootstrap riusciti. Frontend: check senza errori/warning e build
riusciti dopo l'aggiornamento dello scope OAuth. Restano due deprecazioni upstream
nei test Python (TestClient/httpx e ciclo eventi Mangum), senza errori funzionali.

## Primo deploy autorizzato, subordinato alla verifica economica

Lo stack applicativo crea due tabelle/tre GSI, due bucket privati, Cognito,
parametro SSM SecureString, tre Lambda, HTTP API, log WARN con retention predefinita di un giorno
e scheduler opzionali. API e MCP condividono HTTP API e verificano JWT nel backend.
Il runtime non ha permessi Scan. Il bootstrap prepara stato S3 privato/versionato,
provider GitHub OIDC verificato o nuovo, ruoli plan/deploy separati e boundary dei
ruoli applicativi. Non riusa ruoli o stato di altri progetti.

Prima dell'attivazione verificare regione Milano, permessi, quote residue e tutte
le voci: DynamoDB, Lambda, API, Cognito, S3, log, SSM/KMS, stato e piani. La modalità predefinita di DynamoDB è a consumo con limiti espliciti su tabelle
e indici. La modalità provisioned opzionale alloca 7 RCU/7 WCU e richiede
la verifica della copertura residua; nessuna delle due garantisce costo zero. La concorrenza Lambda riservata
richiede quota disponibile nell'account. `budget_reviewed=false` blocca il piano.

1. Revisionare `infra/bootstrap`, salvare il suo stato fuori dal repository e
   fornire il repository GitHub esatto; ispezionare prima un eventuale provider OIDC.
2. Configurare l'environment GitHub `aws-prototype`, limitato a `main`, con revisione
   richiesta per il deploy. Impostare variabili `AWS_PLAN_ROLE_ARN`, `AWS_DEPLOY_ROLE_ARN`,
   `TF_STATE_BUCKET`, `RUNTIME_PERMISSIONS_BOUNDARY_ARN`, `FRONTEND_URL`, `PROJECT_PREFIX`
   e, per rotazioni deliberate, `CURSOR_SECRET_VERSION`. Il segreto casuale di almeno
   32 caratteri va in `SMT_CURSOR_SECRET`, mai in un tfvars o nella repository.
3. Il workflow **Piano AWS manuale senza apply** costruisce il bundle e salva piano,
   bundle e manifest sotto un percorso privato legato a commit e run ID. Il segreto
   Terraform è effimero e usa `value_wo` SSM; non viene scritto nel piano.
4. Revisionare il piano privato, quindi avviare **Apply AWS manuale da piano revisionato**
   sullo stesso commit e con quel run ID. Il workflow verifica entrambi gli hash e
   applica soltanto il piano scaricato. Non esiste deploy da push o pull request.
5. Creare gli utenti di prova e il gruppo moderatore con accesso amministrativo
   dedicato; il prototipo Cognito non consente autoregistrazione. Verificare login,
   PKCE, rinnovo, API, SDK MCP e il client ChatGPT separatamente. Per MCP il token
   deve contenere l'audience della risorsa; per REST un token Cognito standard senza
   `aud` è ammesso solo con issuer, firma, access token e client ID validi.
6. Caricare esclusivamente il seed sintetico e invocare l'aggregatore. I processi
   periodici sono disattivati: abilitarli dopo revisione di costo e fonte.

I ruoli plan/deploy devono leggere alcune risorse Cognito/API Gateway della regione
per gestire ID non noti prima della creazione; revisionare le policy del bootstrap.
Il ruolo deploy può modificare soltanto i quattro ruoli runtime nominati e deve
mantenerne il boundary. Non può modificare il proprio ruolo OIDC.

## Limiti dichiarati

Prototipo con massimo 2.000 dispositivi, 1.000 eventi unificati per dispositivo,
20 alias, 100 fonti e snapshot DynamoDB inferiore a 350 KB. Una coda GSI può essere
arretrata: il record originale protegge autorizzazioni e revisione; la copertura
del censimento dichiara coerenza eventuale. I limiti di scrittura sono distribuiti
per account/minuto e API Gateway applica throttling; non è un sistema completo
di prevenzione abuso per una release pubblica.

Per la release serviranno prove AWS e client reali, misure di latenza/consumo,
strategie per volumi superiori ed export/ripristino amministrativo. Nessuna di queste verifiche viene dichiarata già eseguita.


Il target economico aggiornato e il blocco di rete osservato il 15 ottobre sono
descritti nel [rapporto del primo deploy](primo-deploy-e-costi.md).
