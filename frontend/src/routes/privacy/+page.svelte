<script lang="ts">
  import Icon from "$lib/Icon.svelte";
  import { privacyContact } from "$lib/privacy-contact";
  const requestLink = `mailto:${privacyContact.email}?subject=${encodeURIComponent("Richiesta privacy · Scale Mobili Torino")}`;
</script>

<svelte:head>
  <title>Privacy e cookie · Scale Mobili Torino</title>
  <meta
    name="description"
    content="Come trattiamo account, preferiti, segnalazioni e fotografie, e come esercitare i tuoi diritti."
  />
  <meta name="robots" content="noindex,nofollow" />
</svelte:head>

<header class="privacy-header">
  <a class="privacy-brand" href="/home/"
    ><Icon name="stairs" size={27} /><span
      >Scale Mobili <strong>Torino</strong></span
    ></a
  >
  <a href="/home/">Torna alla panoramica →</a>
</header>
<main class="privacy-page">
  <p class="eyebrow">I TUOI DATI</p>
  <h1>Privacy e cookie</h1>
  <p class="privacy-intro">
    Puoi consultare gli impianti senza un account. Per contribuire usiamo
    un’email verificata; i tuoi preferiti restano privati. Le segnalazioni sono
    pubbliche, le foto solo dopo la revisione.
  </p>
  <p class="privacy-updated">
    Informativa ai sensi degli articoli 13 e 14 del Regolamento UE 2016/679 · 16
    ottobre 2026 · beta pubblica
  </p>
  <nav class="privacy-index" aria-label="Indice dell’informativa">
    <a href="#titolare">Titolare e contatti</a><a href="#dati"
      >Dati e finalità</a
    ><a href="#pubblico">Contenuti pubblici</a><a href="#conservazione"
      >Conservazione</a
    ><a href="#fornitori">Fornitori</a><a href="#cookie">Cookie</a><a
      href="#diritti">I tuoi diritti</a
    >
  </nav>

  <section id="titolare">
    <h2>1. Titolare e contatti</h2>
    <p>
      Il titolare del trattamento è <strong>{privacyContact.name}</strong>,
      gestore del progetto civico indipendente Scale Mobili Torino, non
      affiliato a GTT.
    </p>
    <p>
      Per informazioni sui dati, cancellazione dell’account o rimozione di un
      contenuto, scrivi a <a href={requestLink}>{privacyContact.email}</a>. Le
      richieste vengono gestite dal titolare; nella beta non è presente un
      pulsante di cancellazione automatica.
    </p>
  </section>

  <section id="dati">
    <h2>2. Dati, finalità e basi giuridiche</h2>
    <div class="privacy-table-wrap">
      <table>
        <thead
          ><tr
            ><th>Quando</th><th>Dati e utilizzo</th><th>Base giuridica</th></tr
          ></thead
        >
        <tbody>
          <tr
            ><th>Visiti il sito</th><td
              >I fornitori ricevono indirizzo IP, richieste di rete,
              informazioni del browser e dati tecnici per consegnare le pagine e
              proteggere il servizio.</td
            ><td
              >Legittimo interesse al funzionamento e alla sicurezza, art. 6.1.f
              GDPR.</td
            ></tr
          >
          <tr
            ><th>Crei un account</th><td
              >Email, verifica, identificativo interno, credenziali gestite dal
              servizio di autenticazione e ruolo. Servono per accesso, recupero
              password, permessi e attribuzione interna dei contributi.</td
            ><td>Esecuzione del servizio richiesto, art. 6.1.b GDPR.</td></tr
          >
          <tr
            ><th>Salvi i preferiti</th><td
              >Stazioni scelte e aggiornamento, associati al tuo account, per
              riproporre il percorso e chiederti un’osservazione al successivo
              accesso.</td
            ><td>Esecuzione del servizio richiesto, art. 6.1.b GDPR.</td></tr
          >
          <tr
            ><th>Invii contributi</th><td
              >Impianto, stato, date, eventuale descrizione e foto, conferme e
              rettifiche. Le proposte includono le indicazioni per riconoscere
              l’impianto. Conserviamo il collegamento interno all’account per
              gestire storico e rettifiche.</td
            ><td
              >Esecuzione del servizio di contribuzione e pubblicazione che
              richiedi, art. 6.1.b GDPR.</td
            ></tr
          >
          <tr
            ><th>Gestiamo abusi e revisioni</th><td
              >Identificativi, contatori di invio, esiti e decisioni di
              moderazione, per limitare abusi, proteggere foto private e
              correggere errori.</td
            ><td
              >Legittimo interesse alla sicurezza e all’integrità del servizio,
              art. 6.1.f GDPR.</td
            ></tr
          >
          <tr
            ><th>Ci contatti</th><td
              >Email e messaggio per rispondere alla richiesta. Non inviare
              documenti d’identità o altri dati non richiesti.</td
            ><td
              >Gestione della richiesta, art. 6.1.b; adempimenti sui diritti
              privacy, art. 6.1.c GDPR.</td
            ></tr
          >
        </tbody>
      </table>
    </div>
    <p>
      La registrazione è necessaria per contribuire e salvare preferiti.
      Descrizioni e fotografie sono facoltative. Non chiediamo posizione GPS,
      dati sanitari o documenti d’identità. Le stazioni preferite non
      costituiscono un tracciamento della tua posizione.
    </p>
    <p>
      Il censimento e le informazioni ufficiali provengono dai documenti GTT
      citati nelle schede. Gli stati della community derivano dalle osservazioni
      inviate volontariamente.
    </p>
  </section>

  <section id="pubblico">
    <h2>3. Cosa diventa pubblico</h2>
    <p>
      Inviando chiedi di pubblicare impianto, stato, orari, descrizione ed
      eventuali rettifiche. Le proposte di censimento vengono verificate prima
      dell’inserimento. Le foto diventano pubbliche solo dopo l’approvazione di
      un moderatore.
    </p>
    <p>
      <strong
        >Email, preferiti e identificativo dell’autore non compaiono nelle
        risposte pubbliche delle segnalazioni.</strong
      > Il collegamento all’account resta interno alle funzioni autorizzate. Le foto
      in attesa sono accessibili solo al proprietario e ai moderatori autorizzati.
    </p>
    <p>
      I contributi pubblicati sono consultabili e copiabili da chiunque, anche
      tramite API e MCP. La rimozione dal sito non garantisce la cancellazione
      delle copie effettuate da terzi.
    </p>
    <p>
      Fotografa l’impianto evitando volti riconoscibili, minori, targhe e
      documenti. Non inserire dati personali o sanitari nelle descrizioni. Le
      immagini vengono ricodificate senza metadati EXIF prima della
      pubblicazione; questo non elimina le informazioni personali visibili nella
      foto.
    </p>
  </section>

  <section id="conservazione">
    <h2>4. Conservazione</h2>
    <ul>
      <li>
        <strong>Account e preferiti:</strong> per la durata dell’account, fino alla
        chiusura o alla richiesta di cancellazione, salvo dati necessari per obblighi
        di legge o contestazioni. Nella beta non è configurata una cancellazione automatica
        degli account inattivi.
      </li>
      <li>
        <strong>Contributi e revisioni:</strong> finché necessari a rendere consultabile
        e verificabile lo storico degli impianti. Le informazioni personali non necessarie
        vengono rimosse o anonimizzate a seguito della valutazione di una richiesta
        di cancellazione. Lo storico tecnico non implica la conservazione illimitata
        dell’identità dell’autore.
      </li>
      <li>
        <strong>Foto:</strong> finché necessarie alla proposta, alla revisione o al
        contributo cui sono collegate. Puoi richiederne la rimozione. Gli originali
        vengono eliminati dopo l’elaborazione riuscita; gli upload non elaborati hanno
        una scadenza configurata di un giorno, con i tempi tecnici dell’archiviazione.
      </li>
      <li>
        <strong>Log applicativi AWS:</strong> conservazione configurata di un giorno.
        I contatori antiabuso hanno scadenza breve e le ricevute che evitano duplicazioni
        scadono dopo un giorno; la pulizia tecnica può avvenire successivamente.
      </li>
      <li>
        <strong>Messaggi e richieste privacy:</strong> per il tempo necessario alla
        risposta e alla documentazione dell’esito, e per eventuali obblighi di legge
        o contestazioni.
      </li>
    </ul>
    <p>
      Questi criteri riguardano i dati gestiti dal progetto. I fornitori possono
      conservare propri dati tecnici, di sicurezza o relativi ai loro account
      secondo le rispettive informative. Per un caso concreto puoi contattare il
      titolare.
    </p>
  </section>

  <section id="fornitori">
    <h2>5. Fornitori e trasferimenti</h2>
    <p>
      Il titolare e i moderatori autorizzati accedono ai dati necessari alle
      rispettive funzioni. Utilizziamo Amazon Web Services per autenticazione,
      API, archiviazione e sicurezza, con dati applicativi configurati nella
      regione Milano, e OpenAI ChatGPT Sites per l’hosting.
    </p>
    <p>
      L’hosting è distribuito e non tutti i trattamenti tecnici sono limitati
      all’Italia. Gli accordi dei fornitori prevedono, per eventuali
      trasferimenti fuori dallo Spazio economico europeo, garanzie applicabili
      come decisioni di adeguatezza o clausole contrattuali standard UE. Sono
      consultabili l’<a
        href="https://openai.com/policies/chatgpt-sites-data-processing-addendum/"
        target="_blank"
        rel="noreferrer">accordo sul trattamento dei dati di ChatGPT Sites</a
      >, i suoi
      <a
        href="https://platform.openai.com/subprocessors"
        target="_blank"
        rel="noreferrer">subfornitori</a
      >
      e le
      <a
        href="https://aws.amazon.com/compliance/gdpr-center/"
        target="_blank"
        rel="noreferrer">informazioni AWS</a
      >. Puoi richiedere dettagli al titolare.
    </p>
    <p>
      Il progetto non vende i dati e non li usa per pubblicità. Se scegli
      un’applicazione esterna per accedere ad API o MCP, quell’applicazione
      tratta le informazioni che le trasmetti secondo le proprie condizioni.
    </p>
  </section>

  <section id="cookie">
    <h2>6. Cookie e memoria del browser</h2>
    <p>
      Il codice dell’app non integra pubblicità, profilazione o analytics di
      terze parti. I caratteri tipografici sono serviti dal sito.
    </p>
    <p>
      La memoria di sessione del browser mantiene l’accesso, il ritorno dopo il
      login e l’avvenuta verifica dei preferiti. L’uscita rimuove i token
      applicativi; la chiusura della scheda termina normalmente la memoria di
      sessione, secondo il comportamento del browser.
    </p>
    <p>
      Autenticazione e hosting possono usare cookie e altri strumenti tecnici
      propri per accesso e sicurezza. Consulta anche le informative di <a
        href="https://aws.amazon.com/privacy/"
        target="_blank"
        rel="noreferrer">AWS</a
      >
      e
      <a
        href="https://openai.com/policies/privacy-policy/"
        target="_blank"
        rel="noreferrer">OpenAI</a
      >. Bloccare gli strumenti necessari può impedire l’accesso alle funzioni
      personali.
    </p>
  </section>

  <section id="diritti">
    <h2>7. I tuoi diritti</h2>
    <p>
      Nei casi previsti dal GDPR puoi chiedere accesso e copia dei dati,
      rettifica, cancellazione, limitazione, portabilità e opposizione ai
      trattamenti fondati sul legittimo interesse. Se un trattamento si basa sul
      consenso, puoi revocarlo senza pregiudicare il trattamento precedente.
    </p>
    <p>
      Per chiudere l’account o rimuovere una foto, scrivi a <a
        href={requestLink}>{privacyContact.email}</a
      >, preferibilmente dall’email di registrazione, indicando la richiesta o
      il contenuto. Il semplice logout non cancella l’account. Potremmo chiedere
      una verifica proporzionata per evitare richieste non autorizzate.
    </p>
    <p>
      Rispondiamo di norma entro un mese, con le eventuali proroghe e
      comunicazioni previste dall’articolo 12 GDPR. Puoi presentare un reclamo
      al <a
        href="https://www.garanteprivacy.it/home/diritti/come-agire-per-tutelare-i-tuoi-dati-personali"
        target="_blank"
        rel="noreferrer">Garante per la protezione dei dati personali</a
      > o all’autorità di controllo competente.
    </p>
  </section>

  <section>
    <h2>8. Decisioni automatizzate e aggiornamenti</h2>
    <p>
      Non prendiamo decisioni automatizzate con effetti giuridici sulle persone
      né elaboriamo profili personali. I conteggi degli impianti sono
      elaborazioni delle osservazioni, non valutazioni degli utenti.
    </p>
    <p>
      L’informativa descrive la beta attuale. Nuove finalità, strumenti di
      tracciamento o cambiamenti rilevanti saranno comunicati prima del loro
      utilizzo, raccogliendo il consenso quando necessario.
    </p>
    <p>
      Riferimenti: <a
        href="https://eur-lex.europa.eu/eli/reg/2016/679/2016-05-04?locale=it"
        target="_blank"
        rel="noreferrer">Regolamento UE 2016/679</a
      >
      e
      <a
        href="https://www.garanteprivacy.it/home/docweb/-/docweb-display/docweb/9677876"
        target="_blank"
        rel="noreferrer">linee guida del Garante su cookie e tracciamento</a
      >.
    </p>
  </section>
  <a class="privacy-return" href="/home/">← Torna alla panoramica</a>
