import { PUBLIC_BROWSER_DEMO, PUBLIC_DEV_LOGIN } from "$env/static/public";
import { ApiError, apiBase, request } from "./api";
import { accessToken, configureAuth, login, logout } from "./auth";
import type { AuthConfig } from "./auth";
import type {
  Availability,
  Data,
  Device,
  Evidence,
  Member,
  Photo,
  PrivateStatistics,
  Proposal,
  QueuedPhoto,
  Report,
  Station,
} from "./platform-model";

export const browserDemo = PUBLIC_BROWSER_DEMO === "true";
let config: AuthConfig | undefined;
let activeMember: Member | null = null;
const devTokenKey = "smt.development-token";
export function developmentLogin() {
  return (
    browserDemo ||
    (PUBLIC_DEV_LOGIN === "true" && !!config && config.mode !== "aws")
  );
}
export function backendMode() {
  return browserDemo ? "browser" : config?.mode;
}
async function initialize() {
  if (browserDemo || config) return;
  config = await request<AuthConfig>("/api/config");
  configureAuth(config);
}
async function token() {
  await initialize();
  return developmentLogin()
    ? sessionStorage.getItem(devTokenKey)
    : accessToken();
}
export async function authorized<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const value = await token();
  if (!value) throw new ApiError("Accedi prima di contribuire.", 401);
  const headers = new Headers(options.headers);
  headers.set("Authorization", `Bearer ${value}`);
  try {
    return await request<T>(path, { ...options, headers });
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) signOut();
    throw error;
  }
}
export async function member(): Promise<Member | null> {
  if (browserDemo) return (await import("./platform-demo")).member();
  if (!(await token())) return (activeMember = null);
  try {
    const result = await authorized<{ id: string; moderator: boolean }>(
      "/api/me",
    );
    return (activeMember = {
      id: result.id,
      name: result.moderator ? "Moderatore" : "Cittadino",
      role: result.moderator ? "moderator" : "citizen",
    });
  } catch (error) {
    if (error instanceof ApiError && error.status === 401)
      return (activeMember = null);
    throw error;
  }
}
export async function signIn(
  role: "citizen" | "moderator",
  destination: string,
): Promise<Member | null> {
  if (browserDemo) {
    sessionStorage.removeItem("smt.favorites-checked");
    return (await import("./platform-demo")).signIn(role);
  }
  await initialize();
  if (!developmentLogin()) {
    await login(destination);
    return null;
  }
  sessionStorage.removeItem("smt.favorites-checked");
  sessionStorage.setItem(
    devTokenKey,
    role === "moderator" ? "demo-moderator" : "demo-user-1",
  );
  return member();
}
export function signOut() {
  activeMember = null;
  sessionStorage.removeItem("smt.favorites-checked");
  sessionStorage.removeItem(devTokenKey);
  sessionStorage.removeItem("smt.platform-member.v2");
  logout();
}
export function stationName(data: Data | null, id: string) {
  return (
    data?.stationCatalog?.find((station) => station.id === id)?.name ||
    "Stazione non disponibile"
  );
}
export const gttSource =
  "https://www.gtt.to.it/cms/en/19-linee-e-orari/urbana/12186-metropolitana-aggiornamento-ascensori-e-scale-mobili";
