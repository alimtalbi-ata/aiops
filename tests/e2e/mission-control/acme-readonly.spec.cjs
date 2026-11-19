const {test,expect}=require('../../../qa/mission-control/node_modules/@playwright/test');
// Authenticated API only: disable traces to avoid recording bearer credentials.
test.use({trace:'off',screenshot:'off',video:'off'});
test('runtime ACME read-only cross-contract and LIVE isolation',async({playwright})=>{
 const token=process.env.QA_VIEWER_TOKEN;
 test.skip(!token,'Approved viewer credential required');
 const url=new URL(process.env.BASE_URL);
 if(url.protocol!=='https:'&&!['localhost','127.0.0.1','[::1]'].includes(url.hostname)) throw Error('Viewer requires HTTPS or loopback');
 if(!/^[!-~]{32,256}$/.test(token)) throw Error('Invalid viewer format');
 const api=await playwright.request.newContext({baseURL:url.origin,extraHTTPHeaders:{Authorization:'Bearer '+token},ignoreHTTPSErrors:false});
 try{
  async function read(path,status=200){const r=await api.get(path,{maxRedirects:0});if(r.status()!==status)throw Error('Unexpected status '+r.status()+' for '+path);return r.json();}
  const session=await read('/api/mission-actions/session');
  expect(session.tenant_acl_qualified===false&&session.live_remediation_authorized===false).toBe(true);
  const {data:a,state}=await read('/api/mission-data/acme?mode=DEMO');
  const j=await read('/api/mission-actions/journey');
  expect(state==='AVAILABLE'&&a.classification==='SYNTHETIC_SIMULATION_ONLY'&&j.schema==='aiops.mission-actions.journey.v1'&&j.mode==='DEMO').toBe(true);
  expect(/^[a-f0-9]{64}$/.test(a.source_sha256)&&a.source_sha256===j.source_sha256).toBe(true);
  expect(a.runtime_attested===false&&j.runtime_attested===false&&a.live_remediation_authorized===false&&j.live_remediation_authorized===false).toBe(true);
  expect(a.incidents.some(i=>i.incident_id===j.incident_id)&&typeof j.run_id==='string'&&j.run_id.length>0).toBe(true);
  expect(a.kpis.affected_ci_count===j.affected_ci_ids.length&&JSON.stringify([...a.impact.affected_ci_ids].sort())===JSON.stringify([...j.affected_ci_ids].sort())).toBe(true);
  expect(a.kpis.runtime_open_incidents===null&&a.observed_at===null&&a.impact.operational_impact==='UNKNOWN').toBe(true);
  expect(a.history.every(h=>h.status==='MISSING'&&h.observed_at===null)&&j.timeline.every(h=>h.status==='MISSING')).toBe(true);
  const live=await read('/api/mission-data/acme?mode=LIVE',503);
  expect(live.reason==='TENANT_ACL_NOT_QUALIFIED'&&live.data===null).toBe(true);
 }finally{await api.dispose();}
});