import { PUBLIC_COGNITO_CLIENT_ID, PUBLIC_COGNITO_DOMAIN } from '$env/static/public';
import { apiBase } from './api';

const domain = PUBLIC_COGNITO_DOMAIN.replace(/\/$/, '');
const callback = () => `${window.location.origin}/callback`;
const encode = (value: Uint8Array) => btoa(String.fromCharCode(...value))
  .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');

export async function login(): Promise<void> {
  if (!domain || !PUBLIC_COGNITO_CLIENT_ID || !apiBase) {
    throw new Error('Il login AWS non è ancora configurato in questo ambiente.');
  }
  const verifier = encode(crypto.getRandomValues(new Uint8Array(32)));
  const state = encode(crypto.getRandomValues(new Uint8Array(24)));
  sessionStorage.setItem('smt.oauth', JSON.stringify({ verifier, state }));
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier));
  const params = new URLSearchParams({
    response_type: 'code', client_id: PUBLIC_COGNITO_CLIENT_ID,
    redirect_uri: callback(), scope: 'openid scale-mobili/reports:write scale-mobili/stats:read',
    code_challenge: encode(new Uint8Array(digest)), code_challenge_method: 'S256',
    state, resource: `${apiBase}/mcp`
  });
  window.location.assign(`${domain}/oauth2/authorize?${params}`);
}

type Tokens = { access_token: string; expires_in: number; refresh_token?: string; expires_at?: number };

function saveTokens(tokens: Tokens, previousRefresh?: string): void {
  sessionStorage.setItem('smt.tokens', JSON.stringify({
    access_token: tokens.access_token,
    refresh_token: tokens.refresh_token || previousRefresh,
    expires_at: Date.now() + tokens.expires_in * 1000
  }));
}

export async function finishLogin(): Promise<void> {
  const params = new URLSearchParams(window.location.search);
  const stored = sessionStorage.getItem('smt.oauth');
  sessionStorage.removeItem('smt.oauth');
  if (!stored) throw new Error('Accesso non avviato da questa sessione.');
  const pending = JSON.parse(stored);
  if (!params.get('code') || params.get('state') !== pending.state) {
    throw new Error('Risposta di accesso non valida. Ripeti il login.');
  }
  const response = await fetch(`${domain}/oauth2/token`, {
    method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ grant_type: 'authorization_code',
      client_id: PUBLIC_COGNITO_CLIENT_ID, code: params.get('code')!,
      redirect_uri: callback(), code_verifier: pending.verifier })
  });
  if (!response.ok) throw new Error('Il servizio di autenticazione ha rifiutato il login.');
  saveTokens(await response.json());
  window.history.replaceState({}, '', '/callback');
}

export async function accessToken(): Promise<string | null> {
  const stored = sessionStorage.getItem('smt.tokens');
  if (!stored) return null;
  const tokens: Tokens = JSON.parse(stored);
  if ((tokens.expires_at || 0) > Date.now() + 30000) return tokens.access_token;
  if (!tokens.refresh_token) { logout(); return null; }
  const response = await fetch(`${domain}/oauth2/token`, {
    method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ grant_type: 'refresh_token', client_id: PUBLIC_COGNITO_CLIENT_ID,
      refresh_token: tokens.refresh_token })
  });
  if (!response.ok) { logout(); return null; }
  const fresh: Tokens = await response.json();
  saveTokens(fresh, tokens.refresh_token);
  return fresh.access_token;
}

export function logout(): void {
  sessionStorage.removeItem('smt.tokens');
  sessionStorage.removeItem('smt.oauth');
}
