export type Kind = "scala_mobile" | "ascensore";
export type DeviceStatus =
  "funzionante" | "guasta" | "manutenzione" | "non_verificabile";
export type View = "landing" | "home" | "report" | "proposal" | "moderation";
export type Station = { id: string; name: string; area: string };
export type Device = {
  id: string;
  station_id: string;
  kind: Kind;
  name: string;
  location: string;
  synthetic: boolean;
  official_id?: string | null;
  inventory_evidence?: {
    title: string;
    url: string;
    document: string;
    page: number;
    acquired_at: string;
    identification_note: string;
  } | null;
};
export type Member = {
  id: string;
  name: string;
  role: "citizen" | "moderator";
  administrator?: boolean;
};
export type Photo = {
  data: string;
  file?: Blob;
  id?: string;
  version?: number;
  status: "pending" | "approved" | "rejected";
};
export type Report = {
  id: string;
  device_id: string;
  station_id: string;
  status: DeviceStatus;
  description: string;
  observed_at: string;
  recorded_at: string;
  author_id: string;
  author_name: string;
  photo?: Photo;
  seeded?: boolean;
};
export type Proposal = {
  id: string;
  station_id: string;
  kind: Kind;
  name: string;
  location: string;
  description: string;
  actor_id: string;
  created_at: string;
  status: "pending" | "approved" | "rejected";
  photo?: Photo;
  version?: number;
  device_id?: string;
};
export type Data = {
  stationCatalog?: Station[];
  availability?: Availability;
  currentCommunity?: Record<string, Report | undefined>;
  officialEvidence?: Record<string, Evidence | null>;
  statistics?: PrivateStatistics;
  statisticsError?: string;
  photoQueue?: QueuedPhoto[];
  feedCursor?: string | null;
  devices: Device[];
  reports: Report[];
  proposals: Proposal[];
  audit: {
    actor: string;
    target: string;
    decision: string;
    recorded_at: string;
  }[];
  officialExamples: Record<string, DeviceStatus>;
};

export type Availability = {
  total: number;
  working: number;
  percentage: number | null;
  observed_devices: number;
  synthetic: boolean;
  generated_at: string;
};
export type Evidence = {
  status: DeviceStatus;
  observed_at?: string;
  recorded_at?: string;
  published_at?: string;
  acquired_at?: string;
};
export type PrivateStatistics = {
  generated_at: string;
  stale: boolean;
  pending_recalculation: boolean;
  alignment: {
    percentage: number | null;
    aligned: number;
    comparable: number;
    excluded: number;
    items: {
      device_id: string;
      community_status: DeviceStatus;
      observed_at: string;
      official: Evidence;
      aligned: boolean;
    }[];
  };
  incidents: { new_stops: Incident[]; streaks: Incident[] };
};
export type Incident = {
  device_id: string;
  status: DeviceStatus;
  observation_count: number;
  first_observed_at: string;
  latest_observed_at: string;
  first_known: boolean;
};
export type QueuedPhoto = {
  id: string;
  origin: "report" | "proposal";
  photo: Photo;
  name: string;
  station_id: string;
};

export const labels: Record<DeviceStatus, string> = {
  funzionante: "Funzionante",
  guasta: "Fuori servizio",
  manutenzione: "In manutenzione",
  non_verificabile: "Da verificare",
};
export const kindLabels: Record<Kind, string> = {
  scala_mobile: "Scala mobile",
  ascensore: "Ascensore",
};

export function latest(data: Data, id: string): Report | undefined {
  if (data.currentCommunity) return data.currentCommunity[id];
  return data.reports
    .filter((r) => r.device_id === id)
    .sort(
      (a, b) =>
        b.observed_at.localeCompare(a.observed_at) ||
        b.recorded_at.localeCompare(a.recorded_at),
    )[0];
}
export function deviceName(data: Data, id: string) {
  return (
    data.devices.find((d) => d.id === id)?.name || "Impianto non disponibile"
  );
}
export function date(value: string) {
  return new Intl.DateTimeFormat("it-IT", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "Europe/Rome",
  }).format(new Date(value));
}
export function age(value: string) {
  const minutes = Math.max(
    0,
    Math.floor((Date.now() - Date.parse(value)) / 60000),
  );
  return minutes < 1
    ? "Adesso"
    : minutes < 60
      ? `${minutes} min fa`
      : minutes < 1440
        ? `${Math.floor(minutes / 60)} h fa`
        : date(value);
}
