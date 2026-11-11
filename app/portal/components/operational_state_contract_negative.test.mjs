import test from 'node:test';
import assert from 'node:assert/strict';
import {createLatestReader} from './operational_state.mjs';

const observed_at='2026-11-11T02:39:00Z';
const now=()=>Date.parse('2026-11-11T02:40:00Z');
const qualified=()=>({scope_verified:true,authorization_source:'server',observed_at,records:[{id:'run-1'}]});

test('proxy descriptor trap failure is READ_FAILED without leaking tenant data',async()=>{
 const events=[];
 const response=new Proxy(qualified(),{
  getOwnPropertyDescriptor(_target,key){
   if(key==='records')throw new Error('tenant-secret: cross-tenant');
   return Reflect.getOwnPropertyDescriptor(_target,key);
  }
 });
 const reader=createLatestReader(async()=>response,e=>events.push(e),{now});
 await reader.load('runs');
 assert.deepEqual(events,[{state:'LOADING'},{state:'ERROR',error_code:'READ_FAILED',result:null}]);
 assert.equal(JSON.stringify(events).includes('tenant-secret'),false);
});

test('server provenance cannot be asserted by inherited or accessor-backed fields',async()=>{
 const events=[];
 const inherited=Object.assign(Object.create({authorization_source:'server'}),qualified());
 delete inherited.authorization_source;
 let called=0;
 const accessor=qualified();
 Object.defineProperty(accessor,'scope_verified',{get(){called++;return true}});
 const queue=[inherited,accessor];
 const reader=createLatestReader(async()=>queue.shift(),e=>events.push(e),{now});
 await reader.load('runs');
 await reader.load('runs');
 assert.equal(called,0);
 assert.deepEqual(events.filter(e=>e.state!=='LOADING'),[
  {state:'UNKNOWN',result:null},{state:'UNKNOWN',result:null}
 ]);
});

test('transport failure never becomes timeout by message and never reveals URL',async()=>{
 const events=[];
 const reader=createLatestReader(async()=>{throw Error('OPERATIONAL_TIMEOUT https://internal.invalid/?token=secret')},e=>events.push(e),{now,timeoutMs:100});
 await reader.load('evidence');
 assert.deepEqual(events.at(-1),{state:'ERROR',error_code:'READ_FAILED',result:null});
 assert.equal(JSON.stringify(events).includes('secret'),false);
});
