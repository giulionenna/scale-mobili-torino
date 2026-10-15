# Deploy e collaudo AWS del prototipo

15 ottobre 2026. Backend distribuito in **Milano, eu-south-1**, tramite workflow
manuali GitHub Actions/OIDC. Il [sito privato](https://scale-mobili-torino-prototipo.tender-tapir-0169.chatgpt.site)
usa ora le API AWS, Cognito e persistenza DynamoDB/S3. Accesso di sviluppo e
archiviazione demo nel browser sono disattivati nella build pubblicata.

Il censimento contiene quattro stazioni e dieci impianti **fittizi**: nove dal
seed e uno approvato durante il collaudo. Anche le osservazioni e le foto sono
sintetiche. Non sono dati GTT né misure della disponibilità reale della metro.
Due account di prova, cittadino e moderatore, sono stati creati con inviti email
soppressi; password e token non sono nella repository o nei log pubblici.

## Esiti verificati sui servizi reali

| Verifica | Esito |
| --- | --- |
| Deploy OIDC da piano privato e bundle del commit revisionato | Riuscito |
| Health Lambda/API, catalogo e ricalcolo da DynamoDB | Riusciti |
| Cognito authorization code, PKCE e ritorno alla pagina richiesta | Riusciti per entrambi gli account |
| Audience MCP e rinnovo del token dal frontend | Verificati prima e dopo il refresh |
| API senza login, token demo in AWS e moderazione da cittadino | Rifiutati con 401/403 |
| Invio ripetuto con la stessa chiave e corpo | Stesso risultato, nessun duplicato |
| Stessa chiave con corpo diverso | Conflitto 409 |
| Foto S3 privata, ricodifica JPEG senza EXIF, revisione e immagine pubblica | Verificate; 404 prima dell'approvazione |
| Proposta fuori dal censimento fino all'approvazione | Verificata; impianto approvato ancora synthetic |
| Nuovo processo, Lambda di aggregazione e nuova sessione browser | Leggono i dati persistiti |
| SDK MCP Python 1.30.0 su HTTP AWS | Initialize, discovery, lettura pubblica, rifiuto senza login, statistiche riservate e scrittura idempotente riusciti |
| Frontend effettivamente ospitato da Sites | Login/rinnovo reali e invio dal browser con upload S3/CORS riusciti |
| Riservatezza del sito e della nuova foto | Accesso anonimo al sito bloccato; foto appena inviata ancora privata |
| Layout mobile a 390 px | Nessuno scorrimento orizzontale |

Il collaudo del contenuto ospitato usa il token di servizio Sites esistente,
in memoria e inviato solo all'origine del sito, per accedere alla pubblicazione
privata. Non sostituisce un collaudo interattivo dell'accesso ChatGPT del visitatore.

## Configurazione OAuth verificata

Managed login richiede **Cognito Essentials** per il resource binding usato da MCP.
Il resource server ha come identificatore l'URL MCP; gli scope custom appartengono
allo stesso identificatore. Il frontend legge gli scope da `/api/config`, la
resource discovery pubblica gli stessi valori e il backend riconosce soltanto
quelli della propria risorsa. I token MCP senza audience esatta restano rifiutati.

Il callback applicativo è `/auth/cognito`. `/callback` resta riservato a Sites
per l'accesso ChatGPT. Il pool non permette autoregistrazione e il client web
è pubblico, senza client secret, con authorization code e PKCE.

Il provider AWS richiede anche `ListUserPoolClients` durante il refresh del
branding, oltre alle due letture DescribeManagedLoginBranding. I ruoli OIDC
hanno queste letture di metadati; il ruolo plan non legge gli oggetti S3 applicativi.

## Costi e limiti

La quota regionale Lambda resta **10**, condivisa, senza riserve per funzione.
Nessuno scheduler è attivo; il ricalcolo finale della snapshot è stato invocato
manualmente. Tabelle/GSI a consumo, limiti 100 letture e 20 scritture/s per
risorsa; HTTP API 2 richieste/s con burst 10; log WARN conservati un giorno.

La stima conservativa è **0,04 USD per il collaudo** e **0,08 USD/mese** con
1.000 richieste API e due MAU, prima di crediti, inclusioni e imposte. Ipotesi e
tariffe nel [rapporto economico](primo-deploy-e-costi.md). Non è un tetto di spesa.

Il piano account Free è stato ricontrollato ed è attivo. Nel campione CloudWatch
raccolto durante il collaudo risultano 121 invocazioni API e due aggregazioni,
con zero errori Lambda; durata media API circa 306 ms. Il campione può essere
incompleto per il ritardo delle metriche e non è una fattura. Saldo crediti e
stato dell'account restano nel rapporto privato; non si deduce costo nullo da
un addebito non ancora registrato. Non sono state eseguite query Cost Explorer.

## Provenienza e controlli del codice

- Stack applicativo: commit `3fa0670dcbe6ea66c8ba1c61b03e941ab37ac563`,
  [piano 38747486937](https://github.com/giulionenna/scale-mobili-torino/actions/runs/38747486937)
  e [apply 38748395621](https://github.com/giulionenna/scale-mobili-torino/actions/runs/38748395621).
- Source repository Sites: commit `9a8773a7ca58c069b7f9a9ca5915d99f7930cd59`.
  Archivio con solo manifest di hosting e build statica; stesso progetto e accesso
  owner-private esistenti. Pubblicazione nativa riuscita, poi collaudata sul browser.
- CI delle modifiche applicative: sei controlli riusciti, 71 test backend,
  cinque test stack e quattro bootstrap con provider simulato; Ruff, build,
  check Svelte e collaudo completo browser/API con emulatori riusciti.

L'utente ha rimosso Required reviewers dall'environment GitHub per consentire
l'esecuzione autonoma. Restano environment limitato a main, workflow manuali,
OIDC e revisione del piano esatto prima dell'apply. Non esiste deploy automatico
da push o pull request.

## Limiti del collaudo

Non sono verificati il collegamento nativo di ChatGPT/altri client MCP, una
registrazione dinamica dei client, traffico di carico o failover. La persistenza
fra riavvii dell'API è coperta anche dal collaudo con emulatori; in AWS sono
verificati letture da processi indipendenti e storage reale. Non è stata forzata
una modifica della configurazione Lambda per simulare un riavvio.

Nessuna fonte reale è collegata agli impianti sintetici e nessuna acquisizione
GTT è stata simulata come ufficiale. Un account personale Cognito non è stato
creato: i due account usati qui sono esclusivamente di collaudo.
