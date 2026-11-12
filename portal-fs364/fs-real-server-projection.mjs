/** FS364 server-side projection builder. Mount ONLY behind the existing authenticated Portal route and tenant/actor ACL. */
const STATES = new Set(['UNKNOWN','PENDING','RUNNING','BLOCKED','FAILED','WAITING_HUMAN']);
const MODES = new Set(['lab147','insufficient']);
const unavailable = (mode) => ({
  mode, glpi_ticket_id:147, synthetic:true, no_live_effects:true,
  approved:false, resolved:false, core:{state:'UNKNOWN'},
  temporal:{state:'UNKNOWN'}, policy:{state:'UNKNOWN'}, questions:[]
});
function state(value) {
  return typeof value === 'string' && STATES.has(value) ? value : 'UNKNOWN';
}
/**
 * Dependencies are authenticated, tenant-scoped READ operations supplied by the host.
 * Never use this function as an HTTP handler without the host's existing auth/ACL middleware.
 * Any missing/failed dependency produces UNKNOWN, never inferred approval or RESOLVED.
 */
export async function buildFsRealProjection({mode, ticketId, principal, authorize, readCore, readTemporal, readPolicy, readQuestions}) {
  if (!MODES.has(mode) || ticketId !== 147) throw new Error('INVALID_REQUEST');
  // A truthy placeholder is not an authenticated tenant-scoped identity.
  // The host still owns authentication; this only rejects malformed principals.
  if (!principal || typeof principal !== 'object' || Array.isArray(principal) ||
      typeof principal.actor !== 'string' || !principal.actor.trim() ||
      typeof principal.tenant !== 'string' || !principal.tenant.trim() ||
      typeof authorize !== 'function' ||
      (await authorize(principal, {ticketId:147, scope:'fs-real:read', mode})) !== true)
    throw new Error('FORBIDDEN');
  const result = unavailable(mode);
  const safe = async (fn) => {
    if (typeof fn !== 'function') return null;
    try { return await fn({principal,ticketId:147,mode}); } catch { return null; }
  };
  const [core,temporal,policy] = await Promise.all([
    safe(readCore),safe(readTemporal),safe(readPolicy)
  ]);
  // Trust a cross-service correlation only after Core itself is tenant-scoped,
  // synthetic, non-live and bound to ticket 147. A matching untrusted run_id
  // alone must never authenticate a Temporal/Policy observation.
  const trustedCore = core?.glpi_ticket_id === 147 && core?.synthetic === true &&
    core?.no_live_effects === true;
  const trustedRun = trustedCore && typeof core.run_id === 'string' &&
    /^RUN-[A-Z0-9-]{1,80}$/.test(core.run_id) ? core.run_id : null;
  // No historic ticket 146 approval or state may be projected onto ticket 147.
  for (const [key,source] of [['core',core],['temporal',temporal],['policy',policy]]) {
    // A ticket match alone does not prove that services describe the same run.
    // If a service supplies a run correlation, require the Core run to match.
    const correlated = key === 'core' ? trustedCore :
      (trustedRun !== null && source?.run_id === trustedRun &&
       // Optional correlation identifiers must never contradict Core.
       (source?.incident_id == null ||
        (typeof core?.incident_id === 'string' && source.incident_id === core.incident_id)) &&
       (source?.evidence_id == null ||
        (typeof core?.evidence_id === 'string' && source.evidence_id === core.evidence_id)));
    if (correlated && source?.glpi_ticket_id === 147 && source?.synthetic === true &&
        source?.no_live_effects === true) result[key] = {state:state(source.state)};
  }
  if (trustedCore) {
    for (const [key,prefix] of [['incident_id','INC'],['run_id','RUN'],['evidence_id','EVD']]) {
      if (typeof core[key] === 'string' && new RegExp('^'+prefix+'-[A-Z0-9-]{1,80}$').test(core[key]))
        result[key] = core[key];
    }
  }
  // Human questions must not be exposed when the Core ticket binding is untrusted.
  // A mis-scoped questions reader must not leak ticket 146 or another tenant's context.
  // Do not even invoke the GLPI/Copilot reader before Core proves ticket binding.
  // This prevents unnecessary cross-tenant reads on missing or mismatched Core data.
  const questions = mode === 'insufficient' && trustedCore ? await safe(readQuestions) : null;
  if (mode === 'insufficient' && trustedCore && Array.isArray(questions) &&
      questions.length <= 12 && questions.every(q => typeof q === 'string' && q.length <= 500))
    result.questions = questions;
  return result;
}
