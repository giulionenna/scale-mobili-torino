# Informativa privacy della beta

La pagina statica `/privacy/` descrive i trattamenti effettivi della beta:
account Cognito, preferiti privati, contributi pubblici, foto moderate, controlli
antiabuso, conservazione e fornitori. Non carica API né richiede un account.
È collegata dal footer, dalla finestra di accesso prima della registrazione,
dal modulo di contribuzione e dai dettagli dei preferiti.

I recapiti del titolare in `frontend/src/lib/privacy-contact.ts` devono essere
quelli scelti espressamente per la pubblicazione. Un indirizzo fornito per
creare un amministratore non viene riutilizzato implicitamente come contatto
pubblico. **Non pubblicare la pagina con nome o email vuoti.**

Le richieste di accesso/cancellazione passano dal recapito indicato. Il titolare
deve verificare in modo proporzionato la richiesta, ricostruire i dati associati
all’account e gestire Cognito, preferiti, contributi e fotografie, valutando
cancellazione o anonimizzazione e aggiornamento delle proiezioni. Non basta
eliminare l’utente Cognito, e il logout non equivale a una cancellazione.
Il sito non promette una procedura self-service che non è implementata.

L’informativa riporta criteri di conservazione per gli account e lo storico,
senza inventare scadenze automatiche. Le durate tecniche descritte derivano da
`infra/storage.tf`, `infra/app.tf`, `infra/identity.tf` e dai record applicativi:
log Lambda un giorno; scadenza upload non elaborati un giorno; ricevute di
idempotenza un giorno; rimozione degli originali dopo elaborazione riuscita.
La scadenza non garantisce l’eliminazione immediata da parte del servizio.

Non vengono aggiunti analytics, pubblicità, banner di consenso generici o
nuovi servizi. Le affermazioni sull’assenza di profilazione sono riferite al
codice applicativo; hosting e autenticazione hanno proprie informative.
AWS conserva i dati applicativi nella regione Milano; l’hosting Sites è
distribuito e i trasferimenti dei fornitori seguono i loro accordi applicabili.

Fonti consultate il 16 ottobre 2026:

- [GDPR](https://eur-lex.europa.eu/eli/reg/2016/679/2016-05-04?locale=it).
- [Garante: contenuti dell’informativa](https://www.garanteprivacy.it/web/guest/home/principi-fondamentali-del-trattamento).
- [Garante: cookie e tracciamento](https://www.garanteprivacy.it/home/docweb/-/docweb-display/docweb/9677876).
- [DPA di ChatGPT Sites](https://openai.com/policies/chatgpt-sites-data-processing-addendum/).
- [AWS: GDPR](https://aws.amazon.com/compliance/gdpr-center/).

Questa modifica non attiva scheduler, backup o avvisi di spesa, e non cambia
autenticazione, ruoli amministrativi o permessi delle API. La pubblicazione
del sito riguarda l’accesso in lettura; contribuzioni e dati personali mantengono
le autorizzazioni applicative esistenti.