const part = encodeURIComponent;
export const resourceUrl = (path: string) => `${apiBase}${path}`;
type Page<T> = { items: T[]; next_cursor: string | null };
type BackendProposal = Omit<Proposal, "id" | "actor_id"> & {
  proposal_id: string;
  photo_id?: string;
  version: number;
};
type BackendPhoto = {
  photo_id: string;
  device_id: string | null;
  proposal_id: string | null;
  version: number;
  status: Photo["status"];
};
type BackendReport = Omit<Report, "id" | "author_id" | "author_name"> & {
  event_id: string;
  photo_url?: string;
};
export type OverviewResponse = {
  stations: { station_id: string; name: string; synthetic: boolean }[];
  devices: (Omit<Device, "id"> & { device_id: string })[];
  states: Record<
    string,
    { community: Evidence | null; official: Evidence | null }
  >;
  availability: Availability;
};
async function pages<T>(path: string): Promise<T[]> {
  const items: T[] = [];
  let cursor: string | null = null;
  do {
    const query: string = cursor ? `&cursor=${part(cursor)}` : "";
    const page: Page<T> = await authorized<Page<T>>(
      `${path}?limit=100${query}`,
    );
    items.push(...page.items);
    if (items.length > 2000)
      throw new Error("Elenco oltre il limite del prototipo.");
    cursor = page.next_cursor;
  } while (cursor);
  return items;
}
function proposal(item: BackendProposal, actorId: string): Proposal {
  return {
    ...item,
    id: item.proposal_id,
    actor_id: actorId,
    photo: item.photo_id
      ? { id: item.photo_id, data: "", status: "pending" }
      : undefined,
  };
}
function report(item: BackendReport): Report {
  return {
    ...item,
    id: item.event_id,
    author_id: "",
    author_name: "Community",
    photo: item.photo_url
      ? { data: resourceUrl(item.photo_url), status: "approved" }
      : undefined,
  };
}
export async function load(): Promise<Data> {
  if (browserDemo) {
    const demo = await import("./platform-demo");
    return { ...demo.load(), stationCatalog: demo.stations };
  }
  await initialize();
  const [overview, feed] = await Promise.all([
    request<OverviewResponse>("/api/overview"),
    request<Page<BackendReport>>("/api/feed?limit=20"),
  ]);
  const devices = overview.devices.map((device) => ({
    ...device,
    id: device.device_id,
  }));
  const stationCatalog: Station[] = overview.stations.map((station) => ({
    id: station.station_id,
    name: station.name,
    area: "Metro M1",
  }));
  const currentCommunity: Data["currentCommunity"] = {};
  const officialEvidence: Data["officialEvidence"] = {};
  for (const device of devices) {
    const state = overview.states[device.id];
    if (state?.community)
      currentCommunity[device.id] = {
        id: `current-${device.id}`,
        device_id: device.id,
        station_id: device.station_id,
        status: state.community.status,
        description: "",
        observed_at: state.community.observed_at!,
        recorded_at: state.community.recorded_at!,
        author_id: "",
        author_name: "Community",
      };
    officialEvidence[device.id] = state?.official || null;
  }
  const data: Data = {
    devices,
    stationCatalog,
    availability: overview.availability,
    currentCommunity,
    officialEvidence,
    reports: feed.items.map(report),
    feedCursor: feed.next_cursor,
    proposals: [],
    audit: [],
    officialExamples: {},
    photoQueue: [],
  };
  if (!activeMember) return data;
  // Availability and station cards stay usable when a derived snapshot is pending.
  try {
    data.statistics = await authorized<PrivateStatistics>("/api/stats/private");
    data.officialExamples = Object.fromEntries(
      data.statistics.alignment.items.map((item) => [
        item.device_id,
        item.official.status,
      ]),
    );
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) throw error;
    data.statisticsError =
      error instanceof Error ? error.message : "Statistiche non disponibili.";
  }
  const own = await pages<BackendProposal>("/api/me/proposals");
  data.proposals = own.map((item) => proposal(item, activeMember!.id));
  if (activeMember.role === "moderator") {
    const [pending, photos] = await Promise.all([
      pages<BackendProposal>("/api/moderation/proposal/queue"),
      pages<BackendPhoto>("/api/moderation/photo/queue"),
    ]);
    for (const item of pending)
      if (!data.proposals.some((p) => p.id === item.proposal_id))
        data.proposals.push(proposal(item, ""));
    data.photoQueue = photos.map((item) => {
      const device = devices.find((d) => d.id === item.device_id);
      return {
        id: item.photo_id,
        origin: item.proposal_id ? "proposal" : "report",
        name: device?.name || "Impianto",
        station_id: device?.station_id || "",
        photo: {
          id: item.photo_id,
          version: item.version,
          data: "",
          status: item.status,
        },
      } satisfies QueuedPhoto;
    });
  }
  return data;
}
export async function moreReports(data: Data): Promise<Data> {
  if (!data.feedCursor) return data;
  const page = await request<Page<BackendReport>>(
    `/api/feed?limit=20&cursor=${part(data.feedCursor)}`,
  );
  const existing = new Set(data.reports.map((r) => r.id));
  return {
    ...data,
    reports: [
      ...data.reports,
      ...page.items.filter((r) => !existing.has(r.event_id)).map(report),
    ],
    feedCursor: page.next_cursor,
  };
}
async function write<T>(path: string, body: unknown, key: string): Promise<T> {
  return authorized<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": key },
    body: JSON.stringify(body),
  });
}
type Reservation = {
  photo_id: string;
  upload: {
    url: string;
    fields: Record<string, string>;
    method: "POST" | "PUT";
  };
};
const uploads = new WeakMap<
  Photo,
  {
    parent: string;
    reservation: Reservation;
    uploaded: boolean;
    completed: boolean;
  }
