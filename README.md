# Scale Mobili Torino

Piattaforma civica indipendente per scale mobili e ascensori della metropolitana di Torino. Raccoglie osservazioni della community e le confronta con comunicazioni ufficiali verificabili. Backend del prototipo eseguibile, pacchetto Lambda e Terraform completi per i flussi principali; **nessuna risorsa applicativa AWS creata**.

[Apri l'anteprima privata interattiva](https://scale-mobili-torino-prototipo.tender-tapir-0169.chatgpt.site). Pubblicata con Sites: usa dati fittizi e accesso simulato, conserva le segnalazioni soltanto nella sessione del browser e non è collegata al backend AWS.

## Da leggere

1. [Istruzioni per Codex](AGENTS.md)
2. [Architettura e prova iniziale](docs/architettura-e-prova-iniziale.md)
3. [Modello DynamoDB](docs/modello-dynamodb.md)
4. [Piano operativo per il prototipo](docs/piano-prototipo.md)
5. [Sviluppo e verifiche del primo incremento](docs/sviluppo-e-verifiche.md)
6. [Verifica AWS e configurazione di rete](docs/verifica-iniziale-aws.md)
7. [Interfaccia, segnalazioni e proposte aggiornate](docs/specifiche-interfaccia.md)
8. [Backend: avvio, contratti, collaudo e deploy successivo](docs/backend-deployabile.md)
9. [Frontend collegato alle API: modalità e collaudo](docs/frontend-collegato.md)
10. [Primo deploy AWS e controllo dei costi](docs/primo-deploy-e-costi.md)

Database confermato: **DynamoDB**. Frontend SvelteKit statico, backend Python/Lambda, Cognito, S3, API/MCP e deploy Terraform/GitHub Actions OIDC costituiscono l'impostazione proposta. Le prove devono verificare concretamente funzionamento e consumo. Regione proposta: Milano, `eu-south-1`.

La repository contiene API e MCP condivisi, JWT Cognito, segnalazioni/rettifiche, proposte e foto moderate, archivio delle fonti, statistiche pubbliche/riservate e censimento con alias. La demo backend usa quattro stazioni e nove impianti fittizi. DynamoDB/S3 e persistenza tra riavvii API sono collaudati con emulatori HTTP; lo stack e il blocco budget sono verificati con provider Terraform simulato. Login Cognito, deploy, consumi e client MCP reali saranno verificati dopo l'attivazione autorizzata.

```bash
uv sync --project backend --frozen
SMT_MODE=demo uv run --project backend uvicorn scale_mobili.app:app --host 127.0.0.1 --port 8000
```

Contratto interattivo su `/docs`; backend in memoria per la prova immediata.
Il frontend della repository è ora collegato alle API: home pubblica, login,
segnalazioni con foto, proposte e moderazione. Il sito Sites già pubblicato resta
una demo browser separata; questo incremento non lo modifica e non crea risorse AWS.

Collaudo completo nel cloud, con Chromium disponibile nell’ambiente:

```bash
uv run --project backend python scripts/frontend_api_check.py
```

Il comando avvia frontend, API ed emulatori DynamoDB/S3, prova i flussi dal browser
e li arresta al termine. Per l’avvio interattivo e le modalità di autenticazione,
vedi il [runbook del frontend collegato](docs/frontend-collegato.md).

## Requisiti essenziali

- Progetto da pubblicare open source; nome definitivo, dominio e licenze sono ancora da scegliere.
- Identità distinta e stabile per ogni impianto; identificativi ufficiali solo quando verificati.
- Stati osservabili: funzionante, guasta, manutenzione, non verificabile. Assenza di dati distinta da tutti questi stati.
- Informazioni ufficiali, community e stima separate, con fonte, tempi e freschezza.
- Segnalazioni, conferme e rettifiche tracciate; proposte di censimento e foto moderate.
- Originali GTT conservati con provenienza e hash; acquisizioni registrate anche senza variazioni.
- Statistiche con copertura e metodo; nessuna disponibilità inventata su periodi non osservati.
- API e strumenti MCP con la stessa logica; scritture autenticate e protette da abuso.
- Target concordato: pochi centesimi per il collaudo e per l’uso leggero; verificare tariffe e benefici prima di attivare AWS.
- Sviluppo e distribuzione cloud; nessuna installazione del progetto richiesta sul PC dell'utente.

## Portare il progetto in Codex Cloud

Caricare `README.md`, `AGENTS.md`, `.gitignore` e la cartella `docs` alla radice della repository GitHub. In Codex creare un ambiente cloud collegato a quella repository, completare la preparazione, salvarlo e pubblicarlo. Avviare poi un nuovo task nell'ambiente pubblicato.

La documentazione locale è stata adattata per GitHub: i link tra questi file sono relativi alla repository. Il trasferimento del contesto avviene tramite i file; la conversazione precedente non è richiesta per capire le scelte del progetto.

Per la prima fase bastano gli strumenti di sviluppo e gli accessi alla repository. L'accesso AWS sarà configurato nel passaggio dedicato al deploy, senza chiavi permanenti nella repository.

Percorso ufficiale verificato il 14 ottobre 2026: [Codex Cloud e ambienti](https://learn.chatgpt.com/docs/environments/cloud-environments).
