<script lang="ts">
  import { onMount } from 'svelte';
  import { request, labels, date } from './api';
  import type { Station, Escalator, EscalatorStatus, History, Event } from './api';
  import { login, logout, accessToken } from './auth';
  import Arrow from './Arrow.svelte';

  let stations = $state<Station[]>([]);
  let escalators = $state<Escalator[]>([]);
  let selected = $state<Escalator | null>(null);
  let station = $state('');
  let current = $state<EscalatorStatus | null>(null);
  let events = $state<Event[]>([]);
  let cursor = $state<string | null>(null);
  let demo = $state(false);
  let ready = $state(false);
  let busy = $state(false);
  let loadingDetails = $state(false);
  let error = $state('');
  let success = $state('');
  let identity = $state('');
  let signedIn = $state(false);
  let reportedStatus = $state('guasta');
  let correctedStatus = $state('funzionante');
  let correction = $state<Event | null>(null);
  let correctionReason = $state('');
  let observedLocal = $state('');
  let pendingKey: string | null = null;
  let pendingBody = '';
  let pendingPath = '';
  let detailsVersion = 0;

  onMount(() => {
    initialise().catch(showError);
  });

  function showError(value: unknown): void {
    error = value instanceof Error ? value.message : 'Operazione non riuscita. Riprova.';
  }

  async function initialise() {
    const health = await request<{ mode: string }>('/health');
    demo = health.mode === 'demo';
    signedIn = !demo && Boolean(await accessToken());
    stations = (await request<{ items: Station[] }>('/api/stations')).items;
    if (stations[0]) { station = stations[0].station_id; await loadStation(); }
    ready = true;
  }

  async function loadStation() {
    error = '';
    escalators = (await request<{ items: Escalator[] }>(
      `/api/stations/${encodeURIComponent(station)}/escalators`)).items;
    const requested = new URLSearchParams(window.location.search).get('id');
    const initial = escalators.find(e => e.escalator_id === requested) || escalators[0];
    if (initial) await select(initial);
    else { selected = null; current = null; events = []; }
  }

  async function select(escalator: Escalator) {
    const version = ++detailsVersion;
    selected = escalator; current = null; events = []; cursor = null;
    correction = null; success = ''; error = ''; loadingDetails = true;
    try {
      const [state, history] = await Promise.all([
        request<EscalatorStatus>(`/api/escalators/${escalator.escalator_id}/status`),
        request<History>(`/api/escalators/${escalator.escalator_id}/history`)
      ]);
      if (version === detailsVersion) {
        current = state; events = history.items; cursor = history.next_cursor;
      }
    } catch (e) { if (version === detailsVersion) showError(e); }
    finally { if (version === detailsVersion) loadingDetails = false; }
  }

  async function moreHistory() {
    if (!cursor || !selected) return;
    busy = true;
    const id = selected.escalator_id;
    try {
      const history = await request<History>(`/api/escalators/${id}/history?cursor=${encodeURIComponent(cursor)}`);
      if (selected.escalator_id === id) { events = [...events, ...history.items]; cursor = history.next_cursor; }
    } catch (e) { showError(e); } finally { busy = false; }
  }

  async function write(path: string, body: object | null): Promise<boolean> {
    const token = demo ? identity : await accessToken();
    if (!token) { error = 'Accedi prima di inviare una segnalazione.'; return false; }
    const encoded = body ? JSON.stringify(body) : '';
    if (!pendingKey || encoded !== pendingBody || path !== pendingPath) {
      pendingKey = crypto.randomUUID(); pendingBody = encoded; pendingPath = path;
    }
    await request(path, { method: 'POST', headers: {
      Authorization: `Bearer ${token}`, 'Idempotency-Key': pendingKey,
      ...(body ? { 'Content-Type': 'application/json' } : {})
    }, ...(body ? { body: encoded } : {}) });
    pendingKey = null;
    return true;
  }

  async function submitReport() {
    if (!selected) return;
    busy = true; error = ''; success = '';
    const chosen = selected;
    try {
      const body = { status: reportedStatus, ...(observedLocal ? {
        observed_at: new Date(observedLocal).toISOString()
      } : {}) };
      if (await write(`/api/escalators/${chosen.escalator_id}/reports`, body)) {
        await select(chosen); success = 'Segnalazione registrata.';
      }
    } catch (e) { showError(e); } finally { busy = false; }
  }

  async function confirm(event: Event) {
    if (!selected) return;
    busy = true; error = '';
    const chosen = selected;
    try {
      if (await write(`/api/escalators/${chosen.escalator_id}/confirmations?reference=${encodeURIComponent(event.reference)}`, null)) {
        await select(chosen); success = 'Conferma registrata nello storico.';
      }
    } catch (e) { showError(e); } finally { busy = false; }
  }

  async function submitCorrection() {
    if (!selected || !correction) return;
    busy = true; error = '';
    const chosen = selected;
    try {
      if (await write(`/api/escalators/${chosen.escalator_id}/corrections?reference=${encodeURIComponent(correction.reference)}`,
          { status: correctedStatus, reason: correctionReason })) {
        await select(chosen); correction = null; correctionReason = ''; success = 'Rettifica registrata. L’originale è conservato.';
      }
    } catch (e) { showError(e); } finally { busy = false; }
  }

  async function signIn() { try { await login(); } catch (e) { showError(e); } }
