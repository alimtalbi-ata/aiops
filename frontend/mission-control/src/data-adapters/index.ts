export const jobs = ["aiops2-core", "aiops2-worker", "aiops2-twin", "aiops2-policy", "aiops2-evidence", "aiops2-portal"] as const;
export type Job = typeof jobs[number];
export type Mode = "LIVE" | "DEMO";
export type Dataset = "core" | "fs-lab" | "evidence" | "logs" | "traces" | "twin" | "impact" | "noc";
export type Point = { at: number; up: 0 | 1 };
export type Health = { job: Job; points: Point[]; classification: "PLATFORM_TECHNICAL_ONLY"; freshness: "QUERY_EVALUATION_TIME_NOT_SCRAPE_TIME" };
export type Result<T> = { mode: Mode; source: string; retrieved_at: number | null; tenant_acl_qualified: false } & (
  { state: "AVAILABLE"; reason: null; data: T } |
  { state: "UNKNOWN"; reason: string; data: null }
);
type Options = { token: string; signal?: AbortSignal };
function unavailable<T>(mode: Mode, source: string, reason: string): Result<T> {
  return { mode, source, retrieved_at: null, tenant_acl_qualified: false, state: "UNKNOWN", reason, data: null };
}
async function read<T>(path: string, mode: Mode, source: string, options: Options): Promise<Result<T>> {
  try {
    const response = await fetch("/api/mission-data/" + path, {
      headers: { Authorization: "Bearer " + options.token }, credentials: "omit",
      cache: "no-store", redirect: "error", signal: options.signal
    });
    if (response.status !== 200 && response.status !== 503)
      return unavailable(mode, source, "HTTP_" + response.status);
    const body = await response.json();
    if (body.mode !== mode || body.source !== source || body.tenant_acl_qualified !== false ||
        !Number.isFinite(body.retrieved_at)) return unavailable(mode, source, "INVALID_RESPONSE");
    if (body.state === "UNKNOWN" && body.data === null && typeof body.reason === "string")
      return body as Result<T>;
    if (response.ok && body.state === "AVAILABLE" && body.reason === null && body.data !== null)
      return body as Result<T>;
    return unavailable(mode, source, "INVALID_RESPONSE");
  } catch (error) {
    if (options.signal?.aborted) throw error;
    return unavailable(mode, source, "NETWORK_UNAVAILABLE");
  }
}
export function readHealth(job: Job, mode: Mode, options: Options, minutes = 0): Promise<Result<Health>> {
  return read("health?" + new URLSearchParams({ job, mode, minutes: String(minutes) }), mode, "prometheus", options);
}
export function readDataset(dataset: Dataset, mode: Mode, options: Options): Promise<Result<never>> {
  return read("datasets/" + encodeURIComponent(dataset) + "?" + new URLSearchParams({ mode }), mode, dataset, options);
}
