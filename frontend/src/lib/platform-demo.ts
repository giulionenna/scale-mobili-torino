// Dati ed accesso esclusivamente dimostrativi. Nessuna fonte GTT viene acquisita qui.
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
  synthetic: true;
};
export type Member = {
  id: string;
  name: string;
  role: "citizen" | "moderator";
};
export type Photo = {
  data: string;
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
  device_id?: string;
};
export type Data = {
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

export const stations: Station[] = [
  { id: "demo-porta-nuova", name: "Porta Nuova", area: "Metro M1" },
  { id: "demo-re-umberto", name: "Re Umberto", area: "Metro M1" },
  { id: "demo-vinzaglio", name: "Vinzaglio", area: "Metro M1" },
  { id: "demo-porta-susa", name: "Porta Susa", area: "Metro M1" },
];
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
export const gttSource =
  "https://www.gtt.to.it/cms/en/19-linee-e-orari/urbana/12186-metropolitana-aggiornamento-ascensori-e-scale-mobili";
const key = "smt.platform-demo.v2";
const userKey = "smt.platform-member.v2";

function initial(): Data {
  const devices: Device[] = stations.flatMap((s, i) => [
    {
      id: `demo-device-${i}-stairs`,
      station_id: s.id,
      kind: "scala_mobile" as Kind,
      name: "Scala mobile A",
      location: "Ingresso → mezzanino · esempio",
      synthetic: true as const,
    },
    {
      id: `demo-device-${i}-lift`,
      station_id: s.id,
      kind: "ascensore" as Kind,
      name: "Ascensore A",
      location: "Mezzanino → banchina · esempio",
      synthetic: true as const,
    },
    ...(i === 0
      ? [
          {
            id: "demo-device-0-stairs-b",
            station_id: s.id,
            kind: "scala_mobile" as Kind,
            name: "Scala mobile B",
            location: "Mezzanino → banchina · esempio",
            synthetic: true as const,
          },
        ]
      : []),
  ]);
  const examples: DeviceStatus[] = [
    "funzionante",
    "guasta",
    "funzionante",
    "funzionante",
    "manutenzione",
    "funzionante",
    "funzionante",
    "non_verificabile",
    "funzionante",
  ];
  const reports = devices.map((d, i) => ({
    id: `example-report-${i}`,
    station_id: d.station_id,
    device_id: d.id,
    status: examples[i],
    description:
      examples[i] === "manutenzione"
        ? "Esempio: è presente un cartello di manutenzione."
        : examples[i] === "non_verificabile"
          ? "Esempio: non è stato possibile verificare l’impianto."
          : examples[i] === "guasta"
            ? "Esempio: l’impianto non è in servizio."
            : d.kind === "ascensore"
              ? "Esempio: l’ascensore risponde alla chiamata."
              : "Esempio: la scala mobile è in movimento.",
    observed_at: new Date(Date.now() - (12 + i * 7) * 60000).toISOString(),
    recorded_at: new Date(Date.now() - (10 + i * 7) * 60000).toISOString(),
    author_id: "example-member",
    author_name: "Community · esempio",
    seeded: true,
  }));
  return {
    devices,
    reports,
    proposals: [],
    audit: [],
    officialExamples: {
      "demo-device-0-lift": "manutenzione",
      "demo-device-1-lift": "funzionante",
      "demo-device-2-stairs": "manutenzione",
    },
  };
}

export function load(): Data {
  const saved = sessionStorage.getItem(key);
  if (saved) return JSON.parse(saved);
  const value = initial();
  save(value);
  return value;
}
function save(data: Data) {
  sessionStorage.setItem(key, JSON.stringify(data));
}
export function member(): Member | null {
  const value = sessionStorage.getItem(userKey);
  return value ? JSON.parse(value) : null;
}
export function signIn(role: "citizen" | "moderator"): Member {
  const value: Member = {
    id: role === "moderator" ? "demo-moderator" : "demo-citizen",
    name: role === "moderator" ? "Moderatore demo" : "Cittadino demo",
    role,
  };
  sessionStorage.setItem(userKey, JSON.stringify(value));
  return value;
}
export function signOut() {
  sessionStorage.removeItem(userKey);
}
function actor(moderator = false): Member {
  const user = member();
  if (!user) throw new Error("Accedi prima di contribuire.");
  if (moderator && user.role !== "moderator")
    throw new Error("Questa operazione è riservata al moderatore.");
  return user;
}
export function latest(data: Data, id: string): Report | undefined {
  return data.reports
    .filter((r) => r.device_id === id)
    .sort(
      (a, b) =>
        b.observed_at.localeCompare(a.observed_at) ||
        b.recorded_at.localeCompare(a.recorded_at),
    )[0];
}
export function stationName(id: string) {
  return stations.find((s) => s.id === id)?.name || "Stazione non disponibile";
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
function checkStation(id: string) {
  if (!stations.some((s) => s.id === id))
    throw new Error("Scegli una stazione.");
}
function description(value: string) {
  if (value.trim().length > 1000)
    throw new Error("La descrizione può contenere al massimo 1.000 caratteri.");
  return value.trim();
}

export function submitReport(
  input: {
    station_id: string;
    device_id: string;
    status: DeviceStatus;
    description: string;
    photo?: Photo;
  },
  requestId: string,
): Data {
  const user = actor();
  const data = load();
  checkStation(input.station_id);
  const device = data.devices.find(
    (d) => d.id === input.device_id && d.station_id === input.station_id,
  );
  if (!device)
    throw new Error("Scegli un impianto della stazione selezionata.");
  if (!(input.status in labels)) throw new Error("Scegli lo stato osservato.");
  if (data.reports.some((r) => r.id === requestId)) return data;
  if (data.reports.length >= 200)
    throw new Error("Limite della demo raggiunto.");
  const now = new Date().toISOString();
  data.reports.push({
    ...input,
    id: requestId,
    author_id: user.id,
    author_name: user.name,
    description: description(input.description),
    photo: input.photo ? { ...input.photo, status: "pending" } : undefined,
    recorded_at: now,
    observed_at: now,
  });
  save(data);
  return data;
}
export function submitProposal(
  input: {
    station_id: string;
    kind: Kind;
    name: string;
    location: string;
    description: string;
    photo?: Photo;
  },
  requestId: string,
): Data {
  const user = actor();
  const data = load();
  checkStation(input.station_id);
  if (!["scala_mobile", "ascensore"].includes(input.kind))
    throw new Error("Scegli il tipo di impianto.");
  if (input.name.trim().length < 3 || input.name.trim().length > 100)
    throw new Error("Indica un nome da 3 a 100 caratteri.");
  if (input.location.trim().length < 5 || input.location.trim().length > 300)
    throw new Error("Descrivi dove si trova l’impianto (5–300 caratteri).");
  if (data.proposals.some((p) => p.id === requestId)) return data;
  if (
    data.devices.some(
      (d) =>
        d.station_id === input.station_id &&
        d.name.toLowerCase() === input.name.trim().toLowerCase(),
    )
  )
    throw new Error(
      "Esiste già un impianto con questo nome nella stazione. Controlla il censimento.",
    );
  data.proposals.push({
    ...input,
    id: requestId,
    name: input.name.trim(),
    location: input.location.trim(),
    description: description(input.description),
    actor_id: user.id,
    status: "pending",
    created_at: new Date().toISOString(),
    photo: input.photo ? { ...input.photo, status: "pending" } : undefined,
  });
  save(data);
  return data;
}
export function reviewProposal(
  id: string,
  decision: "approved" | "rejected",
): Data {
  const user = actor(true);
  const data = load();
  const proposal = data.proposals.find((p) => p.id === id);
  if (!proposal || proposal.status !== "pending")
    throw new Error("Questa proposta è già stata esaminata.");
  if (decision === "approved") {
    if (
      data.devices.some(
        (d) =>
          d.station_id === proposal.station_id &&
          d.name.toLowerCase() === proposal.name.toLowerCase(),
      )
    )
      throw new Error("Un impianto con questo nome è già presente.");
    const id = `demo-proposed-${proposal.id}`;
    data.devices.push({
      id,
      station_id: proposal.station_id,
      kind: proposal.kind,
      name: proposal.name,
      location: proposal.location,
      synthetic: true,
    });
    proposal.device_id = id;
  }
  proposal.status = decision;
  if (decision === "rejected" && proposal.photo)
    proposal.photo.status = "rejected";
  data.audit.push({
    actor: user.id,
    target: id,
    decision,
    recorded_at: new Date().toISOString(),
  });
  save(data);
  return data;
}
export function reviewPhoto(
  id: string,
  origin: "report" | "proposal",
  decision: "approved" | "rejected",
): Data {
  const user = actor(true);
  const data = load();
  const item =
    origin === "report"
      ? data.reports.find((r) => r.id === id)
      : data.proposals.find((p) => p.id === id);
  if (!item?.photo || item.photo.status !== "pending")
    throw new Error("Foto non più in revisione.");
  if (origin === "proposal" && (item as Proposal).status !== "approved")
    throw new Error("Approva prima l’impianto associato.");
  item.photo.status = decision;
  data.audit.push({
    actor: user.id,
    target: id,
    decision: `photo_${decision}`,
    recorded_at: new Date().toISOString(),
  });
  save(data);
  return data;
}
export async function preparePhoto(file: File): Promise<Photo> {
  if (!["image/jpeg", "image/png", "image/webp"].includes(file.type))
    throw new Error("Scegli una foto JPEG, PNG o WebP.");
  if (file.size > 5 * 1024 * 1024)
    throw new Error("La foto deve pesare al massimo 5 MB.");
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    throw new Error("Il file non è una fotografia valida.");
  }
  try {
    if (bitmap.width * bitmap.height > 20000000)
      throw new Error("La foto deve contenere al massimo 20 megapixel.");
    const ratio = Math.min(1, 1200 / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * ratio);
    canvas.height = Math.round(bitmap.height * ratio);
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Impossibile elaborare la foto.");
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    const encoded = canvas.toDataURL("image/jpeg", 0.78);
    if (encoded.length > 1000000)
      throw new Error("Scegli una foto meno complessa o più piccola.");
    return { data: encoded, status: "pending" };
  } finally {
    bitmap.close();
  }
}
