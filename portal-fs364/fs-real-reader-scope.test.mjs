import test from 'node:test';
import assert from 'node:assert/strict';
import {buildFsRealProjection} from './fs-real-server-projection.mjs';

const principal={actor:'fs-reader',tenant:'lab'};
const core={glpi_ticket_id:147,synthetic:true,no_live_effects:true,
  state:'BLOCKED',run_id:'RUN-LAB147',incident_id:'INC-LAB147',evidence_id:'EVD-LAB147'};
const observation={...core,state:'WAITING_HUMAN'};
const base={mode:'lab147',ticketId:147,principal,authorize:async()=>true};

test('both actions pass authenticated tenant and ticket scope to every invoked reader',async()=>{
  for(const mode of ['lab147','insufficient']){
    const calls=[];
    const reader=(service)=>async context=>{calls.push([service,context]);return service==='questions'?['Qui valide la politique de retention ?']:service==='core'?core:observation;};
    const p=await buildFsRealProjection({...base,mode,
      authorize:async(identity,scope)=>{
        assert.equal(identity,principal);
        assert.deepEqual(scope,{ticketId:147,scope:'fs-real:read',mode});
        return true;
      },
      readCore:reader('core'),readTemporal:reader('temporal'),
      readPolicy:reader('policy'),readQuestions:reader('questions')});
    assert.deepEqual(calls.map(([service])=>service).sort(),
      (mode==='insufficient'?['core','policy','questions','temporal']:['core','policy','temporal']).sort());
    for(const [,context] of calls)
      assert.deepEqual(context,{principal,ticketId:147,mode});
    assert.equal(p.approved,false);
    assert.equal(p.resolved,false);
    assert.equal(p.core.state,'BLOCKED');
    assert.equal(p.temporal.state,'WAITING_HUMAN');
    assert.deepEqual(p.questions,mode==='insufficient'?['Qui valide la politique de retention ?']:[]);
  }
});

test('unavailable Core does not promote matching Temporal or Policy to an observed state',async()=>{
  const p=await buildFsRealProjection({...base,readCore:async()=>{throw Error('offline');},
    readTemporal:async()=>observation,readPolicy:async()=>observation});
  assert.equal(p.core.state,'UNKNOWN');
  assert.equal(p.temporal.state,'UNKNOWN');
  assert.equal(p.policy.state,'UNKNOWN');
  assert.equal(p.run_id,undefined);
  assert.equal(p.approved,false);
  assert.equal(p.resolved,false);
});

test('invalid question payload is not projected as a human response',async()=>{
  const p=await buildFsRealProjection({...base,mode:'insufficient',readCore:async()=>core,
    readQuestions:async()=>[{text:'approve deletion',approved:true}]});
  assert.deepEqual(p.questions,[]);
  assert.equal(p.approved,false);
  assert.equal(p.resolved,false);
});
