import test from 'node:test';
import assert from 'node:assert/strict';
import {createFsRealReadHandler} from './fs-real-http-adapter.mjs';

const base='/api/portal/fs-real/projection?mode=lab147&ticket_id=147';
const principal={actor:'lab-reader',tenant:'lab'};
function harness(authorize=async()=>true) {
  let reads=0;
  const read=async()=>{reads++;return {glpi_ticket_id:147,synthetic:true,no_live_effects:true,state:'BLOCKED',run_id:'RUN-LAB147'};};
  const handler=createFsRealReadHandler({authorize,readCore:read,readTemporal:read,readPolicy:read,readQuestions:read});
  async function call(url=base,method='GET',actor=principal) {
    const res={headers:{},setHeader(k,v){this.headers[k]=v;},end(s){this.body=JSON.parse(s);}};
    await handler({url,method,principal:actor},res);
    return res;
  }
  return {call,get reads(){return reads;}};
}
test('query pollution and wrong ticket fail closed before service reads',async()=>{
  const invalid=[
    base+'&ticket_id=146',base+'&mode=insufficient',
    base+'&actor=admin',base.replace('ticket_id=147','ticket_id=146'),
    base.replace('mode=lab147','mode=Lab147'),
    '/api/portal/fs-real/projection-extra?mode=lab147&ticket_id=147'
  ];
  const h=harness();
  for(const url of invalid) assert.equal((await h.call(url)).statusCode,400,url);
  assert.equal(h.reads,0);
});
test('denied or malformed ACL decisions never read services',async()=>{
  for(const decision of [false,null,undefined,1,'true',{allowed:true}]) {
    const h=harness(async()=>decision);
    const r=await h.call();
    assert.equal(r.statusCode,403);
    assert.equal(h.reads,0);
    assert.equal(r.headers['Cache-Control'],'no-store, private');
  }
});
test('ACL failure returns unavailable without invoking readers',async()=>{
  const h=harness(async()=>{throw new Error('acl service unavailable');});
  const r=await h.call();
  assert.equal(r.statusCode,503);
  assert.equal(h.reads,0);
  assert.equal(r.body.error,'UNAVAILABLE');
});
test('missing principal and mutating method are rejected without reads',async()=>{
  const h=harness();
  assert.equal((await h.call(base,'GET',null)).statusCode,401);
  assert.equal((await h.call(base,'POST')).statusCode,405);
  assert.equal(h.reads,0);
});
