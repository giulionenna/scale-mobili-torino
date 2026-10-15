# Stack del backend, preparato senza deploy

Terraform 1.14.6, provider AWS 6.68.0 bloccato. Modulo principale: DynamoDB/GSI,
Lambda API e worker, HTTP API/MCP, Cognito, S3 privato, SSM, IAM e log. Scheduler
disattivati per default. `bootstrap/` prepara stato privato, OIDC GitHub,
ruoli plan/deploy e permissions boundary dedicati.

Il 15 ottobre è stato preparato e ispezionato un piano reale privato del solo
bootstrap: undici creazioni, nessuna modifica o eliminazione, riuso del provider
OIDC esistente. Nessun apply AWS è stato eseguito. I cinque test Terraform usano
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

Configurazione di costo ridotto: Cognito Lite/Hosted UI classica, una esecuzione
concorrente per funzione, log WARN con retention di un giorno, API 2 richieste/s
con burst 10 e scheduler spenti. Vecchi bundle/piani scadono dopo sette giorni;
lo stato Terraform corrente resta conservato.

Il deploy è autorizzato entro il target di pochi centesimi per collaudo e uso
leggero. Rete, regione e tariffe sono ora verificate; la quota Lambda effettiva
di 10 impedisce le tre riserve da uno (servono almeno 103 non riservate prima
del deploy). Nessuna risorsa è stata creata. Vedi
[il rapporto del primo deploy](../docs/primo-deploy-e-costi.md).
