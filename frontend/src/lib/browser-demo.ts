// Anteprima privata senza backend: tutto avviene nella sessione del browser.
// Questo adattatore è escluso dal percorso di rete quando PUBLIC_BROWSER_DEMO=false.
type DemoEvent = {
  event_id: string; escalator_id: string; kind: string; actor: string;
  status?: string; observed_at: string; recorded_at: string; reference: string;
  target_event_id?: string; synthetic: true;
};
type Receipt = { body: string; expires: number; result: DemoEvent };
type State = { events: DemoEvent[]; receipts: Record<string, Receipt>; cursorSecret: string };
const storageKey = 'smt.browser-demo.v1';
const statuses = new Set(['funzionante', 'guasta', 'manutenzione', 'non_verificabile']);
const ids = new Set(['demo-esc-1', 'demo-esc-2']);

function state(): State {
  const stored = sessionStorage.getItem(storageKey);
  return stored ? JSON.parse(stored) : { events: [], receipts: {}, cursorSecret: crypto.randomUUID() };
}

function requireCondition(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

function publicEvent(event: DemoEvent) {
  const { actor: _actor, ...result } = event;
  return result;
}

function community(events: DemoEvent[]) {
  const reports = new Map(events.filter(e => e.kind === 'report').map(e => [e.event_id, { ...e }]));
  for (const e of events) {
    if (e.kind === 'correction' && e.target_event_id && reports.has(e.target_event_id)) {
      const original = reports.get(e.target_event_id)!;
      reports.set(e.target_event_id, { ...original, status: e.status });
    }
  }
  const latest = [...reports.values()].sort((a,b) =>
    a.observed_at.localeCompare(b.observed_at) || a.recorded_at.localeCompare(b.recorded_at)).at(-1);
  return latest ? {
    status: latest.status, observed_at: latest.observed_at, recorded_at: latest.recorded_at,
    corrected_at: events.filter(e => e.kind === 'correction' && e.target_event_id === latest.event_id).at(-1)?.recorded_at || null,
    event_id: latest.event_id, source: 'community', report_count: reports.size,
    account_count: new Set([...reports.values()].map(e => e.actor)).size
  } : null;
}

export async function demoRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = new URL(path, 'https://synthetic.invalid');
  const method = options.method || 'GET';
  const data = state();
  let result: unknown;
  if (url.pathname === '/health' && method === 'GET') {
    result = { mode: 'demo', status: 'ok', storage: 'browser_session', synthetic_demo: true };
  } else if (url.pathname === '/api/stations' && method === 'GET') {
    result = { items: [{ station_id: 'demo-station', name: 'Stazione fittizia', synthetic: true }] };
  } else if (url.pathname === '/api/stations/demo-station/escalators' && method === 'GET') {
    result = { items: [1,2].map(n => ({ escalator_id: `demo-esc-${n}`, station_id: 'demo-station',
      name: `Scala mobile fittizia ${n}`, synthetic: true, operator: null, official_id: null })) };
  } else {
    const match = url.pathname.match(/^\/api\/escalators\/([^/]+)\/(status|history|reports|corrections|confirmations)$/);
    requireCondition(match && ids.has(match[1]), 'Impianto di prova non trovato.');
    const [, id, action] = match;
    const events = data.events.filter(e => e.escalator_id === id);
    if (action === 'status' && method === 'GET') {
      const evidence = community(events);
      result = { escalator_id: id, synthetic: true, official: null, community: evidence,
        estimate: null, generated_at: new Date().toISOString(),
        missing_reason: evidence ? null : 'Nessuna informazione disponibile' };
    } else if (action === 'history' && method === 'GET') {
      const limit = Number(url.searchParams.get('limit') || 20);
      requireCondition(Number.isInteger(limit) && limit >= 1 && limit <= 100, 'Limite non valido.');
      const token = url.searchParams.get('cursor');
      let upper = new Date().toISOString(), offset = 0;
      if (token) {
        let cursor;
        try { cursor = JSON.parse(atob(token)); } catch { throw new Error('Cursore non valido.'); }
        requireCondition(cursor.id === id && cursor.secret === data.cursorSecret, 'Cursore non valido.');
        upper = cursor.upper; offset = cursor.offset;
      }
      const eligible = events.filter(e => e.recorded_at <= upper);
      const page = eligible.slice(offset, offset+limit);
      result = { items: page.map(publicEvent), upper_bound: upper, snapshot: false,
        order: 'recorded_at_ascending', next_cursor: offset+limit < eligible.length ? btoa(JSON.stringify({
          id, upper, offset: offset+limit, secret: data.cursorSecret
        })) : null };
    } else {
      requireCondition(method === 'POST' && ['reports','corrections','confirmations'].includes(action), 'Operazione non disponibile.');
      const headers = new Headers(options.headers);
      const actor = (headers.get('Authorization') || '').replace(/^Bearer /, '');
      requireCondition(['demo-user-1','demo-user-2','demo-moderator'].includes(actor), 'Seleziona un utente di prova.');
      const key = headers.get('Idempotency-Key') || '';
      requireCondition(key.length >= 8 && key.length <= 128, 'Chiave di invio non valida.');
      const body = options.body ? JSON.parse(String(options.body)) : {};
      const fingerprint = JSON.stringify({ path, body });
      const receipt = data.receipts[`${actor}:${key}`];
      if (receipt && receipt.expires > Date.now()) {
        requireCondition(receipt.body === fingerprint, 'Chiave di invio già usata con contenuto diverso.');
        return structuredClone(publicEvent(receipt.result)) as T;
      }
      requireCondition(data.events.length < 1000, 'Limite della demo raggiunto. Apri una nuova sessione.');
      const kind = action === 'reports' ? 'report' : action === 'corrections' ? 'correction' : 'confirmation';
      const target = events.find(e => e.reference === url.searchParams.get('reference') && e.kind === 'report');
      if (kind !== 'report') requireCondition(target, 'Segnalazione originale non trovata.');
      if (kind === 'correction') {
        requireCondition(target?.actor === actor || actor === 'demo-moderator', 'Puoi rettificare solo le tue segnalazioni.');
        requireCondition(typeof body.reason === 'string' && body.reason.length >= 3 && body.reason.length <= 500, 'Motivazione da 3 a 500 caratteri richiesta.');
      }
      if (kind !== 'confirmation') requireCondition(statuses.has(body.status), 'Stato non valido.');
      const now = new Date().toISOString();
      const observed = kind === 'report' ? body.observed_at || now : target!.observed_at;
      requireCondition(Number.isFinite(Date.parse(observed)) && Date.parse(observed) <= Date.now()+120000,
        'Il momento osservato non è valido o è futuro.');
      const event: DemoEvent = { event_id: crypto.randomUUID(), escalator_id: id, kind, actor,
        recorded_at: now, observed_at: new Date(observed).toISOString(),
        reference: crypto.randomUUID(), synthetic: true,
        ...(kind !== 'confirmation' ? { status: body.status } : {}),
        ...(target ? { target_event_id: target.event_id } : {}) };
      data.events.push(event);
      data.receipts[`${actor}:${key}`] = { body: fingerprint, expires: Date.now()+86400000, result: event };
      result = publicEvent(event);
    }
  }
  sessionStorage.setItem(storageKey, JSON.stringify(data));
  return structuredClone(result) as T;
}