</script>

<svelte:head>
  <title>Scale Mobili Torino · Prototipo</title>
  <meta name="description" content="Prova della piattaforma civica: stato, fonti e osservazioni delle scale mobili." />
  <meta name="robots" content="noindex, nofollow" />
</svelte:head>

<header class="site-header">
  <a class="brand" href="/"><span class="brand-mark" aria-hidden="true"><Arrow /></span><span>Scale Mobili <strong>Torino</strong></span></a>
  <span class="project-label">PROTOTIPO CIVICO</span>
</header>

<main>
  <section class="hero">
    <p class="eyebrow">UNA CITTÀ PIÙ ACCESSIBILE, INSIEME</p>
    <h1>Ogni percorso<br />conta.</h1>
    <p class="intro">Consulta le osservazioni sulle scale mobili e contribuisci con quello che vedi. Fonti e tempi accompagnano ogni informazione.</p>
  </section>

  {#if demo}
    <aside class="demo-banner"><strong>Ambiente di prova</strong><span>Stazione e impianti fittizi. Accesso simulato e segnalazioni temporanee; nessun dato reale.</span></aside>
  {/if}

  {#if error}<div class="notice error" role="alert">{error}</div>{/if}
  {#if success}<div class="notice success" role="status">{success}</div>{/if}

  {#if !ready && !error}<p class="loading" role="status">Caricamento degli impianti…</p>{/if}
  {#if !ready && error}<button onclick={() => initialise().catch(showError)}>Riprova il caricamento</button>{/if}

  {#if ready}
    <div class="workspace">
      <section class="station-panel" aria-label="Scegli un impianto">
        <p class="eyebrow">ESPLORA GLI IMPIANTI</p>
        <label for="station">Stazione</label>
        <select id="station" bind:value={station} onchange={() => loadStation().catch(showError)} disabled={busy}>
          {#each stations as item}<option value={item.station_id}>{item.name}</option>{/each}
        </select>
        <div class="escalator-list">
          {#each escalators as item}
            <button class:chosen={selected?.escalator_id === item.escalator_id} class="escalator-button"
              onclick={() => select(item)} disabled={busy} aria-pressed={selected?.escalator_id === item.escalator_id}>
              <span class="escalator-icon" aria-hidden="true"><Arrow /></span>
              <span><strong>{item.name}</strong><small>{item.synthetic ? 'Impianto di prova' : 'Impianto censito'}</small></span>
              <span aria-hidden="true">→</span>
            </button>
          {/each}
        </div>
        {#if !escalators.length}<p>Nessun impianto confermato disponibile.</p>{/if}
        <div class="source-note"><strong>Leggere i dati con cura</strong><p>Una fonte che non menziona un impianto non dimostra che funzioni. L’assenza di informazioni è sempre indicata.</p></div>
      </section>

      {#if selected}
        <section class="detail-panel" aria-label="Dettaglio impianto">
          <div class="detail-heading"><div><p class="eyebrow">SCHEDA IMPIANTO</p><h2>{selected.name}</h2></div><span class="pill">{selected.synthetic ? 'DATO FITTIZIO' : 'CENSITO'}</span></div>
          <div class="meta-row"><span>Gestore: {selected.operator || 'non verificato'}</span><span>ID ufficiale: {selected.official_id || 'non disponibile'}</span></div>

          {#if loadingDetails}<p role="status">Caricamento della scheda…</p>{/if}
          {#if current}
            <div class="evidence-grid">
              <article class="evidence-card community"><p class="eyebrow">COMMUNITY</p>
                <h3>{current.community ? labels[current.community.status] : 'Nessuna informazione'}</h3>
                {#if current.community}<p>Osservata il {date(current.community.observed_at)}</p><small>{current.community.report_count} {current.community.report_count === 1 ? 'segnalazione' : 'segnalazioni'} · {current.community.account_count} {current.community.account_count === 1 ? 'account distinto' : 'account distinti'}</small>{:else}<p>Non sono disponibili osservazioni.</p>{/if}
              </article>
              <article class="evidence-card"><p class="eyebrow">FONTE UFFICIALE</p><h3>{current.official ? labels[current.official.status] : 'Nessuna informazione'}</h3><p>Nessuna interpretazione verificata presente.</p></article>
              <article class="evidence-card"><p class="eyebrow">STIMA</p><h3>Non disponibile</h3><p>Copertura insufficiente per una stima.</p></article>
            </div>
            <p class="freshness">Scheda aggiornata il {date(current.generated_at)} · Orari Europe/Rome</p>
          {/if}

          <section class="report-box">
            <div><p class="eyebrow">IL TUO CONTRIBUTO</p><h3>Cosa hai osservato?</h3></div>
            {#if demo}
              <label for="identity">Simula accesso di prova</label>
              <select id="identity" bind:value={identity} disabled={busy}>
                <option value="">Scegli un utente</option><option value="demo-user-1">Utente di prova 1</option><option value="demo-user-2">Utente di prova 2</option><option value="demo-moderator">Moderatore di prova</option>
              </select>
            {:else if !signedIn}
              <p>Accedi per aggiungere un’osservazione.</p><button class="primary" onclick={signIn}>Accedi</button>
            {:else}<p>Accesso effettuato. <button class="text-button" onclick={() => { logout(); signedIn = false; }}>Esci</button></p>{/if}
            {#if (demo && identity) || signedIn}
              <form onsubmit={(e) => { e.preventDefault(); submitReport(); }}>
                <div class="form-row"><div><label for="status">Stato osservato</label><select id="status" bind:value={reportedStatus} disabled={busy}>{#each Object.entries(labels) as [value, label]}<option {value}>{label}</option>{/each}</select></div>
                <div><label for="observed">Momento osservato (facoltativo)</label><input id="observed" type="datetime-local" bind:value={observedLocal} disabled={busy} /><small>Ora locale del tuo dispositivo; se vuoto, adesso.</small></div></div>
                <button class="primary" type="submit" disabled={busy}>{busy ? 'Invio in corso…' : 'Invia segnalazione'}<span aria-hidden="true"><Arrow /></span></button>
              </form>
            {/if}
          </section>

          <section class="history-section"><div class="section-heading"><h3>Storico delle osservazioni</h3><small>Ordine di registrazione</small></div>
            {#if !events.length}<p class="empty">Lo storico è vuoto. La prima osservazione comparirà qui.</p>{/if}
            {#each events as event (event.event_id)}
              <article class="event"><span class="event-dot" aria-hidden="true"></span><div><strong>{event.kind === 'report' ? 'Segnalazione' : event.kind === 'correction' ? 'Rettifica' : 'Conferma'}{event.status ? ` · ${labels[event.status]}` : ''}</strong><p>Osservazione: {date(event.observed_at)}</p><small>Registrazione: {date(event.recorded_at)}</small>
              {#if event.kind === 'report' && ((demo && identity) || signedIn)}<div class="event-actions"><button class="text-button" onclick={() => confirm(event)} disabled={busy}>Conferma</button><button class="text-button" onclick={() => { correction = event; correctionReason = ''; }} disabled={busy}>Rettifica</button></div>{/if}</div></article>
            {/each}
            {#if cursor}<button onclick={moreHistory} disabled={busy}>Carica altre osservazioni</button>{/if}
          </section>

          {#if correction}<form class="correction-box" onsubmit={(e) => { e.preventDefault(); submitCorrection(); }}><h3>Rettifica una segnalazione</h3><p>Il server verifica che tu sia l’autore o un moderatore. L’originale rimane nello storico.</p><label for="corrected-status">Stato corretto</label><select id="corrected-status" bind:value={correctedStatus}>{#each Object.entries(labels) as [value,label]}<option {value}>{label}</option>{/each}</select><label for="reason">Motivazione privata</label><textarea id="reason" bind:value={correctionReason} minlength="3" maxlength="500" required></textarea><div class="event-actions"><button class="primary" disabled={busy}>Salva rettifica</button><button type="button" onclick={() => correction = null}>Annulla</button></div></form>{/if}
        </section>
      {/if}
    </div>
  {/if}
</main>

<footer><span>Scale Mobili Torino · Piattaforma civica indipendente</span><span>Prototipo in sviluppo · Nessun censimento reale</span></footer>
