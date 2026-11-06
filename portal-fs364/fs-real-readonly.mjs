/** FS364 opt-in readonly Portal projection. Backend must enforce existing auth and ACL. */
export const TICKET_ID = 147;
const STATES = new Set(['UNKNOWN','PENDING','RUNNING','BLOCKED','FAILED','WAITING_HUMAN']);
export function validateProjection(p, mode) {
  if (!['lab147','insufficient'].includes(mode) || !p || Array.isArray(p) ||
      p.mode !== mode || p.glpi_ticket_id !== 147 || p.synthetic !== true ||
      p.no_live_effects !== true || (p.approved != null && p.approved !== false) ||
      (p.resolved != null && p.resolved !== false))
    throw new Error('UNTRUSTED_PROJECTION');
  if (p.questions != null && (!Array.isArray(p.questions) || p.questions.length > 12 ||
      p.questions.some(q => typeof q !== 'string' || q.length > 500)))
    throw new Error('INVALID_HUMAN_QUESTIONS');
  for (const service of ['core','temporal','policy'])
    if (!STATES.has(p[service]?.state)) throw new Error('INVALID_SERVICE_STATE');
  for (const [key,prefix] of [['incident_id','INC'],['run_id','RUN'],['evidence_id','EVD']])
    if (p[key] != null && !(new RegExp('^'+prefix+'-[A-Z0-9-]{1,80}$')).test(p[key]))
      throw new Error('INVALID_CORRELATION');
  return {ticket:147, mode, incident:p.incident_id ?? 'UNKNOWN', run:p.run_id ?? 'UNKNOWN',
    evidence:p.evidence_id ?? 'UNKNOWN', core:p.core.state, temporal:p.temporal.state,
    policy:p.policy.state, questions: mode === 'insufficient' && Array.isArray(p.questions)
      ? p.questions.filter(q => typeof q === 'string').slice(0,12) : []};
}
export async function fetchProjection(mode, fetchImpl = fetch, signal) {
  if (!['lab147','insufficient'].includes(mode)) throw new Error('INVALID_MODE');
  const r = await fetchImpl('/api/portal/fs-real/projection?mode='+mode+'&ticket_id=147',
    {method:'GET',credentials:'same-origin',cache:'no-store',
     headers:{Accept:'application/json'},signal});
  if (r.redirected === true) throw new Error('UNAVAILABLE_REDIRECT');
  if (typeof r.url === 'string' && r.url) {
    const target = new URL(r.url, 'http://localhost');
    const expected = '/api/portal/fs-real/projection?mode='+mode+'&ticket_id=147';
    if (target.pathname+target.search !== expected ||
        (typeof location !== 'undefined' && target.origin !== location.origin))
      throw new Error('UNAVAILABLE_REDIRECT');
  }
  if (!r.ok) throw new Error('UNAVAILABLE_HTTP_'+r.status);
  if (!(r.headers.get('content-type')||'').toLowerCase().includes('application/json'))
    throw new Error('UNAVAILABLE_NON_JSON');
  return validateProjection(await r.json(),mode);
}
export function mountFsReal(root, fetchImpl = fetch) {
  if (!root || typeof root.replaceChildren !== 'function') throw new Error('ROOT_REQUIRED');
  let generation=0, controller;
  const status=document.createElement('pre');
  status.setAttribute('role','status');
  const unavailable=()=>{status.textContent='UNAVAILABLE — Core/Temporal/Policy UNKNOWN — SYNTHETIC — NO_LIVE_EFFECTS — fraîcheur/approbation/résolution non attestées';};
  unavailable();
  const buttons=[['lab147','Incident lab 147'],['insufficient','Données insuffisantes']].map(([mode,label])=>{
    const button=document.createElement('button');button.type='button';button.textContent=label;
    button.addEventListener('click',async()=>{
      const current=++generation;controller?.abort();controller=new AbortController();unavailable();
      try {
        const p=await fetchProjection(mode,fetchImpl,controller.signal);
        if(current!==generation)return;
        status.textContent='SYNTHETIC — NO_LIVE_EFFECTS — GLPI 147\nIncident: '+p.incident+
          '\nRun: '+p.run+'\nEvidence: '+p.evidence+'\nCore: '+p.core+
          '\nTemporal: '+p.temporal+'\nPolicy: '+p.policy+
          '\nFreshness: NOT_ATTESTED\nApproval: NOT_ATTESTED\nResolution: NOT_ATTESTED'+
          (p.questions.length?'\nQuestions humaines GLPI/Copilot:\n'+p.questions.join('\n'):'');
      } catch {if(current===generation)unavailable();}
    });return button;
  });
  root.replaceChildren(...buttons,status);
  return ()=>{++generation;controller?.abort();root.replaceChildren();};
}
