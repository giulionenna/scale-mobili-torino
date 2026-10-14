# Stack del backend, preparato senza deploy

Terraform 1.14.6, provider AWS 6.68.0 bloccato. Modulo principale: DynamoDB/GSI,
Lambda API e worker, HTTP API/MCP, Cognito, S3 privato, SSM, IAM e log. Scheduler
disattivati per default. `bootstrap/` prepara stato privato, OIDC GitHub,
ruoli plan/deploy e permissions boundary dedicati.

Non è stato eseguito alcun plan reale o apply AWS. I quattro test Terraform usano
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
proposta complessiva è 7 RCU e 7 WCU; non garantisce quota residua o costo zero.
Stato, piani e manifest restano privati. I workflow di plan e apply sono manuali,
con OIDC, environment GitHub e verifica degli hash del commit revisionato.

Procedura completa, variabili, prove e limiti nel
[runbook del backend](../docs/backend-deployabile.md).
