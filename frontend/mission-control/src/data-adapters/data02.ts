// Isolated DATA02 candidate. No public barrel export or network access.
export type Mode = 'PLATFORM' | 'DEMO' | 'OPERATIONAL';
export type Provenance = {
  origin: 'SYNTHETIC' | 'OBSERVED' | 'UNKNOWN';
  domain: 'PLATFORM_TECHNICAL' | 'PLATFORM_AGGREGATE' | 'BUSINESS' | 'UNKNOWN';
  source: string;
  source_sha256: string | null;
  observed_at: number | null;
  evaluated_at: number | null;
  retrieved_at: number | null;
  freshness: 'UNKNOWN';
  tenant_acl_qualified: boolean;
  runtime_attested: boolean;
};
export type Coverage = { observed: number; expected: number; ratio: number };
export type View<T> = {
  schema: 'aiops.mission-data.view.v2'; mode: Mode;
  provenance: Provenance; coverage: Coverage | null;
} & ({state:'AVAILABLE'; data:T; reason:null} | {state:'UNKNOWN'; data:null; reason:string});
const record = (x: unknown): x is Record<string, unknown> =>
  typeof x === 'object' && x !== null && !Array.isArray(x);
const stamp = (x: unknown) => x === null || (typeof x === 'number' && Number.isSafeInteger(x) && x >= 0);
const digest = (x: unknown) => typeof x === 'string' && /^[a-f0-9]{64}$/.test(x);
export function validProvenance(x: unknown, mode: Mode): x is Provenance {
  if (!record(x)) return false;
  if (!['SYNTHETIC','OBSERVED','UNKNOWN'].includes(String(x.origin)) ||
      !['PLATFORM_TECHNICAL','PLATFORM_AGGREGATE','BUSINESS','UNKNOWN'].includes(String(x.domain)) ||
      typeof x.source !== 'string' || !x.source.trim() ||
      !(x.source_sha256 === null || digest(x.source_sha256)) ||
      !stamp(x.observed_at) || !stamp(x.evaluated_at) || !stamp(x.retrieved_at) ||
      x.freshness !== 'UNKNOWN' || typeof x.tenant_acl_qualified !== 'boolean' ||
      typeof x.runtime_attested !== 'boolean') return false;
  if (x.origin === 'SYNTHETIC') return mode === 'DEMO' && digest(x.source_sha256) &&
      x.observed_at === null && !x.runtime_attested && !x.tenant_acl_qualified;
  return mode !== 'DEMO' || x.origin === 'UNKNOWN';
}
export function validCoverage(x: unknown): x is Coverage {
  if (!record(x)) return false;
  const {observed,expected,ratio} = x;
  return typeof observed === 'number' && Number.isSafeInteger(observed) && observed >= 0 &&
    typeof expected === 'number' && Number.isSafeInteger(expected) && expected > 0 &&
    observed <= expected && typeof ratio === 'number' && Number.isFinite(ratio) &&
    ratio >= 0 && ratio <= 1 && Math.abs(ratio - observed / expected) <= 1e-12;
}
export function combineCoverage(items: readonly Coverage[]): Coverage | null {
  if (!items.length || !items.every(validCoverage)) return null;
  const observed = items.reduce((n,x)=>n+x.observed,0);
  const expected = items.reduce((n,x)=>n+x.expected,0);
  const result = {observed,expected,ratio:observed/expected};
  return validCoverage(result) ? result : null;
}
// Dataset-specific guards must validate nested values and provenance; never use a permissive guard.
export function validateView<T>(x: unknown, mode: Mode, guard: (v: unknown)=>v is T): x is View<T> {
  if (!record(x) || x.schema !== 'aiops.mission-data.view.v2' || x.mode !== mode ||
      !validProvenance(x.provenance,mode) || !(x.coverage === null || validCoverage(x.coverage))) return false;
  if (x.state === 'UNKNOWN') return x.data === null && typeof x.reason === 'string' && !!x.reason.trim();
  if (x.state !== 'AVAILABLE' || x.reason !== null || x.data === null) return false;
  const p = x.provenance;
  // No aggregate grants in current baseline and no business ACL qualification from client data.
  if (p.domain === 'PLATFORM_AGGREGATE' || p.origin === 'UNKNOWN' || p.domain === 'UNKNOWN') return false;
  if (mode === 'DEMO') return p.origin === 'SYNTHETIC' && guard(x.data);
  return p.origin === 'OBSERVED' && p.domain === 'PLATFORM_TECHNICAL' && !p.tenant_acl_qualified && guard(x.data);
}
