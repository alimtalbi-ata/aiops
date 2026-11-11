import test from 'node:test';
import assert from 'node:assert/strict';
import {projectQualifiedRecords} from './qualified_record_projection.mjs';
import {createLatestReader} from './operational_state.mjs';
const observed_at='2026-11-11T03:39:00Z';
const now=Date.parse('2026-11-11T03:40:00Z');
const qualified=records=>({records,observed_at,scope_verified:true,authorization_source:'server'});
test('allowlist removes per-record tokens and nested transport diagnostics',async()=>{
 const source=qualified([{id:'run-1',status:'OPEN',token:'secret-canary',headers:{authorization:'secret-canary'}}]);
 const pre=projectQualifiedRecords(source,['id','status']);
 assert.equal(pre.state,'UNVERIFIED_FRESHNESS');
 assert.equal(JSON.stringify(pre).includes('secret-canary'),false);
 const events=[];
 const reader=createLatestReader(async()=>pre.result,x=>events.push(x),{now:()=>now});
 await reader.load('runs');
 assert.equal(events.at(-1).state,'READY');
 assert.equal(JSON.stringify(events).includes('secret-canary'),false);
 assert.deepEqual({...events.at(-1).result.records[0]},{id:'run-1',status:'OPEN'});
});
test('server qualification and record fields must be own data properties',()=>{
 const inherited=Object.create({scope_verified:true,authorization_source:'server'});
 Object.assign(inherited,{records:[{id:'a'}],observed_at});
 assert.deepEqual(projectQualifiedRecords(inherited,['id']),{state:'UNKNOWN',result:null});
 const getter={};Object.defineProperty(getter,'id',{get(){throw Error('getter executed')}});
 assert.deepEqual(projectQualifiedRecords(qualified([getter]),['id']),{state:'UNKNOWN',result:null});
 const nested=qualified([{id:{secret:'nested'}}]);
 assert.deepEqual(projectQualifiedRecords(nested,['id']),{state:'UNKNOWN',result:null});
});
test('proxy descriptor exceptions, missing fields and bad allowlists fail closed',()=>{
 const proxy=new Proxy({id:'a'},{getOwnPropertyDescriptor(){throw Error('secret-canary')}});
 for(const records of [[proxy],[{id:'a'}]]) {
  const fields=records[0]===proxy?['id']:['id','status'];
  assert.deepEqual(projectQualifiedRecords(qualified(records),fields),{state:'UNKNOWN',result:null});
 }
 for(const fields of [[],['__proto__'],['id','id'],['id',1]])
  assert.deepEqual(projectQualifiedRecords(qualified([{id:'a'}]),fields),{state:'UNKNOWN',result:null});
});
test('no client-side tenant assertion can qualify records',()=>{
 const e=qualified([{id:'a'}]);e.authorization_source='browser';e.tenant_id='tenant-a';
 assert.deepEqual(projectQualifiedRecords(e,['id']),{state:'UNKNOWN',result:null});
});

test('record array accessor is never invoked and fails closed',()=>{
 let calls=0;
 const records=[{id:'safe'}];
 Object.defineProperty(records,'0',{configurable:true,get(){calls++;return {id:'leak'};}});
 assert.deepEqual(projectQualifiedRecords(qualified(records),['id']),{state:'UNKNOWN',result:null});
 assert.equal(calls,0);
});
test('allowlist array accessor is never invoked and fails closed',()=>{
 let calls=0;
 const fields=['id'];
 Object.defineProperty(fields,'0',{configurable:true,get(){calls++;return 'id';}});
 assert.deepEqual(projectQualifiedRecords(qualified([{id:'safe'}]),fields),{state:'UNKNOWN',result:null});
 assert.equal(calls,0);
});
test('sparse record and allowlist arrays fail closed',()=>{
 const sparseRecords=new Array(1);
 const sparseFields=new Array(1);
 assert.deepEqual(projectQualifiedRecords(qualified(sparseRecords),['id']),{state:'UNKNOWN',result:null});
 assert.deepEqual(projectQualifiedRecords(qualified([{id:'safe'}]),sparseFields),{state:'UNKNOWN',result:null});
});
