export const jobs = ["aiops2-core", "aiops2-worker", "aiops2-twin", "aiops2-policy", "aiops2-evidence", "aiops2-portal"] as const;
export type Job = typeof jobs[number];
export type Mode = "LIVE" | "DEMO";
export type HealthMode = Mode | "PLATFORM";
export type Dataset = "incidents" | "core" | "fs-lab" | "evidence" | "logs" | "traces" | "twin" | "impact" | "noc";
export type Point = { at: number; up: 0 | 1 };
export type Health = { job: Job; points: Point[]; classification: "PLATFORM_TECHNICAL_ONLY"; freshness: "QUERY_EVALUATION_TIME_NOT_SCRAPE_TIME" };
export type Result<T> = { mode: HealthMode; source: string; retrieved_at: number | null; tenant_acl_qualified: false } & (
  { state: "AVAILABLE"; reason: null; data: T } |
  { state: "UNKNOWN"; reason: string; data: null }
);
export type Options = { token: string; signal?: AbortSignal };
function unavailable<T>(mode: HealthMode, source: string, reason: string): Result<T> {
  return { mode, source, retrieved_at: null, tenant_acl_qualified: false, state: "UNKNOWN", reason, data: null };
}
async function read<T>(path: string, mode: HealthMode, source: string, options: Options): Promise<Result<T>> {
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
export function readHealth(job: Job, mode: HealthMode, options: Options, minutes = 0): Promise<Result<Health>> {
  return read<Health>("health?" + new URLSearchParams({ job, mode, minutes: String(minutes) }), mode, "prometheus", options).then(result => {
    if (result.state === "UNKNOWN") return result;
    const d = result.data;
    if (mode !== "PLATFORM" || d.job !== job || d.classification !== "PLATFORM_TECHNICAL_ONLY" ||
        d.freshness !== "QUERY_EVALUATION_TIME_NOT_SCRAPE_TIME" || !Array.isArray(d.points) ||
        !d.points.length || d.points.some(p => !p || !Number.isFinite(p.at) || (p.up !== 0 && p.up !== 1)))
      return unavailable<Health>(mode, "prometheus", "INVALID_RESPONSE");
    return result;
  });
}
export function readDataset<K extends Dataset>(dataset: K, mode: Mode, options: Options): Promise<Result<DatasetMap[K]>> {
  return read<never>("datasets/" + encodeURIComponent(dataset) + "?" + new URLSearchParams({ mode }), mode, dataset, options).then(result => result.state === "UNKNOWN" ? result : unavailable<never>(mode, dataset, "UNQUALIFIED_DATA"));
}

export type JobStatus = { job: Job; status: "UP" | "DOWN"; at: number; reason: null } | { job: Job; status: "UNKNOWN"; at: null; reason: "NO_SAMPLES" };
export type PlatformSummary = { items: JobStatus[]; counts: Record<"UP"|"DOWN"|"UNKNOWN", number>; classification: "PLATFORM_TECHNICAL_ONLY"; freshness: "QUERY_EVALUATION_TIME_NOT_SCRAPE_TIME" };
export async function readPlatformSummary(options: Options): Promise<Result<PlatformSummary>> {
  const r = await read<PlatformSummary>("health/jobs", "PLATFORM", "prometheus", options);
  if (r.state === "UNKNOWN") return r;
  const d = r.data;
  if (!d || d.classification !== "PLATFORM_TECHNICAL_ONLY" || d.freshness !== "QUERY_EVALUATION_TIME_NOT_SCRAPE_TIME" ||
      !Array.isArray(d.items) || d.items.length !== jobs.length || !d.counts ||
      jobs.some(job => d.items.filter(i => i && i.job === job).length !== 1) ||
      d.items.some(i => i.status === "UNKNOWN" ? i.at !== null || i.reason !== "NO_SAMPLES" :
        !["UP","DOWN"].includes(i.status) || !Number.isFinite(i.at) || i.reason !== null) ||
      (["UP","DOWN","UNKNOWN"] as const).some(s => d.counts[s] !== d.items.filter(i => i.status === s).length))
    return unavailable("PLATFORM", "prometheus", "INVALID_RESPONSE");
  return r;
}
// Proposed presentation contracts, not a claim of authorized upstream availability.
// Null values denote missing observations, never zero.
export type MetricPoint = { at: number; value: number | null };
export type MetricSeries = { id: string; label: string; unit: string; points: MetricPoint[]; source: string };
export type CoreKpis = { runs_total: number; running: number; blocked: number; resolved: number; open_incidents: number; open_p1: number };
export type TwinNode = { node_id: string; type: string; name: string; site: string | null; state: string; criticality: string | number | null; health: number | null; confidence: number | null };
export type TwinEdge = { edge_id: string; source_id: string; target_id: string; relation_type: string; redundancy: unknown; confidence: number | null };
export type TwinGraph = { nodes: TwinNode[]; edges: TwinEdge[] };
export type Incident = { incident_id: string; title: string; severity: string; state: string; service_id: string | null; synthetic: boolean };
export type EvidenceItem = { evidence_id: string; source: string; observed_at: string | null; known_at: string; claim: string; confidence: number; payload_hash: string };
export type DatasetMap = { core: CoreKpis; "fs-lab": { series: MetricSeries[] }; evidence: { items: EvidenceItem[] }; incidents: { items: Incident[] }; twin: TwinGraph; impact: { root: string; affected: { node_id: string; depth: number }[] }; logs: never; traces: never; noc: never };
