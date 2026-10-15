# Istruzioni per lo sviluppo di Scale Mobili Torino

## Contesto e priorità

Leggere README.md, docs/architettura-e-prova-iniziale.md e docs/modello-dynamodb.md prima di implementare. Le istruzioni dirette dell'utente prevalgono. DynamoDB è la decisione confermata; dettagli di chiavi, indici e componenti proposti vanno convalidati con evidenze e aggiornati nei documenti quando necessario.

L'utente conosce Python e vuole lavorare in cloud senza mantenere un ambiente sul proprio PC. Svolgere autonomamente la preparazione e il lavoro tecnico autorizzato. Usare italiano chiaro nei riepiloghi e distinguere lavoro completato, simulato e ancora da verificare.

## Integrità dei dati

- Non inventare impianti, ID ufficiali, gestori, stati o censimenti.
- I dati sintetici devono essere riconoscibili e isolati dal censimento reale.
- Conservare separatamente osservazione, pubblicazione, acquisizione e registrazione.
- Una fonte GTT che non menziona un impianto non prova che l'impianto funzioni.
- Ufficiale, community e stima restano distinguibili in API, MCP e interfaccia.
- Segnalazioni e rettifiche mantengono riferimenti e audit. Statistiche derivate dichiarano metodo e copertura.
- Foto e dati personali non diventano pubblici senza i controlli applicativi previsti.

## DynamoDB

- Partire dalla matrice degli accessi prima di aggiungere chiavi o indici.
- Usare ID interni immutabili per le chiavi principali e schema_version per i documenti.
- Centralizzare costruzione e interpretazione delle chiavi; API e MCP condividono i servizi applicativi.
- GSI sparsi, con proiezioni minime; nessun LSI iniziale.
- Gestire coerenza eventuale dei GSI, paginazione, scritture condizionate, transazioni e idempotenza.
- Permessi e moderazione sono verificati dal server sui record originali.
- Evitare Scan dello storico nelle richieste pubbliche. Aggregazioni ricalcolabili fuori dalle richieste.
- Valutare insieme consumo, capacità e dimensioni di tabelle e indici.
- Non trattare TTL come un meccanismo di scadenza immediata o come un controllo di autorizzazione.

## Sviluppo e verifica

Preparare codice, build, test significativi e CI nel cloud. Usare dipendenze bloccate e documentare i comandi realmente verificati. I test delle contribuzioni non ricevono accesso AWS.

Testare almeno: accessi e cursori, duplicazione degli invii, correzioni, concorrenza, indici arretrati, mancata autorizzazione, foto non approvate, dati incompleti e ricalcolo delle proiezioni. Emulatori e mock non dimostrano compatibilità o consumi dei servizi reali; elencare esplicitamente le verifiche AWS e dei client ancora necessarie.

Il confronto con giulionenna/mcp-serverless-kit serve a riprendere OIDC, Terraform e workflow manuali. Non riutilizzare automaticamente ruoli, stato, risorse o autenticazione di quel progetto per questa piattaforma pubblica.

## Cloud e budget

Il 15 ottobre 2026 l’utente ha autorizzato il deploy con un obiettivo di pochi centesimi per il primo collaudo e per l’uso successivo a basso traffico; se il servizio cresce, i limiti si possono rivalutare. Prima di attivare la prova AWS, verificare account, benefici residui, regione e stima di tutte le voci; se la previsione supera questo obiettivo, presentare le voci e concordare il passaggio con l’utente. Il traffico non ha un tetto di spesa rigido: throttling e avvisi riducono il rischio ma non lo garantiscono. La disponibilità di una repository non costituisce accesso amministrativo AWS.

Preparare Terraform e workflow di deploy manuali, senza attivazione automatica da push o pull request. Usare GitHub Actions OIDC e credenziali temporanee; mantenere stato e piani Terraform privati. Non inserire credenziali, token, dati personali, foto private o backup nella repository e nei log.

Riferire separatamente CI riuscita, deploy riuscito, login, discovery MCP, chiamate reali e rinnovo OAuth. In una richiesta di preparazione del codice, completare il lavoro senza avviare un deploy AWS non concordato.
