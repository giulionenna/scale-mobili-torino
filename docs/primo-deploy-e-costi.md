# Primo deploy AWS e controllo dei costi

15 ottobre 2026. L’utente autorizza il deploy con obiettivo di **pochi centesimi
per il primo collaudo** e poi pochi centesimi con poco traffico. Se il servizio
cresce, il dimensionamento può essere rivisto. Nessuna risorsa AWS è stata creata.

## Stato verificato

- `STS GetCallerIdentity` riuscito: credenziali funzionanti per identificare un
  utente IAM. Non dimostra permessi di creazione delle risorse.
- Policy della rete `restricted/enforced`: tra i servizi AWS è consentito soltanto
  `sts.amazonaws.com`. Nessuna richiesta è partita verso gli altri endpoint.
- Regione Milano abilitata, risorse presenti, concorrenza Lambda disponibile,
  benefici residui e tariffe regionali: **ancora da verificare**.
- Nessun `terraform plan` reale o `apply` AWS. `budget_reviewed` resta `false`.
- Cinque test Terraform con provider simulato: tre stack e due bootstrap.
  Validazioni e formattazione riuscite; nessun test crea risorse AWS.

## Configurazione preparata per uso leggero

| Voce | Impostazione |
| --- | --- |
| DynamoDB | Due tabelle Standard e tre GSI; `PAY_PER_REQUEST` predefinito, nessuna capacità fissa prenotata |
| Limiti DynamoDB | 100 unità di lettura e 20 di scrittura/s per tabella e per GSI; limiti best effort |
| Variante provisioned | Opzionale: 7 RCU e 7 WCU totali, soltanto dopo verifica delle inclusioni residue |
| Cognito | Piano `LITE`, Hosted UI classica, utenti creati dall’amministratore; non si attivano funzioni Plus, SMS o login machine-to-machine |
| Lambda | API, aggregatore e collector a consumo, 512 MB; concorrenza riservata 1 per funzione; timeout 15/30/30 secondi |
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

**La stima numerica validata resta pendente finché la rete non permette questi
controlli.** Dopo il primo collaudo verificare fatturazione e consumo con il
ritardo dichiarato dal servizio; un costo non ancora registrato non vale zero.
Se la previsione supera il target concordato, presentare le voci prima di creare
risorse. Non usare `budget_reviewed=true` solo per superare il blocco del piano.

## Aggiornare la rete dell’ambiente

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

La lista copre i servizi di controllo previsti, non tutti gli host che potranno
essere generati. Aggiungere gli host effettivi di bucket S3, API distribuita e
dominio Cognito quando noti; Terraform e il backend S3 possono usare host con il
nome del bucket. L’allowlist non assegna permessi IAM e non crea risorse.

Dopo la ripubblicazione:

1. Rileggere lo stato corrente con `cloud_environment.environment_status`.
2. Eseguire `uv run --project backend python scripts/aws_preflight.py` e verificare
   regione, inventario, benefici e concorrenza disponibile. Per riservare tre
   esecuzioni deve restare anche la quota minima non riservata richiesta da AWS.
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
