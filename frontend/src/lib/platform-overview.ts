import { latest } from "./platform-demo";
import type { Data, DeviceStatus } from "./platform-demo";

const stopped = (status: DeviceStatus) =>
  status === "guasta" || status === "manutenzione";
const known = (status?: DeviceStatus) =>
  !!status && status !== "non_verificabile";

export function overviewFor(data: Data | null, now = Date.now()) {
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
