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
    let body;
    try { body = await response.json(); } catch (error) {
      if (options.signal?.aborted) throw error;
      return unavailable(mode, source, "INVALID_RESPONSE");
    }
    if (!body || typeof body !== "object") return unavailable(mode, source, "INVALID_RESPONSE");
    if (body.mode !== mode || body.source !== source || body.tenant_acl_qualified !== false ||
        !Number.isFinite(body.retrieved_at)) return unavailable(mode, source, "INVALID_RESPONSE");
    if (body.state === "UNKNOWN" && body.data === null && typeof body.reason === "string")
      return body as Result<T>;
    if (response.ok && body.state === "AVAILABLE" && body.reason === null && body.data !== null && typeof body.data === "object")
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

export type AcmeProvenance = { source: "LOCAL_SYNTHETIC_FIXTURE"; source_ref: string; source_sha256: string; observed_at: null; freshness: "UNKNOWN"; scope: "STORY_OFFLINE" };
export type AcmeSnapshot = {
  classification: "SYNTHETIC_SIMULATION_ONLY"; source_sha256: string; source_artifact: string;
  observed_at: null; freshness: "UNKNOWN"; runtime_attested: false; live_remediation_authorized: false;
  kpis: { ci_count: number; incident_count: number; affected_ci_count: number; runtime_open_incidents: null };
  graph: { nodes: { node_id: string; type: string; name: string; state: "UNKNOWN"; health: null; provenance: AcmeProvenance }[];
    edges: { source_id: string; target_id: string; relation_type: "DEPENDS_ON"; provenance: AcmeProvenance }[] };
  impact: { path: string[]; affected_ci_ids: string[]; operational_impact: "UNKNOWN" };
  incidents: { incident_id: string; severity: "P1"|"P2"; role: string }[];
  history: { sequence: number; cue: string; service: string; status: "MISSING"; observed_at: null }[];
};
export async function readAcmeDemo(options: Options): Promise<Result<AcmeSnapshot>> {
  const r = await read<AcmeSnapshot>("acme?mode=DEMO", "DEMO", "acme", options);
  if (r.state === "UNKNOWN") return r;
  const d = r.data;
  if (!d || d.classification !== "SYNTHETIC_SIMULATION_ONLY" || d.runtime_attested !== false ||
      d.live_remediation_authorized !== false || d.observed_at !== null || d.freshness !== "UNKNOWN" ||
      !/^[a-f0-9]{64}$/.test(d.source_sha256) || !d.kpis || d.kpis.runtime_open_incidents !== null ||
      !Array.isArray(d.graph?.nodes) || !Array.isArray(d.graph?.edges) ||
      !Array.isArray(d.incidents) || !Array.isArray(d.history) ||
      d.graph.nodes.some(n => !n || n.health !== null || n.state !== "UNKNOWN" || n.provenance?.source_sha256 !== d.source_sha256) ||
      d.graph.edges.some(e => !e || e.relation_type !== "DEPENDS_ON" || e.provenance?.source_sha256 !== d.source_sha256) ||
      d.history.some(h => !h || h.status !== "MISSING" || h.observed_at !== null) ||
      d.impact?.operational_impact !== "UNKNOWN")
    return unavailable("DEMO", "acme", "INVALID_RESPONSE");
  return r;
}

