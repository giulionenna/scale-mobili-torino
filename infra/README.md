# Stack del backend, preparato senza deploy

Terraform 1.14.6, provider AWS 6.68.0 bloccato. Modulo principale: DynamoDB/GSI,
Lambda API e worker, HTTP API/MCP, Cognito, S3 privato, SSM, IAM e log. Scheduler
disattivati per default. `bootstrap/` prepara stato privato, OIDC GitHub,
ruoli plan/deploy e permissions boundary dedicati.

Il bootstrap richiede `github_subject_prefix` dall'API
`GET /repos/OWNER/REPO/actions/oidc/customization/sub` (`sub_claim_prefix`).
Per i repository nuovi GitHub include gli ID immutabili di proprietario e repo:
conservarli nella trust, senza sostituirli con il solo nome.
Le transazioni DynamoDB autorizzano le singole operazioni, incluso
`dynamodb:ConditionCheckItem`, sia nella policy runtime sia nel boundary.
Il provider legge anche configurazione MFA Cognito e code-signing Lambda.
`CreateUserPool` e `DescribeUserPoolDomain` non supportano ARN specifici: la
creazione è vincolata a regione e tag Project/Environment, la lettura alla regione.

Il 15 ottobre è stato preparato e ispezionato un piano reale privato del solo
bootstrap: undici creazioni, nessuna modifica o eliminazione, riuso del provider
OIDC esistente. Il bootstrap è stato applicato; il suo stato è fuori dalla repo
e nel bucket privato. Piano applicativo reale privato: 37 creazioni, non applicate
per il blocco GitHub su environment, variabili e segreti (HTTP 403). I test Terraform usano
`mock_provider aws`; il loro apply è soltanto una simulazione.

```bash
python scripts/build_lambda.py
terraform -chdir=infra init -backend=false -input=false
terraform -chdir=infra fmt -check -recursive
terraform -chdir=infra validate
terraform -chdir=infra test
terraform -chdir=infra/bootstrap init -backend=false -input=false
terraform -chdir=infra/bootstrap validate
terraform -chdir=infra/bootstrap test
```

`example.tfvars` è un esempio non caricato automaticamente. Frontend HTTPS,
boundary e segreto effimero sono input obbligatori. Non salvare il segreto in un
file: usare `TF_VAR_cursor_secret`. Il parametro SSM usa `value_wo`; la versione
controlla le rotazioni deliberate. I riferimenti firmati già distribuiti richiedono
una strategia di migrazione prima di ruotare la chiave.

Il flag `budget_reviewed` è false per default e blocca il piano. L'allocazione
predefinita è a consumo (`PAY_PER_REQUEST`), con massimo 100 unità di lettura e 20 di scrittura al secondo per tabella/GSI. La modalità opzionale provisioned alloca 7 RCU e 7 WCU complessive e richiede la verifica del Free Tier residuo. I limiti non sono un tetto alla fattura.
Stato, piani e manifest restano privati. I workflow di plan e apply sono manuali,
con OIDC, environment GitHub e verifica degli hash del commit revisionato.

Procedura completa, variabili, prove e limiti nel
[runbook del backend](../docs/backend-deployabile.md).

Configurazione di costo ridotto: Cognito Lite/Hosted UI classica, concorrenza
Lambda condivisa (`reserved_concurrency=-1`), log WARN con retention di un giorno, API 2 richieste/s
con burst 10 e scheduler spenti. Vecchi bundle/piani scadono dopo sette giorni;
lo stato Terraform corrente resta conservato.

Il deploy è autorizzato entro il target di pochi centesimi per collaudo e uso
leggero. Rete, regione e tariffe sono ora verificate. L'utente ha autorizzato
l'avvio con la quota Lambda esistente di 10, senza riserve per funzione.
`LAMBDA_RESERVED_CONCURRENCY` nelle variabili GitHub permette di attivarle in
futuro dopo la verifica della quota. Sono state create solo risorse di bootstrap. Vedi
[il rapporto del primo deploy](../docs/primo-deploy-e-costi.md).
