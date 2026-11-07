/**
 * FS364 read-only backend projection contract for /fs-real.
 * Opt-in: mount behind existing backend authentication and tenant ACL only.
 * No external I/O or mutation is performed by this module.
 */
export const UNKNOWN = "UNKNOWN";
const STATES = new Set(["UNKNOWN", "BLOCKED", "PENDING", "RUNNING", "SUCCEEDED", "FAILED"]);
function state(value) { return STATES.has(value) ? value : UNKNOWN; }
function sameTicket(value) { return String(value ?? "") === "147"; }
function verifiedCore(core) {
  return core && sameTicket(core.glpi_ticket_id) &&
    core.mode === "LIVE" && core.no_live_effects === true &&
    typeof core.run_id === "string" && core.run_id.length > 0;
}
function safeStatus(source, core) {
  if (!verifiedCore(core) || !source || source.run_id !== core.run_id ||
      !sameTicket(source.glpi_ticket_id) || source.mode !== "LIVE") return UNKNOWN;
  return state(source.status);
}
/**
 * Readers are trusted backend adapters, never browser-provided URLs.
 * authz must reject unauthenticated/unauthorized tenant/actor requests.
 * No reader may mutate Core, GLPI, Temporal or Policy.
 */
export async function projectFsReal({authz, readCore, readTemporal, readPolicy, readQuestions}, context, route) {
  if (typeof authz !== "function" || !(await authz(context, "fs-real:read", "147")))
    return {httpStatus: 403, body: {error: "FORBIDDEN"}};
  if (!["incident", "insufficient"].includes(route))
    return {httpStatus: 400, body: {error: "INVALID_ROUTE"}};
  let core = null;
  try { if (typeof readCore === "function") core = await readCore(context, "147"); }
  catch { /* fail closed */ }
  const bound = verifiedCore(core);
  const body = {
    ticket_id: "147", mode: "LIVE", read_only: true,
    approved: false, resolved: false, remediation_allowed: false,
    core: bound ? state(core.status) : UNKNOWN,
    temporal: UNKNOWN, policy: UNKNOWN,
    run_id: bound ? core.run_id : null,
    evidence_ids: bound && Array.isArray(core.evidence_ids) ? core.evidence_ids.filter(x=>typeof x==="string") : [],
    questions: [], outcome: "BLOCKED"
  };
  if (!bound) return {httpStatus: 200, body};
  const [temporal, policy] = await Promise.all([
    Promise.resolve().then(()=>typeof readTemporal==="function" ? readTemporal(context, core.run_id) : null).catch(()=>null),
    Promise.resolve().then(()=>typeof readPolicy==="function" ? readPolicy(context, core.run_id) : null).catch(()=>null)
  ]);
  body.temporal = safeStatus(temporal, core);
  body.policy = safeStatus(policy, core);
  if (route === "insufficient" && typeof readQuestions === "function") {
    try {
      const result = await readQuestions(context, core.run_id, "147");
      if (result && sameTicket(result.glpi_ticket_id) && result.run_id === core.run_id &&
          result.mode === "LIVE" && Array.isArray(result.questions)) {
        body.questions = result.questions.filter(q=>q && typeof q.id==="string" &&
          typeof q.text==="string" && ["GLPI","Copilot"].includes(q.source))
          .map(q=>({id:q.id,text:q.text,source:q.source}));
      }
    } catch { /* fail closed */ }
  }
  return {httpStatus: 200, body};
}
