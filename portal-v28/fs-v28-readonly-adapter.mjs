// V28 filesystem demo: read-only projection. No direct Core/Evidence access.
export const IDS = Object.freeze({incident:"INC-DEMO-FS-001",run:"RUN-4FABD1786F107E51",evidence:"EVD-D2069BA816126499"});
const STATES = new Set(["OPEN","ACKNOWLEDGED","INVESTIGATING","MITIGATING","RESOLVED","FAILED","BLOCKED","UNKNOWN"]);
export const unavailable = (reason="BACKEND_UNAVAILABLE") => ({source:"UNAVAILABLE",synthetic:true,noLiveEffects:true,ids:IDS,core:"UNKNOWN",temporal:"UNKNOWN",policy:"UNKNOWN",evidence:"UNKNOWN",incident:"UNKNOWN",approved:false,resolved:false,reason});
export function project(payload) {
  if (!payload || payload.incident_id!==IDS.incident || payload.run_id!==IDS.run || payload.evidence_id!==IDS.evidence) return unavailable("IDENTITY_MISMATCH");
  if (payload.synthetic!==true || payload.no_live_effects!==true || payload.source!=="CORE_EVIDENCE_READONLY") return unavailable("SAFETY_CONTRACT_MISMATCH");
  for(const key of ["incident_state","core_state","temporal_state","policy_state","evidence_state"]) if(!STATES.has(payload[key])) return unavailable("INVALID_STATE");
  return {source:payload.source,synthetic:true,noLiveEffects:true,ids:IDS,incident:payload.incident_state,core:payload.core_state,temporal:payload.temporal_state,policy:payload.policy_state,evidence:payload.evidence_state,approved:false,resolved:false,reason:"NO_SIGNED_HUMAN_APPROVAL_PROOF"};
}
export async function load({fetchImpl=fetch,signal}={}) {
  try {
    const r=await fetchImpl("/api/portal/demo/fs-v28",{method:"GET",credentials:"same-origin",cache:"no-store",redirect:"error",headers:{Accept:"application/json"},signal});
    if(!r.ok) return unavailable(r.status===401||r.status===403?"AUTH_REQUIRED":"BACKEND_UNAVAILABLE");
    if(!String(r.headers.get("content-type")||"").toLowerCase().includes("application/json")) return unavailable("INVALID_CONTENT_TYPE");
    return project(await r.json());
  } catch {return unavailable();}
}
