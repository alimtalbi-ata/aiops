/** Cross-component read-only contract smoke: no backend, network or credentials. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {createLatestReader} from '../app/portal/components/operational_state.mjs';
import {filterEvidence} from '../app/portal/components/evidence_filter.mjs';
const now=Date.parse('2026-11-10T22:00:00Z');
const fresh='2026-11-10T21:59:00Z';
const scoped=records=>({records,observed_at:fresh,scope_verified:true,authorization_source:'server'});
test('only fresh server-qualified evidence may be filtered as READY',async()=>{
 const events=[];
 const reader=createLatestReader(async()=>scoped([{id:'e1',label:'Proof',status:'READY'}]),x=>events.push(x),{now:()=>now});
 await reader.load('incident');
 assert.equal(events.at(-1).state,'READY');
 assert.equal(filterEvidence(events.at(-1).result.records).state,'READY');
});
test('conflicting evidence identities never yield READY',async()=>{
 const events=[];
 const records=[{id:'e1',label:'A',status:'READY'},{id:'e1',label:'B',status:'ERROR'}];
 const reader=createLatestReader(async()=>scoped(records),x=>events.push(x),{now:()=>now});
 await reader.load('incident');
 assert.deepEqual(filterEvidence(events.at(-1).result.records),{state:'UNKNOWN',records:[]});
});
test('unscoped or stale responses never reach evidence filter',async()=>{
 for(const envelope of [{...scoped([{id:'x',label:'Secret',status:'READY'}]),scope_verified:false},{...scoped([{id:'x',label:'Old',status:'READY'}]),observed_at:'2026-11-10T21:00:00Z'}]){
  const events=[];
  await createLatestReader(async()=>envelope,x=>events.push(x),{now:()=>now}).load('incident');
  assert.deepEqual(events.at(-1),{state:'UNKNOWN',result:null});
 }
});
test('transport spoofed timeout cannot masquerade as UNKNOWN or leak details',async()=>{
 const events=[];
 await createLatestReader(async()=>{throw {message:'OPERATIONAL_TIMEOUT',token:'sensitive'}},x=>events.push(x),{now:()=>now}).load('incident');
 assert.deepEqual(events.at(-1),{state:'ERROR',error_code:'READ_FAILED',result:null});
 assert.equal(JSON.stringify(events).includes('sensitive'),false);
});