export type AvailabilityHistory = {
  series: { job: Job; points: { at: number; up: 0|1|null }[]; observed: number; expected: number; coverage: number; last_evaluated_at: number|null }[];
  start: number; end: number; step_seconds: 60; coverage: number;
  classification: "PLATFORM_TECHNICAL_ONLY"; freshness: "QUERY_EVALUATION_TIME_NOT_SCRAPE_TIME";
};
export async function readAvailabilityHistory(options: Options, minutes = 60): Promise<Result<AvailabilityHistory>> {
  if (!Number.isInteger(minutes) || minutes < 1 || minutes > 1440) return unavailable("PLATFORM","prometheus","INVALID_WINDOW");
  const r = await read<AvailabilityHistory>("health/history?minutes="+minutes,"PLATFORM","prometheus",options);
  if (r.state === "UNKNOWN") return r;
  const d = r.data;
  if (!d || d.classification !== "PLATFORM_TECHNICAL_ONLY" || d.freshness !== "QUERY_EVALUATION_TIME_NOT_SCRAPE_TIME" ||
      d.step_seconds !== 60 || !Number.isFinite(d.start) || d.end-d.start !== minutes*60 ||
      !Array.isArray(d.series) || d.series.length !== jobs.length ||
      jobs.some(j => d.series.filter(s => s && s.job === j).length !== 1) ||
      d.series.some(s => !Array.isArray(s.points) || s.points.length !== minutes+1 ||
        s.points.some((p,i) => !p || p.at !== d.start+i*60 || ![0,1,null].includes(p.up)) ||
        s.expected !== minutes+1 || s.observed !== s.points.filter(p => p.up !== null).length ||
        s.coverage !== s.observed/s.expected ||
        s.last_evaluated_at !== lastEvaluation(s.points, p => p.up)) ||
      d.coverage !== d.series.reduce((n,s)=>n+s.observed,0)/(jobs.length*(minutes+1)))
    return unavailable("PLATFORM","prometheus","INVALID_RESPONSE");
  return r;
}

export type TechnicalMetric = "scrape-duration" | "scrape-samples";
export type TechnicalHistory = {
  metric: TechnicalMetric; prometheus_metric: string; unit: "seconds"|"samples";
  series: { job: Job; points: MetricPoint[]; coverage: number; last_evaluated_at: number|null }[];
  start: number; end: number; step_seconds: 60; aggregation: "MAX_BY_JOB";
  classification: "PLATFORM_TECHNICAL_ONLY"; freshness: "QUERY_EVALUATION_TIME_NOT_SCRAPE_TIME";
};
export async function readTechnicalHistory(metric: TechnicalMetric, options: Options, minutes=60): Promise<Result<TechnicalHistory>> {
  if (!Number.isInteger(minutes)||minutes<1||minutes>1440) return unavailable("PLATFORM","prometheus","INVALID_WINDOW");
  const r=await read<TechnicalHistory>("technical/"+metric+"?minutes="+minutes,"PLATFORM","prometheus",options);
  if (r.state==="UNKNOWN") return r;
  const d=r.data;
  if (!d || d.metric!==metric || d.prometheus_metric!==(metric==="scrape-duration"?"scrape_duration_seconds":"scrape_samples_scraped") ||
      d.unit!==(metric==="scrape-duration"?"seconds":"samples") ||
      d.classification!=="PLATFORM_TECHNICAL_ONLY" || d.freshness!=="QUERY_EVALUATION_TIME_NOT_SCRAPE_TIME" ||
      d.aggregation!=="MAX_BY_JOB" || d.step_seconds!==60 || !Number.isFinite(d.start) || d.end-d.start!==minutes*60 ||
      !Array.isArray(d.series)||d.series.length!==jobs.length ||
      jobs.some(j=>d.series.filter(s=>s&&s.job===j).length!==1) ||
      d.series.some(s=>!Array.isArray(s.points)||s.points.length!==minutes+1||
        s.points.some((p,i)=>!p||p.at!==d.start+i*60||(p.value!==null&&(!Number.isFinite(p.value)||p.value<0))) ||
        s.coverage!==s.points.filter(p=>p.value!==null).length/(minutes+1) ||
        s.last_evaluated_at!==lastEvaluation(s.points,p=>p.value)))
    return unavailable("PLATFORM","prometheus","INVALID_RESPONSE");
  return r;
}

