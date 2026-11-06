import test from 'node:test';
import assert from 'node:assert/strict';
import {buildFsRealProjection as build} from './fs-real-server-projection.mjs';
const principal={actor:'lab-reader',tenant:'lab'};
const allow=async()=>true;
const base={mode:'lab147',ticketId:147,principal,authorize:allow};
const observed={glpi_ticket_id:147,synthetic:true,no_live_effects:true,state:'BLOCKED',
 incident_id:'INC-DEMO-FS-001',run_id:'RUN-4FABD1786F107E51',evidence_id:'EVD-D2069BA816126499'};
test('requires authenticated principal and explicit ACL',async()=>{
 await assert.rejects(build({...base,principal:null}),/FORBIDDEN/);
 await assert.rejects(build({...base,authorize:async()=>false,readCore:()=>{throw Error('must not read')}}),/FORBIDDEN/);
});
test('rejects wrong ticket and mode before service reads',async()=>{
 await assert.rejects(build({...base,ticketId:146}),/INVALID_REQUEST/);
 await assert.rejects(build({...base,mode:'live'}),/INVALID_REQUEST/);
});
test('returns observed scoped states but never approval or resolution',async()=>{
 const p=await build({...base,readCore:async()=>({...observed,approved:true,resolved:true}),
 readTemporal:async()=>({...observed,state:'WAITING_HUMAN'}),
 readPolicy:async()=>({...observed,state:'BLOCKED'})});
 assert.equal(p.run_id,observed.run_id);assert.equal(p.temporal.state,'WAITING_HUMAN');
 assert.equal(p.approved,false);assert.equal(p.resolved,false);
});
test('missing services fail closed to UNKNOWN',async()=>{
 const p=await build({...base,readCore:async()=>{throw Error('offline')},
 readPolicy:async()=>({...observed,glpi_ticket_id:146,state:'RUNNING'})});
 assert.equal(p.core.state,'UNKNOWN');assert.equal(p.policy.state,'UNKNOWN');
 assert.equal(p.run_id,undefined);
});
test('insufficient mode accepts only bounded human questions',async()=>{
 const p=await build({...base,mode:'insufficient',readQuestions:async()=>['Quelle rétention ?']});
 assert.deepEqual(p.questions,['Quelle rétention ?']);
 const invalid=await build({...base,mode:'insufficient',readQuestions:async()=>Array(13).fill('Q')});
 assert.deepEqual(invalid.questions,[]);
});
test('never calls questions reader for lab mode',async()=>{
 const p=await build({...base,readQuestions:()=>{throw Error('unexpected')}});
 assert.deepEqual(p.questions,[]);
});

test('never combines Temporal/Policy states from another run on ticket 147',async()=>{
 const p=await build({...base,
   readCore:async()=>observed,
   readTemporal:async()=>({...observed,run_id:'RUN-OTHER',state:'RUNNING'}),
   readPolicy:async()=>({...observed,run_id:'RUN-OTHER',state:'BLOCKED'})});
 assert.equal(p.core.state,'BLOCKED');
 assert.equal(p.temporal.state,'UNKNOWN');
 assert.equal(p.policy.state,'UNKNOWN');
 assert.equal(p.run_id,observed.run_id);
});
test('unlinked service states remain UNKNOWN even when ticket and synthetic match',async()=>{
 const p=await build({...base,
   readCore:async()=>({...observed,run_id:undefined}),
   readTemporal:async()=>({...observed,state:'RUNNING'}),
   readPolicy:async()=>({...observed,state:'BLOCKED'})});
 assert.equal(p.temporal.state,'UNKNOWN');
 assert.equal(p.policy.state,'UNKNOWN');
});

test('rejects matching run on untrusted Core ticket or mode markers',async()=>{
 for (const badCore of [
   {...observed,glpi_ticket_id:146},
   {...observed,synthetic:false},
   {...observed,no_live_effects:false},
   {...observed,run_id:'not-a-run'}
 ]) {
   const p=await build({...base,readCore:async()=>badCore,
     readTemporal:async()=>({...observed,run_id:badCore.run_id,state:'RUNNING'}),
     readPolicy:async()=>({...observed,run_id:badCore.run_id,state:'BLOCKED'})});
   assert.equal(p.temporal.state,'UNKNOWN');
   assert.equal(p.policy.state,'UNKNOWN');
 }
});


test('untrusted Core never supplies a displayed state or correlation IDs', async()=>{
 for (const bad of [
   {...observed,glpi_ticket_id:146,state:'RUNNING'},
   {...observed,synthetic:false,state:'RUNNING'},
   {...observed,no_live_effects:false,state:'RUNNING'}
 ]) {
   const p=await build({...base,readCore:async()=>bad,
     readTemporal:async()=>({...observed,state:'RUNNING'}),
     readPolicy:async()=>({...observed,state:'BLOCKED'})});
   assert.equal(p.core.state,'UNKNOWN');
   assert.equal(p.temporal.state,'UNKNOWN');
   assert.equal(p.policy.state,'UNKNOWN');
   assert.equal(p.run_id,undefined);
   assert.equal(p.approved,false);
   assert.equal(p.resolved,false);
 }
});

test('ACL must return literal true, not a truthy denial or error object',async()=>{
 for (const decision of [{allowed:false},{authorized:false},'true',1,[],{}]) {
   let reads=0;
   await assert.rejects(build({...base,authorize:async()=>decision,
     readCore:async()=>{reads++;return observed;}}),/FORBIDDEN/);
   assert.equal(reads,0,'no service read after ambiguous ACL decision');
 }
});

test('malformed principals fail closed before ACL and service reads',async()=>{
 for (const bad of [true,'reader',[],{}, {actor:'reader'}, {tenant:'lab'},
   {actor:' ',tenant:'lab'}, {actor:'reader',tenant:' '}]) {
   let authCalls=0, reads=0;
   await assert.rejects(build({...base,principal:bad,
     authorize:async()=>{authCalls++;return true;},
     readCore:async()=>{reads++;return observed;}}),/FORBIDDEN/);
   assert.equal(authCalls,0);
   assert.equal(reads,0);
 }
});
