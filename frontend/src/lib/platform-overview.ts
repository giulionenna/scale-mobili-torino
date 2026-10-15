import { latest } from "./platform-model";
import type { Data, DeviceStatus } from "./platform-model";

const stopped = (status: DeviceStatus) =>
  status === "guasta" || status === "manutenzione";
const known = (status?: DeviceStatus) =>
  !!status && status !== "non_verificabile";

export function overviewFor(data: Data | null, now = Date.now()) {
  if (data?.availability) {
    const snapshot = data.statistics;
    const comparable = (snapshot?.alignment.items || []).flatMap((item) => {
      const device = data.devices.find((d) => d.id === item.device_id);
      return device ? [device] : [];
    });
    const incidents = (rows: import("./platform-model").Incident[]) =>
      rows.flatMap((row) => {
        const device = data.devices.find((d) => d.id === row.device_id);
        if (!device) return [];
        const base = {
          id: "",
          device_id: device.id,
          station_id: device.station_id,
          description: "",
          author_id: "",
          author_name: "",
          status: row.status,
          recorded_at: row.latest_observed_at,
        };
        return [
          {
            device,
            latest: { ...base, observed_at: row.latest_observed_at },
            first: { ...base, observed_at: row.first_observed_at },
            count: row.observation_count,
            firstKnown: row.first_known,
            recent: true,
          },
        ];
      });
    return {
      comparable,
      differences: comparable.filter(
        (d) =>
          snapshot!.alignment.items.find((r) => r.device_id === d.id)
            ?.aligned === false,
      ),
      aligned: snapshot?.alignment.aligned || 0,
      alignment:
        snapshot?.alignment.percentage == null
          ? "—"
          : `${snapshot.alignment.percentage}%`,
      newStops: incidents(snapshot?.incidents.new_stops || []),
      streaks: incidents(snapshot?.incidents.streaks || []),
    };
  }
  const comparable =
    data?.devices.filter(
      (device) =>
        known(data.officialExamples[device.id]) &&
        known(latest(data, device.id)?.status),
    ) || [];
  const differences = comparable.filter(
    (device) =>
      data!.officialExamples[device.id] !== latest(data!, device.id)?.status,
  );
  const incidents = (data?.devices || [])
    .flatMap((device) => {
      const history = data!.reports
        .filter((r) => r.device_id === device.id)
        .sort(
          (a, b) =>
            b.observed_at.localeCompare(a.observed_at) ||
            b.recorded_at.localeCompare(a.recorded_at),
        );
      if (!history.length || !stopped(history[0].status)) return [];
      const boundary = history.findIndex((report) => !stopped(report.status));
      const sequence = boundary === -1 ? history : history.slice(0, boundary);
      const first = sequence[sequence.length - 1];
      const elapsed = now - Date.parse(first.observed_at);
      return [
        {
          device,
          latest: history[0],
          first,
          count: sequence.length,
          firstKnown: boundary === -1,
          recent: elapsed >= 0 && elapsed <= 24 * 60 * 60 * 1000,
        },
      ];
    })
    .sort((a, b) => b.latest.observed_at.localeCompare(a.latest.observed_at));
  return {
    comparable,
    differences,
    aligned: comparable.length - differences.length,
    alignment: comparable.length
      ? `${Math.round(((comparable.length - differences.length) / comparable.length) * 100)}%`
      : "—",
    newStops: incidents.filter((incident) => incident.recent),
    streaks: incidents
      .filter((incident) => incident.count >= 2)
      .sort(
        (a, b) =>
          b.count - a.count ||
          b.latest.observed_at.localeCompare(a.latest.observed_at),
      ),
  };
}
