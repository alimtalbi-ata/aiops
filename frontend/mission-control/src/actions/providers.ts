import type { ActionProvider, Command, Reply, Selection } from "./context";
type Json = Record<string, any>;
const blocked = (reason: string): Reply => ({state:"BLOCKED", detail:{reason}});
async function request(path: string, token: string, signal: AbortSignal, body?: object) {
  const response = await fetch("/api/mission-actions/"+path, {
    signal, cache:"no-store", credentials:"omit", redirect:"error",
    headers:{Authorization:"Bearer "+token, ...(body?{"Content-Type":"application/json"}:{})},
    ...(body?{method:"POST",body:JSON.stringify(body)}:{})
  });
  const data: Json = await response.json();
  return {http:response.status, data, ok:response.ok};
}
export function demoProvider(token: string): ActionProvider {
  let cursor = 0, snapshot = "";
  return {mode:"DEMO", async invoke(selection, command, signal) {
    if (!token) return blocked("VIEWER_REQUIRED");
    if (["execute","approve","reject"].includes(command)) return blocked("NO_RUNTIME_AUTHORITY");
    const r = await request("journey",token,signal);
    if (!r.ok) return {state:"BLOCKED",detail:r.data,http:r.http};
    const j = r.data;
    if (j.schema !== "aiops.mission-actions.journey.v1" || j.runtime_attested !== false ||
        j.live_remediation_authorized !== false || typeof j.source_sha256 !== "string")
      return blocked("UNQUALIFIED_DEMO_RESPONSE");
    const ids: Record<string,unknown> = {incident:j.incident_id,run:j.run_id,scenario:j.scenario_id};
    const matches = selection.view === "ci" ? Array.isArray(j.affected_ci_ids) && j.affected_ci_ids.includes(selection.id)
      : selection.view in ids ? ids[selection.view] === selection.id : selection.id === j.run_id;
    if (!matches || (selection.runId !== undefined && selection.runId !== j.run_id))
      return blocked("SELECTION_NOT_BOUND_TO_DEMO_FIXTURE");
    if (snapshot !== j.source_sha256) {cursor=0; snapshot=j.source_sha256;}
    if (command === "rag" && selection.view === "ci") {
      const rag = await request("rag?asset="+encodeURIComponent(selection.id),token,signal);
      return {state:rag.ok && rag.data.state==="SYNTHETIC_REFERENCE_ONLY" && rag.data.asset===selection.id &&
        rag.data.llm_inference_performed===false && rag.data.live_remediation_authorized===false?"SIMULATED":"UNKNOWN",detail:rag.data,http:rag.http};
    }
    if (command !== "inspect") {
      if (selection.view !== "scenario" || !["start","advance","pause","reset","replay"].includes(command))
        return blocked("COMMAND_NOT_APPLICABLE");
      const story = await request("story",token,signal,{action:command,cursor,mode:"story"});
      if (!story.ok || story.data.schema!=="aiops.acme-explore-story.v1" ||
          story.data.source_sha256!==snapshot || story.data.scenario?.run_id!==j.run_id ||
          story.data.runtime_attested!==false || story.data.live_remediation_authorized!==false ||
          !Number.isInteger(story.data.cursor)) return {state:"UNKNOWN",detail:{reason:"STORY_NOT_BOUND"},http:story.http};
      if (!signal.aborted) cursor=story.data.cursor;
      return {state:"SIMULATED",detail:story.data,http:story.http};
    }
    const c=j.cockpit;
    const projections: Record<string,unknown> = {
      incident:c?.lifecycle, ci:j.affected_ci_ids, run:c, scenario:{id:j.scenario_id,run:j.run_id},
      analysis:c?.analyst_critic_review, critic:c?.analyst_critic_review, policy:j.decision_preview?.policy,
      hitl:c?.itil_readiness, execution:j.decision_preview?.remediation_preview, evidence:c?.evidence_plan
    };
    const detail=projections[selection.view];
    return {state:detail==null?"UNKNOWN":"SIMULATED",detail:detail??{reason:"PROJECTION_MISSING"},http:r.http};
  }};
}
export function operationalProvider(viewerToken: string): ActionProvider {
  return {mode:"OPERATIONAL",async invoke(selection, command, signal) {
    if (selection.view !== "run" || command !== "inspect") return blocked("ACTOR_TENANT_CONTRACT_NOT_QUALIFIED");
    if (!viewerToken) return blocked("VIEWER_REQUIRED");
    const r=await request("run/"+encodeURIComponent(selection.id),viewerToken,signal);
    // Current portal contract is viewer-only and fails closed. Never promote a 200.
    return {state:r.ok?"UNKNOWN":"BLOCKED",detail:{reason:"ACTOR_TENANT_CONTRACT_NOT_QUALIFIED"},http:r.http};
  }};
}
