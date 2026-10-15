import { PUBLIC_API_URL, PUBLIC_BROWSER_DEMO } from "$env/static/public";
import { demoRequest } from "./browser-demo";

export const apiBase = (PUBLIC_API_URL || "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  if (PUBLIC_BROWSER_DEMO === "true") return demoRequest<T>(path, options);
  const response = await fetch(`${apiBase}${path}`, options);
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const detail = Array.isArray(data.detail)
      ? data.detail.map((item: { msg: string }) => item.msg).join(". ")
      : data.detail;
    throw new ApiError(
      detail || `Richiesta non riuscita (${response.status})`,
      response.status,
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export type Station = { station_id: string; name: string; synthetic: boolean };
export type Escalator = {
  escalator_id: string;
  name: string;
  station_id: string;
  synthetic: boolean;
  operator: string | null;
  official_id: string | null;
};
export type Evidence = {
  status: string;
  observed_at: string;
  recorded_at: string;
  corrected_at: string | null;
  report_count: number;
  account_count: number;
};
export type EscalatorStatus = {
  escalator_id: string;
  community: Evidence | null;
  official: Evidence | null;
  estimate: Evidence | null;
  generated_at: string;
  missing_reason: string | null;
};
export type Event = {
  event_id: string;
  kind: string;
  status?: string;
  observed_at: string;
  recorded_at: string;
  reference: string;
  target_event_id?: string;
};
export type History = {
  items: Event[];
  next_cursor: string | null;
  upper_bound: string;
};

export const labels: Record<string, string> = {
  funzionante: "Funzionante",
  guasta: "Guasta",
  manutenzione: "In manutenzione",
  non_verificabile: "Non verificabile",
};

export function date(value: string | undefined | null): string {
  return value
    ? new Intl.DateTimeFormat("it-IT", {
        timeZone: "Europe/Rome",
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(value))
    : "Non disponibile";
}