</main>

<style>
  .privacy-header {
    max-width: 1120px;
    margin: auto;
    padding: 26px 32px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 20px;
    border-bottom: 1px solid var(--line);
    font-size: 13px;
  }
  .privacy-brand {
    display: flex;
    gap: 10px;
    align-items: center;
    text-decoration: none;
    color: var(--navy);
    font-size: 17px;
  }
  .privacy-page {
    max-width: 1020px;
    padding: 54px 32px 70px;
    color: var(--navy);
  }
  h1 {
    font-size: clamp(34px, 6vw, 52px);
    letter-spacing: -1.8px;
  }
  .privacy-intro {
    font-size: 19px;
    line-height: 1.7;
    max-width: 820px;
  }
  .privacy-updated {
    font-size: 12px;
    color: #64748b;
  }
  .privacy-index {
    display: flex;
    flex-wrap: wrap;
    gap: 12px 24px;
    padding: 23px;
    border: 1px solid var(--line);
    border-radius: 14px;
    background: #fff;
    margin: 28px 0 38px;
    font-size: 14px;
  }
  section {
    margin: 32px 0;
    scroll-margin-top: 24px;
  }
  h2 {
    font-size: 24px;
    letter-spacing: -0.5px;
    margin-bottom: 14px;
  }
  p,
  li {
    font-size: 15px;
    line-height: 1.8;
  }
  li {
    margin-bottom: 12px;
  }
  a {
    text-underline-offset: 3px;
    overflow-wrap: anywhere;
  }
  .privacy-table-wrap {
    overflow-x: auto;
    margin: 24px 0;
    border: 1px solid var(--line);
    border-radius: 12px;
    background: #fff;
  }
  table {
    border-collapse: collapse;
    width: 100%;
    min-width: 650px;
    font-size: 14px;
    line-height: 1.7;
    text-align: left;
  }
  th,
  td {
    vertical-align: top;
    padding: 16px;
    border-bottom: 1px solid var(--line);
  }
  thead {
    background: #edf2f8;
  }
  tbody th {
    width: 19%;
  }
  td:last-child {
    width: 27%;
  }
  .privacy-return {
    display: inline-block;
    margin-top: 20px;
    font-weight: 650;
  }
  @media (max-width: 600px) {
    .privacy-header {
      padding: 20px;
      align-items: flex-start;
      flex-direction: column;
    }
    .privacy-page {
      padding: 34px 20px 50px;
    }
    .privacy-intro {
      font-size: 17px;
    }
    h2 {
      font-size: 22px;
    }
    ul {
      padding-left: 21px;
    }
  }
</style>