export const aggregateMetrics = {
  core: ["aiops_runs_total","aiops_runs_running","aiops_runs_blocked","aiops_runs_resolved"],
  evidence: ["aiops_evidence_total"],
  twin: ["aiops_twin_nodes","aiops_twin_degraded","aiops_twin_failed"],
  "fs-lab": ["aiops2_fs_lab_used_percent","aiops2_fs_lab_alert_firing"],
  services: ["aiops_worker_up","aiops_policy_up","aiops_portal_up"]
} as const;
export type AggregateGroup = keyof typeof aggregateMetrics;
export type AggregateMetric<G extends AggregateGroup> = typeof aggregateMetrics[G][number];
export type AggregateHistory<G extends AggregateGroup> = {
  group: G; start: number; end: number; step_seconds: 60; coverage: number;
  classification: "PLATFORM_AGGREGATES_UNPARTITIONED"; freshness: "QUERY_EVALUATION_TIME_NOT_SCRAPE_TIME";
  series: {metric: AggregateMetric<G>; unit: "count"|"binary"|"percent"; value: number|null; points: MetricPoint[];
    coverage: number; last_evaluated_at: number|null; reason: null|"NO_CURRENT_SAMPLE"|"AMBIGUOUS_SERIES"}[];
};
export async function readAggregateKpis<G extends AggregateGroup>(group:G,options:Options,minutes=60):Promise<Result<AggregateHistory<G>>> {
  if (!Number.isInteger(minutes)||minutes<1||minutes>1440) return unavailable("PLATFORM","prometheus","INVALID_WINDOW");
  const r=await read<AggregateHistory<G>>("kpis/"+group+"?minutes="+minutes,"PLATFORM","prometheus",options);
  if (r.state==="UNKNOWN") return r;
  const d=r.data;
  const names: readonly string[]=aggregateMetrics[group];
  if (!d||d.group!==group||d.classification!=="PLATFORM_AGGREGATES_UNPARTITIONED"||
      d.freshness!=="QUERY_EVALUATION_TIME_NOT_SCRAPE_TIME"||d.step_seconds!==60||
      !Number.isFinite(d.start)||d.end-d.start!==minutes*60||!Array.isArray(d.series)||d.series.length!==names.length||
      names.some(n=>d.series.filter(s=>s&&s.metric===n).length!==1)||
      d.series.some(s=>{
        const unit=s.metric.endsWith("_percent")?"percent":s.metric.endsWith("_up")||s.metric.endsWith("_alert_firing")?"binary":"count";
        return s.unit!==unit||!Array.isArray(s.points)||s.points.length!==minutes+1||
          s.points.some((p,i)=>!p||p.at!==d.start+i*60||(p.value!==null&&
            (!Number.isFinite(p.value)||p.value<0||(unit==="percent"?p.value>100:unit==="binary"?p.value!==0&&p.value!==1:!Number.isInteger(p.value)))))||
          s.value!==s.points[minutes].value||s.coverage!==s.points.filter(p=>p.value!==null).length/(minutes+1)||
          s.last_evaluated_at!==lastEvaluation(s.points,p=>p.value)||
          (s.reason==="AMBIGUOUS_SERIES"?s.coverage!==0:s.reason!==(s.value===null?"NO_CURRENT_SAMPLE":null));
      }) || !Number.isFinite(d.coverage) || Math.abs(d.coverage-d.series.reduce((n,s)=>n+s.coverage,0)/names.length)>1e-12) return unavailable("PLATFORM","prometheus","INVALID_RESPONSE");
  return r;
}

/** No fallback across modes, providers or missing observations. */
export function aggregateSeries<G extends AggregateGroup>(result: Result<AggregateHistory<G>>, metric: AggregateMetric<G>): AggregateHistory<G>["series"][number] | null {
  return result.state === "AVAILABLE" ? result.data.series.find(s=>s.metric===metric) ?? null : null;
}
export function aggregateValue<G extends AggregateGroup>(result: Result<AggregateHistory<G>>, metric: AggregateMetric<G>): number|null {
  return aggregateSeries(result,metric)?.value ?? null;
}

function lastEvaluation<P extends {at:number}>(points: P[], value:(p:P)=>number|null):number|null {
  for(let i=points.length-1;i>=0;i--) if(value(points[i])!==null) return points[i].at;
  return null;
}
