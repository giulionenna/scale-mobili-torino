import {
  PUBLIC_COGNITO_CLIENT_ID,
  PUBLIC_COGNITO_DOMAIN,
} from "$env/static/public";
import { apiBase, request } from "./api";

export type AuthConfig = {
  mode: "demo" | "local" | "aws";
  cognito_domain: string;
  cognito_client_id: string;
  resource: string;
  scopes?: string[];
};
let config: AuthConfig | undefined;
export function configureAuth(value: AuthConfig) {
  config = value;
}
async function settings() {
  config ??= await request<AuthConfig>("/api/config");
  const resource = config.resource || `${apiBase}/mcp`;
  return {
    domain: (PUBLIC_COGNITO_DOMAIN || config.cognito_domain).replace(/\/$/, ""),
    client: PUBLIC_COGNITO_CLIENT_ID || config.cognito_client_id,
    resource,
    scopes: config.scopes || [
      "openid",
      `${resource}/reports:write`,
      `${resource}/stats:read`,
    ],
  };
}
const callback = () => `${window.location.origin}/auth/cognito`;
const encode = (value: Uint8Array) =>
  btoa(String.fromCharCode(...value))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
const destinations = new Set([
  "/home/",
  "/segnala/",
  "/proponi/",
  "/moderazione/",
]);
export function returnDestination() {
  const value = sessionStorage.getItem("smt.returnTo");
  sessionStorage.removeItem("smt.returnTo");
  return value && destinations.has(value) ? value : "/home/";
}

export async function login(destination = "/home/"): Promise<void> {
  const { domain, client, resource, scopes } = await settings();
  if (!domain || !client)
    throw new Error("Il login non è ancora configurato in questo ambiente.");
  const verifier = encode(crypto.getRandomValues(new Uint8Array(32)));
  const state = encode(crypto.getRandomValues(new Uint8Array(24)));
  sessionStorage.setItem("smt.oauth", JSON.stringify({ verifier, state }));
  sessionStorage.setItem(
    "smt.returnTo",
    destinations.has(destination) ? destination : "/home/",
  );
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(verifier),
  );
  const params = new URLSearchParams({
    response_type: "code",
    client_id: client,
    redirect_uri: callback(),
    scope: scopes.join(" "),
    code_challenge: encode(new Uint8Array(digest)),
    code_challenge_method: "S256",
    state,
    resource,
  });
  window.location.assign(`${domain}/oauth2/authorize?${params}`);
}

type Tokens = {
  access_token: string;
  expires_in: number;
  refresh_token?: string;
  expires_at?: number;
};
function saveTokens(tokens: Tokens, previousRefresh?: string): void {
  sessionStorage.setItem(
    "smt.tokens",
    JSON.stringify({
      access_token: tokens.access_token,
      refresh_token: tokens.refresh_token || previousRefresh,
      expires_at: Date.now() + tokens.expires_in * 1000,
    }),
  );
}
export async function finishLogin(): Promise<void> {
  const { domain, client } = await settings();
  const params = new URLSearchParams(window.location.search);
  const stored = sessionStorage.getItem("smt.oauth");
  sessionStorage.removeItem("smt.oauth");
  // Remove the authorization code from browser history even on a failed callback.
  window.history.replaceState({}, "", "/auth/cognito");
  if (!stored) throw new Error("Accesso non avviato da questa sessione.");
  const pending = JSON.parse(stored);
  if (!params.get("code") || params.get("state") !== pending.state) {
    throw new Error("Risposta di accesso non valida. Ripeti il login.");
  }
  const response = await fetch(`${domain}/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      client_id: client,
      code: params.get("code")!,
      redirect_uri: callback(),
      code_verifier: pending.verifier,
    }),
  });
  if (!response.ok)
    throw new Error("Il servizio di autenticazione ha rifiutato il login.");
  saveTokens(await response.json());
  sessionStorage.removeItem("smt.favorites-checked");
}
let refreshing: Promise<string | null> | null = null;
export async function accessToken(): Promise<string | null> {
  const stored = sessionStorage.getItem("smt.tokens");
  if (!stored) return null;
  let tokens: Tokens;
  try {
    tokens = JSON.parse(stored);
  } catch {
    logout();
    return null;
  }
  if ((tokens.expires_at || 0) > Date.now() + 30000) return tokens.access_token;
  if (!tokens.refresh_token) {
    logout();
    return null;
  }
  if (!refreshing)
    refreshing = refresh(tokens).finally(() => {
      refreshing = null;
    });
  return refreshing;
}
async function refresh(tokens: Tokens) {
  const original = sessionStorage.getItem("smt.tokens");
  const { domain, client } = await settings();
  const response = await fetch(`${domain}/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "refresh_token",
      client_id: client,
      refresh_token: tokens.refresh_token!,
    }),
  });
  if (!response.ok) {
    logout();
    return null;
  }
  const fresh: Tokens = await response.json();
  if (sessionStorage.getItem("smt.tokens") !== original) return null;
  saveTokens(fresh, tokens.refresh_token);
  return fresh.access_token;
}
export function logout(): void {
  sessionStorage.removeItem("smt.tokens");
  sessionStorage.removeItem("smt.oauth");
  sessionStorage.removeItem("smt.returnTo");
}
