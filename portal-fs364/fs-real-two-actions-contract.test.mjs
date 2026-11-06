import test from 'node:test';
import assert from 'node:assert/strict';
import {createFsRealReadHandler} from './fs-real-http-adapter.mjs';
import {fetchProjection} from './fs-real-readonly.mjs';

// In-process contract test: no network, GLPI mutation, or Debian access.
const core = {glpi_ticket_id:147, synthetic:true, no_live_effects:true,
  state:'BLOCKED', run_id:'RUN-LAB147', incident_id:'INC-LAB147', evidence_id:'EVD-LAB147'};
function bridge({principal={actor:'reader',tenant:'lab'},authorize=async()=>true,
                 readCore=async()=>core,readTemporal=async()=>({...core,state:'WAITING_HUMAN'}),
                 readPolicy=async()=>({...core,state:'BLOCKED'}),
                 readQuestions=async()=>['GLPI : quelle rétention autorisée ?',
                   'Copilot : quelles dépendances vérifier ?']}={}) {
  let reads=0;
  const wrap=fn=>async ctx=>{reads++;return fn(ctx);};
  const handler=createFsRealReadHandler({authorize,readCore:wrap(readCore),
    readTemporal:wrap(readTemporal),readPolicy:wrap(readPolicy),
    readQuestions:wrap(readQuestions)});
  const fetchImpl=async (url,opts)=>{
    assert.equal(opts.method,'GET');
    assert.equal(opts.credentials,'same-origin');
    const res={headers:{},setHeader(k,v){this.headers[k.toLowerCase()]=v;},
      end(body){this.body=JSON.parse(body);}};
    await handler({method:opts.method,url,principal},res);
    return {ok:res.statusCode===200,status:res.statusCode,
      headers:{get:k=>res.headers[k.toLowerCase()]},json:async()=>res.body};
  };
  return {fetchImpl,get reads(){return reads;}};
}
test('both Portal actions consume one authenticated read-only backend contract',async()=>{
  const b=bridge();
  const lab=await fetchProjection('lab147',b.fetchImpl);
  assert.equal(lab.ticket,147);
  assert.equal(lab.core,'BLOCKED');
  assert.equal(lab.temporal,'WAITING_HUMAN');
  assert.equal(lab.policy,'BLOCKED');
  assert.equal(lab.run,'RUN-LAB147');
  assert.deepEqual(lab.questions,[]);
  const insufficient=await fetchProjection('insufficient',b.fetchImpl);
  assert.equal(insufficient.core,'BLOCKED');
  assert.match(insufficient.questions[0],/GLPI/);
  assert.match(insufficient.questions[1],/Copilot/);
  assert.equal(b.reads,7); // 3 readers in lab, 4 in insufficient
});
test('missing authenticated actor fails closed for both buttons before any read',async()=>{
  const b=bridge({principal:null});
  for(const mode of ['lab147','insufficient'])
    await assert.rejects(fetchProjection(mode,b.fetchImpl),/UNAVAILABLE_HTTP_401/);
  assert.equal(b.reads,0);
});
test('tenant ACL denial fails closed for both buttons before any read',async()=>{
  const b=bridge({authorize:async()=>false});
  for(const mode of ['lab147','insufficient'])
    await assert.rejects(fetchProjection(mode,b.fetchImpl),/UNAVAILABLE_HTTP_403/);
  assert.equal(b.reads,0);
});
test('unavailable Core cannot lend Temporal/Policy a fabricated run',async()=>{
  const b=bridge({readCore:async()=>{throw Error('offline');}});
  const p=await fetchProjection('lab147',b.fetchImpl);
  assert.equal(p.core,'UNKNOWN');
  assert.equal(p.temporal,'UNKNOWN');
  assert.equal(p.policy,'UNKNOWN');
  assert.equal(p.run,'UNKNOWN');
});
test('ticket 146 observations cannot become ticket 147 state',async()=>{
  const b=bridge({readCore:async()=>({...core,glpi_ticket_id:146})});
  const p=await fetchProjection('lab147',b.fetchImpl);
  assert.equal(p.core,'UNKNOWN');
  assert.equal(p.temporal,'UNKNOWN');
  assert.equal(p.policy,'UNKNOWN');
});
