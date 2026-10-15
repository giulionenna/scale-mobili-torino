# Primo deploy AWS e controllo dei costi

15 ottobre 2026. L’utente autorizza il deploy con obiettivo di **pochi centesimi
per il primo collaudo** e poi pochi centesimi con poco traffico. Se il servizio
cresce, il dimensionamento può essere rivisto. Il bootstrap AWS è stato applicato;
le risorse applicative non sono ancora state create.

## Stato verificato

- `STS GetCallerIdentity` riuscito: credenziali funzionanti per identificare un
  utente IAM. Non dimostra permessi di creazione delle risorse.
- Nel nuovo ambiente la policy locale è `unrestricted`; la revisione corrente
  conferma enforcement attivo e credenziali pronte. Le chiamate effettive hanno
  verificato gli endpoint AWS necessari al preflight.
- Milano è `ENABLED`. Inventario regionale paginato: nessuna tabella DynamoDB,
  nessuna HTTP API, tre Lambda, un pool Cognito, tre gruppi log e nessuno scheduler.
  Le risorse preesistenti non sono state modificate.
- Piano account Free attivo e crediti residui verificati tramite
  `GetAccountPlanState`; saldo e scadenza restano nel rapporto privato.
  Free Tier segnala margine per Lambda e log; la stima sotto non lo sottrae.
- Il provider OIDC GitHub esistente ha URL e audience corretti. La simulazione
  IAM consente le principali operazioni di bootstrap e deploy; non dimostra
  che ogni futura creazione riuscirà. Environment GitHub `aws-prototype` assente.
- **Quota Lambda:** quota regionale effettiva 10, tutte non riservate. Per tre
  nuove riserve da uno occorrono almeno 103 esecuzioni non riservate prima del
  deploy, perché AWS ne mantiene almeno 100. Service Quotas conferma quota 10
  modificabile e nessuna richiesta precedente. Un tentativo a 103 con
  `SupportCaseAllowed=false` è stato rifiutato: l'API richiede un valore superiore
  alla quota standard di 1.000. Nessun caso di assistenza è stato aperto.
  L'utente ha quindi autorizzato l'avvio **senza riserve**, condividendo la quota
  regionale esistente anche con gli altri progetti. `reserved_concurrency=-1`
  è il nuovo default; la quota rimane invariata e questo blocco è risolto.
- Preparato, ispezionato e applicato un **piano reale privato del bootstrap**: undici
  creazioni, zero modifiche e zero eliminazioni; riusa il provider OIDC verificato.
  Creati soltanto bucket di stato/configurazioni, boundary e ruoli/policy dedicati.
  Stato conservato fuori dalla repository e copiato nel bucket privato versionato,
  sotto `scale-mobili/bootstrap/terraform.tfstate`. Per questo piano è stato passato
  `budget_reviewed=true` dopo la stima; il default e i workflow restano bloccati.
- Preparato e ispezionato anche un piano applicativo reale privato: 37 creazioni,
  nessuna modifica o eliminazione, tre Lambda senza riserve e nessuno scheduler.
  Non applicato: il deploy applicativo resta affidato ai workflow manuali OIDC.
- L'utente ha completato l'environment `aws-prototype`, con revisore e branch
  `main`. Il primo workflow manuale ha verificato input e avvio, ma l'assunzione
  OIDC è stata rifiutata: il repository usa il prefisso immutabile restituito
  dall'API GitHub (`use_immutable_subject=true`). Il bootstrap ora richiede
  `github_subject_prefix` e conserva esattamente quel prefisso nella trust dei
  due ruoli, senza wildcard. Non si modifica la configurazione OIDC di GitHub.
- Le policy runtime e il boundary ora includono `dynamodb:ConditionCheckItem`:
  le condizioni nelle transazioni richiedono questo permesso oltre a Put/Update.
  Le verifiche con emulatori non dimostravano la correttezza dei permessi IAM.
- Il piano OIDC successivo è riuscito. Il primo apply ha creato parte dello
  stack e salvato lo stato, poi si è fermato: mancavano `ssm:DescribeParameters`
  nel refresh del parametro write-only e `apigateway:TagResource` durante
  CreateStage con i tag predefiniti. CloudTrail ha confermato entrambi i rifiuti.
  Il bootstrap ora autorizza i metadati SSM soltanto nella regione prevista e i
  tag API Gateway soltanto al ruolo deploy. Il recupero richiede un nuovo piano
  sullo stato parziale: il precedente piano non va riapplicato.
