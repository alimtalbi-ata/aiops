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
export function demoProvider(token: string, operatorToken?: string): ActionProvider {
  let cursor = 0, snapshot = "";
  let receipt: Json | undefined;
  return {mode:"DEMO", canSimulate: Boolean(operatorToken), async invoke(selection, command, signal) {
    if (!token) return blocked("VIEWER_REQUIRED");
    if (["approve","reject"].includes(command)) return blocked("NO_RUNTIME_AUTHORITY");
    const r = await request("journey",token,signal);
    if (!r.ok) return {state:"BLOCKED",detail:r.data,http:r.http};
    const j = r.data;
    if (j.schema !== "aiops.mission-actions.journey.v1" || j.mode !== "DEMO" || j.runtime_attested !== false ||
        j.live_remediation_authorized !== false || typeof j.source_sha256 !== "string")
      return blocked("UNQUALIFIED_DEMO_RESPONSE");
    const ids: Record<string,unknown> = {incident:j.incident_id,run:j.run_id,scenario:j.scenario_id};
    const matches = selection.view === "ci" ? Array.isArray(j.affected_ci_ids) && j.affected_ci_ids.includes(selection.id)
      : selection.view in ids ? ids[selection.view] === selection.id : selection.id === j.run_id;
    if (!matches || (selection.runId !== undefined && selection.runId !== j.run_id))
      return blocked("SELECTION_NOT_BOUND_TO_DEMO_FIXTURE");
    if (snapshot !== j.source_sha256) {cursor=0; snapshot=j.source_sha256; receipt=undefined;}
    if (command === "execute") {
      if (selection.view !== "execution" || !operatorToken) return blocked("DEMO_OPERATOR_REQUIRED");
      const sim = await request("demo/simulation",operatorToken,signal,{
        incident_id:j.incident_id,run_id:j.run_id,source_sha256:j.source_sha256
      });
      const d=sim.data;
      const valid=sim.ok && d.schema==="aiops.acme-demo-simulation-pipeline.v1" &&
        d.run_id===j.run_id && d.incident_id===j.incident_id && d.source_sha256===j.source_sha256 &&
        d.mode==="DEMO" && d.actual_recovery_state==="UNKNOWN" && d.runtime_execution_performed===false &&
        d.temporal_execution_performed===false && d.glpi_write_performed===false && d.live_remediation_authorized===false;
      if(valid && !signal.aborted) receipt=d;
      return {state:valid?"SIMULATED":sim.ok?"UNKNOWN":"BLOCKED",detail:valid?d:{reason:d.reason??d.detail??"SIMULATION_UNQUALIFIED"},http:sim.http};
    }
    if (command === "glpi" && selection.view === "itsm") {
      const g=await request("glpi",token,signal);
      return {state:g.ok?"UNKNOWN":"BLOCKED",detail:{reason:g.data.reason??g.data.detail??"GLPI_NOT_QUALIFIED",connection_state:g.data.connection_state??"UNKNOWN"},http:g.http};
    }
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
          story.data.source_sha256!==snapshot || story.data.scenario?.run_id!==j.run_id || story.data.scenario?.incident_id!==j.incident_id ||
          story.data.runtime_attested!==false || story.data.live_remediation_authorized!==false ||
          !Number.isInteger(story.data.cursor) || !Array.isArray(story.data.timeline) ||
          story.data.cursor<0 || story.data.cursor>=story.data.timeline.length ||
          story.data.timeline.some((step:Json)=>step?.status!=="MISSING")) return {state:"UNKNOWN",detail:{reason:"STORY_NOT_BOUND"},http:story.http};
      if (!signal.aborted) cursor=story.data.cursor;
      return {state:"SIMULATED",detail:story.data,http:story.http};
    }
    const c=j.cockpit;
    const projections: Record<string,unknown> = {
      incident:c?.lifecycle, ci:{selected:selection.id,affected:j.affected_cis,twin:j.twin}, run:c, scenario:{id:j.scenario_id,run:j.run_id,cursor,source_sha256:snapshot},
      analysis:j.decision_preview?.analyst, critic:j.decision_preview?.critic, policy:j.decision_preview?.policy,
      hitl:c?.itil_readiness, execution:j.decision_preview?.remediation_preview, evidence:{plan:c?.evidence_plan, simulation_receipt:receipt?.simulation??null, evidence_gate:receipt?.evidence_gate??null}, itsm:c?.itil_readiness
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