>();
async function uploadPhoto(
  photo: Photo,
  parent: { device_id: string } | { proposal_id: string },
  key: string,
) {
  const identity = JSON.stringify(parent);
  let progress = uploads.get(photo);
  if (!progress || progress.parent !== identity) {
    if (!photo.file) throw new Error("Seleziona nuovamente la fotografia.");
    const reservation = await write<Reservation>(
      "/api/photos/uploads",
      { ...parent, content_type: photo.file.type, size_bytes: photo.file.size },
      `${key}:reserve`,
    );
    progress = {
      parent: identity,
      reservation,
      uploaded: false,
      completed: false,
    };
    uploads.set(photo, progress);
  }
  const { reservation } = progress;
  if (!progress.uploaded) {
    if (reservation.upload.method === "POST") {
      const form = new FormData();
      for (const [name, value] of Object.entries(reservation.upload.fields))
        form.append(name, value);
      form.append("file", photo.file!, "photo.jpg");
      // S3 receives only its signed form, never the API's bearer token.
      const response = await fetch(reservation.upload.url, {
        method: "POST",
        body: form,
      });
      if (!response.ok)
        throw new Error(
          "Caricamento della foto non riuscito. Ritenta l’invio.",
        );
    } else
      await authorized(reservation.upload.url, {
        method: "PUT",
        headers: { "Content-Type": photo.file!.type },
        body: photo.file,
      });
    progress.uploaded = true;
  }
  if (!progress.completed) {
    await write(
      `/api/photos/${part(reservation.photo_id)}/complete`,
      {},
      `${key}:complete`,
    );
    progress.completed = true;
  }
  return reservation.photo_id;
}
export async function preparePhoto(file: File): Promise<Photo> {
  const photo = await (await import("./platform-demo")).preparePhoto(file);
  // Client preview and upload use the same EXIF-free image; the server sanitizes again.
  const raw = atob(photo.data.split(",")[1]);
  photo.file = new Blob([Uint8Array.from(raw, (c) => c.charCodeAt(0))], {
    type: "image/jpeg",
  });
  return photo;
}
export type Favorites = { station_ids: string[]; version: number };
export async function getFavorites(): Promise<Favorites> {
  if (browserDemo)
    return JSON.parse(
      sessionStorage.getItem(`smt.favorites.${(await member())!.id}`) ||
        '{"station_ids":[],"version":0}',
    );
  return authorized<Favorites>("/api/me/favorite-stations");
}
export async function saveFavorites(
  station_ids: string[],
  version: number,
  key: string,
): Promise<Favorites> {
  if (browserDemo) {
    const result = { station_ids, version: version + 1 };
    sessionStorage.setItem(
      `smt.favorites.${(await member())!.id}`,
      JSON.stringify(result),
    );
    return result;
  }
  return authorized<Favorites>("/api/me/favorite-stations", {
    method: "PUT",
    headers: { "Content-Type": "application/json", "Idempotency-Key": key },
    body: JSON.stringify({ station_ids, version }),
  });
}
export async function submitReport(
  input: Parameters<typeof import("./platform-demo").submitReport>[0] & {
    observed_at?: string;
  },
  key: string,
): Promise<void> {
  if (browserDemo) {
    (await import("./platform-demo")).submitReport(input, key);
    return;
  }
  const photo_id = input.photo
    ? await uploadPhoto(
        input.photo,
        { device_id: input.device_id },
        `${key}:photo`,
      )
    : undefined;
  await write(
    `/api/devices/${part(input.device_id)}/reports`,
    {
      station_id: input.station_id,
      status: input.status,
      description: input.description.trim(),
      observed_at: input.observed_at,
      photo_id,
    },
    key,
  );
}
export async function submitProposal(
  input: Parameters<typeof import("./platform-demo").submitProposal>[0],
  key: string,
): Promise<void> {
  if (browserDemo) {
    (await import("./platform-demo")).submitProposal(input, key);
    return;
  }
  const { photo: attachment, ...body } = input;
  const item = await write<BackendProposal>("/api/proposals", body, key);
  if (attachment) {
    try {
      await uploadPhoto(
        attachment,
        { proposal_id: item.proposal_id },
        `${key}:photo`,
      );
    } catch {
      throw new Error(
        "La proposta è salvata, ma la foto non è ancora allegata. Ritenta con gli stessi dati per completarla senza duplicare la proposta.",
      );
    }
  }
}
export async function reviewProposal(
  id: string,
  decision: "approved" | "rejected",
  version: number,
  reason: string,
  key: string,
): Promise<void> {
  if (browserDemo) {
    (await import("./platform-demo")).reviewProposal(id, decision);
    return;
  }
  await write(
    `/api/moderation/proposals/${part(id)}/review`,
    { decision, version, reason },
    key,
  );
}
export async function reviewPhoto(
  id: string,
  origin: "report" | "proposal",
  decision: "approved" | "rejected",
  version: number,
  reason: string,
  key: string,
): Promise<void> {
  if (browserDemo) {
    (await import("./platform-demo")).reviewPhoto(id, origin, decision);
    return;
  }
  await write(
    `/api/moderation/photos/${part(id)}/review`,
    { decision, version, reason },
    key,
  );
}
// Authenticated images use short-lived object URLs, released by the component.
export async function privatePhoto(id: string): Promise<string> {
  const value = await token();
  if (!value) throw new ApiError("Autenticazione richiesta", 401);
  const response = await fetch(resourceUrl(`/api/photos/${part(id)}/preview`), {
    headers: { Authorization: `Bearer ${value}` },
  });
  if (!response.ok)
    throw new ApiError("Anteprima privata non disponibile.", response.status);
  return URL.createObjectURL(await response.blob());
}
