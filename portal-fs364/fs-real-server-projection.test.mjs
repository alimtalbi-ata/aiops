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
