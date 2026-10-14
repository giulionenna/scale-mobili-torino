# Scale Mobili Torino

Progetto di una piattaforma civica indipendente che censisce le scale mobili della metropolitana di Torino, raccoglie osservazioni della community e le confronta con comunicazioni ufficiali verificabili. È disponibile un primo incremento dimostrativo con dati sintetici; il deploy AWS resta da verificare e realizzare.

[Apri l'anteprima privata interattiva](https://scale-mobili-torino-prototipo.tender-tapir-0169.chatgpt.site). Pubblicata con Sites: usa dati fittizi e accesso simulato, conserva le segnalazioni soltanto nella sessione del browser e non è collegata al backend AWS.

## Da leggere

1. [Istruzioni per Codex](AGENTS.md)
2. [Architettura e prova iniziale](docs/architettura-e-prova-iniziale.md)
3. [Modello DynamoDB](docs/modello-dynamodb.md)
4. [Piano operativo per il prototipo](docs/piano-prototipo.md)
5. [Sviluppo e verifiche del primo incremento](docs/sviluppo-e-verifiche.md)
6. [Verifica AWS e configurazione di rete](docs/verifica-iniziale-aws.md)
7. [Interfaccia, segnalazioni e proposte aggiornate](docs/specifiche-interfaccia.md)

Database confermato: **DynamoDB**. Frontend SvelteKit statico, backend Python/Lambda, Cognito, S3, API/MCP e deploy Terraform/GitHub Actions OIDC costituiscono l'impostazione proposta. Le prove devono verificare concretamente funzionamento e consumo. Regione proposta: Milano, `eu-south-1`.

La repository contiene backend Python/API/MCP, frontend SvelteKit statico, test, CI e un modulo Terraform iniziale per DynamoDB. La demo usa un archivio in memoria con una stazione e due impianti fittizi. L'adattatore DynamoDB è stato verificato con un emulatore; autenticazione Cognito, infrastruttura completa e deploy AWS restano da completare. Le verifiche distinguono simulazioni, emulatori, servizi AWS reali e client MCP reali.

## Requisiti essenziali

- Progetto da pubblicare open source; nome definitivo, dominio e licenze sono ancora da scegliere.
- Identità distinta e stabile per ogni impianto; identificativi ufficiali solo quando verificati.
- Stati osservabili: funzionante, guasta, manutenzione, non verificabile. Assenza di dati distinta da tutti questi stati.
- Informazioni ufficiali, community e stima separate, con fonte, tempi e freschezza.
- Segnalazioni, conferme e rettifiche tracciate; proposte di censimento e foto moderate.
- Originali GTT conservati con provenienza e hash; acquisizioni registrate anche senza variazioni.
- Statistiche con copertura e metodo; nessuna disponibilità inventata su periodi non osservati.
- API e strumenti MCP con la stessa logica; scritture autenticate e protette da abuso.
- Budget iniziale zero: verificare quote e voci residue prima di attivare servizi AWS.
- Sviluppo e distribuzione cloud; nessuna installazione del progetto richiesta sul PC dell'utente.

## Portare il progetto in Codex Cloud

Caricare `README.md`, `AGENTS.md`, `.gitignore` e la cartella `docs` alla radice della repository GitHub. In Codex creare un ambiente cloud collegato a quella repository, completare la preparazione, salvarlo e pubblicarlo. Avviare poi un nuovo task nell'ambiente pubblicato.

La documentazione locale è stata adattata per GitHub: i link tra questi file sono relativi alla repository. Il trasferimento del contesto avviene tramite i file; la conversazione precedente non è richiesta per capire le scelte del progetto.

Per la prima fase bastano gli strumenti di sviluppo e gli accessi alla repository. L'accesso AWS sarà configurato nel passaggio dedicato al deploy, senza chiavi permanenti nella repository.

Percorso ufficiale verificato il 14 ottobre 2026: [Codex Cloud e ambienti](https://learn.chatgpt.com/docs/environments/cloud-environments).
