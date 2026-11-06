import test from 'node:test';
import assert from 'node:assert/strict';
import {createFsRealReadHandler} from './fs-real-http-adapter.mjs';

const base='/api/portal/fs-real/projection?mode=insufficient&ticket_id=147';
const principal={actor:'reader-147',tenant:'lab'};
const observed={glpi_ticket_id:147,synthetic:true,no_live_effects:true,
  state:'BLOCKED',run_id:'RUN-LAB147',incident_id:'INC-LAB147',evidence_id:'EVD-LAB147'};
async function request(handler, url=base, identity=principal) {
  const res={setHeader(){},end(body){this.body=JSON.parse(body);}};
  await handler({method:'GET',url,principal:identity},res);
  return res;
}

test('insufficient-data questions remain read-only and require a real scoped ACL',async()=>{
  const calls=[];
  const handler=createFsRealReadHandler({
    authorize:async(identity,scope)=>{
      assert.equal(identity,principal);
      assert.deepEqual(scope,{ticketId:147,scope:'fs-real:read',mode:'insufficient'});
      return true;
    },
    readCore:async context=>{calls.push(['core',context]);return observed;},
    readTemporal:async context=>{calls.push(['temporal',context]);return {...observed,state:'WAITING_HUMAN'};},
    readPolicy:async context=>{calls.push(['policy',context]);return {...observed,state:'BLOCKED',approved:true};},
    readQuestions:async context=>{calls.push(['questions',context]);return ['Quelle retention est autorisee ?'];}
  });
  const res=await request(handler);
  assert.equal(res.statusCode,200);
  assert.deepEqual(res.body.questions,['Quelle retention est autorisee ?']);
  assert.equal(res.body.core.state,'BLOCKED');
  assert.equal(res.body.temporal.state,'WAITING_HUMAN');
  assert.equal(res.body.policy.state,'BLOCKED');
  assert.equal(res.body.approved,false);
  assert.equal(res.body.resolved,false);
  assert.deepEqual(calls.map(([name])=>name).sort(),['core','policy','questions','temporal']);
  for(const [,context] of calls) assert.deepEqual(context,{principal,ticketId:147,mode:'insufficient'});
});

test('questions cannot leak across denied tenant ACL or ticket 146',async()=>{
  let reads=0;
  const handler=createFsRealReadHandler({
    authorize:async()=>false,
    readCore:async()=>{reads++;return observed;},
    readQuestions:async()=>{reads++;return ['private'];}
  });
  assert.equal((await request(handler)).statusCode,403);
  assert.equal((await request(handler,base.replace('147','146'))).statusCode,400);
  assert.equal(reads,0);
});

test('questions failure or forged human approval never implies resolution',async()=>{
  const handler=createFsRealReadHandler({
    authorize:async()=>true,
    readCore:async()=>observed,
    readQuestions:async()=>{throw Error('GLPI offline');},
    readTemporal:async()=>({...observed,state:'RESOLVED'}),
    readPolicy:async()=>({...observed,state:'APPROVED'})
  });
  const res=await request(handler);
  assert.equal(res.statusCode,200);
  assert.deepEqual(res.body.questions,[]);
  assert.equal(res.body.temporal.state,'UNKNOWN');
  assert.equal(res.body.policy.state,'UNKNOWN');
  assert.equal(res.body.approved,false);
  assert.equal(res.body.resolved,false);
});
