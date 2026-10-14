# Infrastruttura preparatoria

Questo modulo prepara soltanto le due tabelle DynamoDB e i tre GSI del modello.
Non distribuisce ancora Lambda, API Gateway, Cognito, S3 o CloudFront e non costituisce
il deploy del prototipo. La capacità proposta complessiva è 7 RCU e 7 WCU, senza
autoscaling: disponibilità gratuita e adeguatezza richiedono le verifiche reali.

`budget_reviewed` è false per impostazione iniziale: un plan operativo richiede
prima la verifica economica documentata. Il controllo non prova da solo la gratuità.
Il backend S3 resta privato, cifrato e con lock; creare o riutilizzare uno spazio
dedicato soltanto dopo la verifica dell'account. Non salvare file di backend reali,
stato o piani nella repository.

Per la CI senza AWS: `terraform init -backend=false` e `terraform validate`.
La procedura manuale preparata in GitHub Actions produce soltanto un piano privato;
non applica modifiche. Bootstrap OIDC, permessi minimi, inventario, verifica del
provider esistente e workflow di apply appartengono alla fase 4 ancora da completare.