- In caso di errore, i workflow conservano i log Terraform soltanto nel bucket
  privato, nello stesso prefisso dei piani con scadenza a sette giorni. Non
  pubblicano contenuto Terraform nei log Actions o negli artifact GitHub.
- **Limite dell'integrazione GitHub:** restituisce HTTP 403 `Resource not accessible
  by integration` per la creazione dell'environment `aws-prototype`, le variabili
  Actions e la chiave pubblica necessaria a scrivere i segreti. L'accesso ADMIN
  dell'utente alla repository non estende i permessi del token dell'integrazione.
  L'utente ha configurato queste risorse dalle impostazioni GitHub. Anche la
  revisione dei job protetti restituisce HTTP 403 all'integrazione: il revisore
  deve usare Review deployments nella pagina Actions. Non trasferire le chiavi
  AWS permanenti su GitHub.
- Cinque test dello stack Terraform con provider simulato, compresa l'opzione
  delle riserve future e il rifiuto di valori frazionari; quattro test bootstrap,
  compresi prefisso OIDC immutabile e rifiuto di un repository differente.
  Validazioni e formattazione riuscite; nessun test crea risorse AWS. Backend:
  70 test passati e pacchetto Lambda verificato in isolamento.

## Configurazione preparata per uso leggero

| Voce | Impostazione |
| --- | --- |
| DynamoDB | Due tabelle Standard e tre GSI; `PAY_PER_REQUEST` predefinito, nessuna capacità fissa prenotata |
| Limiti DynamoDB | 100 unità di lettura e 20 di scrittura/s per tabella e per GSI; limiti best effort |
| Variante provisioned | Opzionale: 7 RCU e 7 WCU totali, soltanto dopo verifica delle inclusioni residue |
| Cognito | Piano `LITE`, Hosted UI classica, utenti creati dall’amministratore; non si attivano funzioni Plus, SMS o login machine-to-machine |
| Lambda | API, aggregatore e collector a consumo, 512 MB; concorrenza condivisa nella quota regionale 10; timeout 15/30/30 secondi |
| HTTP API | 2 richieste/s, burst 10: consente il caricamento delle schede del prototipo |
| Log | Livello WARN, retention di un giorno |
| Processi periodici | Disattivati; primo seed e ricalcolo controllati manualmente |
| S3 | Storage Standard privato, SSE-S3; nessuna chiave KMS del cliente con canone mensile |
| Piani e bundle di deploy | Scadenza dopo sette giorni; un apply successivo richiede un nuovo piano |
| Stato Terraform | Corrente conservato; versioni precedenti per 30 giorni |
| Frontend | Riutilizzo dell’hosting Sites esistente, dopo il deploy dell’API e l’aggiornamento della build |

Non sono previsti VM, NAT Gateway, load balancer, RDS, WAF, domini a pagamento o
concorrenza Lambda preallocata. L’impostazione è per il prototipo; latenza e
throttling vanno misurati prima di aumentare il carico.

La quota DynamoDB provisioned gratuita non copre automaticamente le richieste
on-demand. Il pagamento a consumo evita il canone di capacità se quella quota è
già occupata; se la quota residua è verificata, il provisioned può risultare più
economico. Non si assume la disponibilità di crediti o inclusioni.

I limiti di throughput e gli avvisi di budget **non sono un tetto rigido alla
fattura**. Richieste rifiutate possono comunque avere costi di ingresso; le
notifiche di fatturazione possono arrivare in ritardo. Non è stato ancora creato
un budget AWS né un sistema di notifica. La procedura non promette costo zero.

## Verifica economica prima dell’apply

Il primo scenario è una prova breve con due account sintetici, circa 100 richieste
API, dieci segnalazioni e tre fotografie. Il secondo è un mese leggero con circa
1.000 richieste API complessive, poche decine di segnalazioni e foto compresse.
Le richieste API non equivalgono alle visite: una pagina può farne diverse.

Compilare una stima con tariffe correnti Milano, unità effettive e benefici residui:

| Voce | Base di calcolo |
| --- | --- |
| DynamoDB on-demand | RRU × tariffa lettura + WRU × tariffa scrittura, inclusi transazioni e indici; aggiungere storage |
| Variante provisioned | Ore × (7 × tariffa RCU/ora + 7 × tariffa WCU/ora), sottraendo solo quota residua accertata |
| Lambda | Invocazioni + GB-secondi misurati, incluse partenze a freddo e worker manuali |
| HTTP API | Richieste fatturabili, dimensione dei payload e trasferimenti |
| Cognito Lite | MAU di prova e dell’account/organizzazione, oltre le eventuali inclusioni condivise |
| S3 | Byte-mese di foto, originali, stato, versioni, piani e bundle; PUT/GET/LIST |
| Log | Byte acquisiti e conservati; non si attivano query ricorrenti o metriche personalizzate |
| SSM/KMS | Parametro Standard e operazioni di cifratura/decifratura; AWS-managed KMS non significa ogni operazione gratuita |
| Altri costi | Eventuali trasferimenti, strumenti di fatturazione, GitHub Actions e hosting; cambio e imposte separati |

### Tariffe regionali verificate e stima iniziale

Il 15 ottobre 2026 le API AWS Price List hanno restituito queste tariffe per
`EU (Milan)`, in USD, senza imposte o cambio. Le date di efficacia del catalogo
sono agosto–ottobre 2026, luglio 2025 per KMS.

| Voce | Tariffa utilizzata |
| --- | --- |
| DynamoDB Standard on-demand | 0,1485 USD/milione RRU; 0,74 USD/milione WRU |
| DynamoDB storage | 0,29715 USD/GB-mese, senza sottrarre i primi 25 GB gratuiti |
| Lambda x86 a consumo | 0,23 USD/milione richieste + 0,0000195172 USD/GB-secondo |
| HTTP API | 1,17 USD/milione richieste |
| Cognito Lite | 0,0055 USD/MAU, senza sottrarre inclusioni condivise |
| S3 Standard | 0,024 USD/GB-mese; 0,0053 USD/1.000 PUT/LIST; 0,0004 USD/1.000 GET |
| Log Standard | 0,60 USD/GB acquisito; 0,032 USD/GB-mese conservato |
| KMS simmetrico | 0,03 USD/10.000 richieste; nessuna chiave gestita dal cliente |
| Uscita Internet | 0,09 USD/GB, senza sottrarre la quota gratuita globale |
| SSM Standard, throughput standard | Nessun costo aggiuntivo; entrambe le impostazioni dell'account verificate |

| Ipotesi | Collaudo | Mese leggero |
| --- | --- | --- |
| Richieste HTTP API | 100 | 1.000 |
| Lambda a 512 MB | 100 chiamate da 1 s + due worker da 30 s | 1.000 chiamate da 1 s + due worker da 30 s |
| DynamoDB, incluse transazioni e GSI | 3.000 RRU + 1.000 WRU; 0,001 GB-mese | 30.000 RRU + 5.000 WRU; 0,01 GB-mese |
| Cognito | Due MAU sintetici | Due MAU sintetici |
| S3, inclusi stato/versioni/piano/bundle/foto | 0,05 GB-mese, 200 PUT/LIST, 1.000 GET | 0,1 GB-mese, 500 PUT/LIST, 5.000 GET |
| Log acquisiti, conservazione un giorno | 0,001 GB | 0,01 GB |
| KMS | 103 operazioni | 1.003 operazioni |
| Trasferimento Internet | 0,02 GB | 0,05 GB |
| **Totale arrotondato, prima di crediti e inclusioni** | **0,02 USD** | **0,06 USD** |

Stima condizionata ai volumi indicati, non consumo misurato né tetto garantito.
La durata media di un secondo è da collaudare: timeout ripetuti, più utenti,
foto, richieste o deploy aumentano il costo. Il censimento resta sintetico e
gli scheduler spenti. IAM/OIDC non comportano un canone; non sono previsti budget
con azioni a pagamento. GitHub Actions usa runner standard della repository
pubblica e il frontend riutilizzerebbe il progetto Sites esistente; nessun nuovo
servizio di hosting o dominio viene acquistato.

La stima rientra nell'obiettivo autorizzato. La scelta autorizzata di concorrenza
condivisa consente di procedere con quota 10: a parità di lavoro il prezzo resta
uguale, ma vengono meno la capacità garantita e il tetto individuale per funzione.
Un picco può occupare la quota degli altri progetti o essere rifiutato quando
questa è già esaurita. Per le riserve future basta verificare la quota e impostare
`LAMBDA_RESERVED_CONCURRENCY=1` nelle variabili GitHub prima di un nuovo piano:
nessuna migrazione dati. Non sono stati aperti casi AWS Support o richiesti
cambi di piano dell'account.

Dopo il primo collaudo verificare fatturazione e consumo con il
ritardo dichiarato dal servizio; un costo non ancora registrato non vale zero.
Se la previsione supera il target concordato, presentare le voci prima di creare
risorse. Non usare `budget_reviewed=true` solo per superare il blocco del piano.

## Configurazione di rete (blocco precedente risolto)

In ChatGPT: **Settings → Codex Cloud → Environments → Edit** sull’ambiente del
progetto. Lasciare attivi i package manager e aggiungere gli host seguenti in
**Additional allowed domains**, poi salvare e ripubblicare. Verificare in un nuovo
task; la configurazione pubblicata non implica che il task già attivo la riceva.

```text
sts.amazonaws.com
sts.eu-south-1.amazonaws.com
account.us-east-1.amazonaws.com
iam.amazonaws.com
freetier.us-east-1.amazonaws.com
api.pricing.us-east-1.amazonaws.com
servicequotas.eu-south-1.amazonaws.com
dynamodb.eu-south-1.amazonaws.com
cognito-idp.eu-south-1.amazonaws.com
apigateway.eu-south-1.amazonaws.com
lambda.eu-south-1.amazonaws.com
s3.amazonaws.com
s3.eu-south-1.amazonaws.com
ssm.eu-south-1.amazonaws.com
kms.eu-south-1.amazonaws.com
logs.eu-south-1.amazonaws.com
monitoring.eu-south-1.amazonaws.com
scheduler.eu-south-1.amazonaws.com
budgets.amazonaws.com
```

La lista resta utile se si torna a una policy ristretta. Copre i servizi di controllo previsti, non tutti gli host che potranno
essere generati. Aggiungere gli host effettivi di bucket S3, API distribuita e
dominio Cognito quando noti; Terraform e il backend S3 possono usare host con il
nome del bucket. L’allowlist non assegna permessi IAM e non crea risorse.

Dopo la ripubblicazione:

1. Rileggere lo stato corrente con `cloud_environment.environment_status`.
2. Eseguire `uv run --project backend python scripts/aws_preflight.py` e verificare
   regione, inventario, benefici e concorrenza condivisa disponibile. Per verificare
   le riserve future usare `--reserved-concurrency 1`: tre nuove riserve richiedono
   almeno 103 esecuzioni non riservate prima del deploy.
3. Verificare le tariffe e completare la tabella di stima; definire eventuali
   notifiche di budget con un destinatario concordato.
4. Preparare il piano privato del bootstrap dedicato, ispezionarlo e applicarlo
   entro il budget. Poi configurare OIDC e l’environment GitHub del progetto.
5. Creare il piano applicativo sul commit verificato e distribuire con il workflow
   manuale. Popolare solo dati sintetici e creare utenti di test senza inviti email.
6. Verificare API, login e rinnovo reali, quindi aggiornare il frontend Sites
   mantenendo il suo accesso privato. La demo esistente rimane invariata fino ad allora.

Per fermare rapidamente l’elaborazione si può impostare a zero la concorrenza
riservata delle sole funzioni del progetto; i dati restano conservati. Questo non
elimina storage o fatturazione dell’ingresso API. Una rimozione definitiva va
pianificata sulle risorse dedicate, preservando stato, audit e originali.

## Fonti consultate il 15 ottobre 2026

- [OpenAI: configurazione degli ambienti cloud](https://learn.chatgpt.com/docs/environments/cloud-environments).
- [DynamoDB: prezzi e distinzione tra on-demand e provisioned](https://aws.amazon.com/dynamodb/pricing/).
- [DynamoDB: limiti di throughput on-demand](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/on-demand-capacity-mode-max-throughput.html).
- [Cognito: prezzi e inclusioni condivise](https://aws.amazon.com/cognito/pricing/).
- [Cognito: piani, default Essentials e funzioni Lite](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-sign-in-feature-plans.html).
- [Lambda: prezzi](https://aws.amazon.com/lambda/pricing/).
- [HTTP API: prezzi](https://aws.amazon.com/api-gateway/pricing/).
- [AWS Budgets: ritardi e limiti delle notifiche](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html).
- [AWS Price List: interrogazione delle tariffe](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/using-price-list-query-api.html).
- [Lambda: minimo di 100 esecuzioni non riservate](https://docs.aws.amazon.com/lambda/latest/dg/configuration-concurrency.html).
- [Service Quotas: richiesta e apertura facoltativa del caso di assistenza](https://docs.aws.amazon.com/servicequotas/2019-06-24/apireference/API_RequestServiceQuotaIncrease.html).
- [Piani Free e Paid e loro scadenza](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html).
- [SSM Parameter Store: prezzi Standard](https://aws.amazon.com/systems-manager/pricing/).
- [GitHub OIDC: identificatori immutabili dei nuovi repository](https://docs.github.com/en/actions/reference/security/oidc).
- [DynamoDB: autorizzazioni delle transazioni](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis-iam.html).
