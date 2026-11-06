import test from 'node:test';
import assert from 'node:assert/strict';
import {createFsRealReadHandler} from './fs-real-http-adapter.mjs';

const url='/api/portal/fs-real/projection?mode=lab147&ticket_id=147';
const principal={actor:'reader',tenant:'lab'};
async function invoke(handler, method='GET', path=url, actor=principal) {
  const res={headers:{},setHeader(k,v){this.headers[k]=v;},end(data){this.body=JSON.parse(data);}};
  await handler({method,url:path,principal:actor},res);
  return res;
}
const observed={glpi_ticket_id:147,synthetic:true,no_live_effects:true,state:'BLOCKED',
  incident_id:'INC-DEMO-FS-001',run_id:'RUN-4FABD1786F107E51',evidence_id:'EVD-D2069BA816126499'};
test('authorized GET projects only scoped observed states and no approvals',async()=>{
  const handler=createFsRealReadHandler({authorize:async()=>true,readCore:async()=>({...observed,approved:true,resolved:true}),
    readTemporal:async()=>({...observed,state:'WAITING_HUMAN'}),readPolicy:async()=>observed});
  const r=await invoke(handler);
  assert.equal(r.statusCode,200);assert.equal(r.body.core.state,'BLOCKED');
  assert.equal(r.body.temporal.state,'WAITING_HUMAN');assert.equal(r.body.approved,false);
  assert.equal(r.body.resolved,false);assert.equal(r.headers['Cache-Control'],'no-store, private');
});
test('no principal denies without reading services',async()=>{
  let reads=0;const handler=createFsRealReadHandler({authorize:async()=>true,readCore:()=>{reads++;}});
  const r=await invoke(handler,'GET',url,null);
  assert.equal(r.statusCode,401);assert.equal(reads,0);
});
test('ACL denied before service reads',async()=>{
  let reads=0;const handler=createFsRealReadHandler({authorize:async()=>false,readCore:()=>{reads++;}});
  assert.equal((await invoke(handler)).statusCode,403);assert.equal(reads,0);
});
test('malformed requests and mutation verbs fail closed',async()=>{
  const handler=createFsRealReadHandler({authorize:async()=>true});
  for(const [method,path,status] of [
    ['POST',url,405],['GET',url.replace('147','146'),400],
    ['GET',url+'&tenant=other',400],['GET',url+'&mode=insufficient',400],
    ['GET',url.replace('lab147','live'),400],['GET','/api/portal/fs-real/projection-evil?mode=lab147&ticket_id=147',400]
  ]) assert.equal((await invoke(handler,method,path)).statusCode,status);
});
test('failed reader remains UNKNOWN, no fabricated resolved state',async()=>{
  const handler=createFsRealReadHandler({authorize:async()=>true,readCore:async()=>{throw Error('offline');}});
  const r=await invoke(handler);
  assert.equal(r.statusCode,200);assert.equal(r.body.core.state,'UNKNOWN');
  assert.equal(r.body.resolved,false);
});
test('insufficient data projects bounded questions without GLPI writes',async()=>{
  const handler=createFsRealReadHandler({authorize:async()=>true,readQuestions:async()=>['Quelle politique de rétention ?']});
  const r=await invoke(handler,'GET',url.replace('lab147','insufficient'));
  assert.equal(r.statusCode,200);assert.deepEqual(r.body.questions,['Quelle politique de rétention ?']);
});
