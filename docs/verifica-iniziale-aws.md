# Verifica AWS iniziale

14 ottobre 2026, con aggiornamento del 15 ottobre. Nessuna risorsa AWS creata.
Nessun deploy o bootstrap eseguito. Il target aggiornato e la configurazione a
consumo sono nel [rapporto del primo deploy](primo-deploy-e-costi.md); le sezioni
seguenti conservano anche il confronto iniziale con provisioned.

## Esiti reali e limiti

`STS GetCallerIdentity` è riuscito con le credenziali dell'ambiente. È un'identità
IAM di tipo utente; non si conservano account ID o ARN nella documentazione pubblica.
Questo risultato non dimostra permessi amministrativi, disponibilità del Free Tier
o abilitazione di Milano.

La policy di rete corrente è restricted/enforced e consente STS, oltre ai domini
predefiniti di sviluppo. Lo script [aws_preflight.py](../scripts/aws_preflight.py)
è stato eseguito e ha saltato gli endpoint non consentiti: regione, OIDC, risorse
DynamoDB, Cognito, API Gateway, Lambda, Scheduler, log, Free Tier e catalogo prezzi
restano **da verificare**. Non sono fallimenti IAM: nessuna richiesta è partita
verso quei servizi. Lo script riporta soltanto dati riepilogativi, senza credenziali,
identità o messaggi SDK completi.

Comando verificato nell'ambiente cloud:

```bash
uv run --project backend python scripts/aws_preflight.py
```

Lo script legge lo snapshot locale della policy per decidere quali chiamate saltare.
Dopo una modifica dell'ambiente controllare anche la readiness corrente tramite
`cloud_environment.environment_status`; uno snapshot iniziale può diventare vecchio.
Le prime pagine degli inventari non certificano un censimento completo e l'accesso
al catalogo prezzi non è ancora una stima economica.

## Domini richiesti

Configurare i domini attraverso le impostazioni dell'ambiente Codex, non modificando
il file della policy: il controllo è applicato dal proxy. I nomi AWS sono stati
confermati dalla risoluzione endpoint del SDK boto3 installato, senza chiamare i servizi.

```text
sts.amazonaws.com
account.us-east-1.amazonaws.com
iam.amazonaws.com
freetier.us-east-1.amazonaws.com
api.pricing.us-east-1.amazonaws.com
dynamodb.eu-south-1.amazonaws.com
servicequotas.eu-south-1.amazonaws.com
cognito-idp.eu-south-1.amazonaws.com
apigateway.eu-south-1.amazonaws.com
lambda.eu-south-1.amazonaws.com
s3.eu-south-1.amazonaws.com
cloudfront.amazonaws.com
logs.eu-south-1.amazonaws.com
scheduler.eu-south-1.amazonaws.com
```

Per le successive acquisizioni reali serviranno anche `www.gtt.to.it` e `gtt.to.it`.
Per login e chiamate ai servizi distribuiti si aggiungeranno i domini effettivi del
pool Cognito, dell'API, della distribuzione e degli oggetti S3. Se il catalogo prezzi
restituisce URL di listini da scaricare, verificare anche quei domini.

## Budget zero: cosa è noto

Le pagine ufficiali sono state consultate il 14 ottobre 2026; le condizioni per
questo specifico account restano da verificare.

| Voce | Condizione pubblicata e controllo richiesto |
| --- | --- |
| DynamoDB Standard/provisioned | La quota gratuita pubblicata è 25 RCU, 25 WCU e 25 GB per regione/payer account. Il modulo preparato propone **7 RCU e 7 WCU totali**, sommando due tabelle e tre GSI. Verificare capacità già allocata e storage nel payer account. |
| CloudFront | È pubblicato un piano Free a 0 USD/mese con inclusioni proprie. Verificare idoneità e modalità di sottoscrizione: il modulo preparato non crea ancora una distribuzione né sottoscrive quel piano. |
| Cognito | È pubblicata una quota di 10.000 MAU per accessi diretti/social in Lite/Essentials, condivisa per account/organizzazione. Verificare utilizzo corrente; email/SMS e funzioni aggiuntive richiedono controllo separato. |
| HTTP API | Le offerte gratuite e i crediti dipendono dall'età e dal piano dell'account. Non considerarli permanenti o automaticamente disponibili. |
| S3, Lambda, Scheduler, log, stato Terraform, backup | Richieste, storage, versioni, durata, retention, trasferimenti e operazioni di recupero vanno conteggiati. Le inclusioni CloudFront non coprono automaticamente tutto il backend. |

Fonti: [DynamoDB](https://aws.amazon.com/dynamodb/pricing/),
[CloudFront](https://aws.amazon.com/cloudfront/pricing/),
[Cognito](https://aws.amazon.com/cognito/pricing/),
[API Gateway](https://aws.amazon.com/api-gateway/pricing/).

## Stima ancora da completare

Non è disponibile una stima verificata delle tariffe regionali e della copertura
residua. Il totale è **non determinato**, non zero. Prima del deploy compilare:

- prova: ore di attivazione, circa 100 letture, 10 segnalazioni, 3 foto, acquisizioni
  controllate, pacchetto Lambda, file web, log, stato e ripristino;
- mese: 10.000 richieste dinamiche, 100 segnalazioni, 100 foto compresse, sei
  acquisizioni giornaliere, dimensione dei file e archivio corrente;
- DynamoDB: `ore × (7 × tariffa RCU/ora + 7 × tariffa WCU/ora)`, poi storage e
  operazioni extra; sottrarre soltanto benefici realmente disponibili;
- altri servizi: unità effettive × tariffa Milano/servizio, separando costo lordo,
  benefici residui, crediti, tasse e costo netto.

Le transazioni aumentano il consumo e gli indici ricevono scritture; la proposta di
capacità non è una misura di adeguatezza. Avvisi e throttling non sono un tetto di
spesa. Se si rilevano costi non coperti, presentarli prima dell'attivazione.

La fase 1 del piano rimane aperta. La preparazione di codice, test e build è proseguita
senza attivare servizi AWS.
