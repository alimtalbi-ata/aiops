import test from 'node:test';
import assert from 'node:assert/strict';
import {projectReadTransportFailure as project} from './read_transport_diagnostics.mjs';

test('401/403 cannot become READY or expose tenant data',()=>{
 for(const [status,reason] of [[401,'AUTH_REQUIRED'],[403,'TENANT_ACL_NOT_QUALIFIED']]){
  assert.deepEqual(project({status}),{state:'UNKNOWN',reason,result:null});
 }
});
test('timeouts and cancellation stay UNKNOWN and never publish payload',()=>{
 assert.deepEqual(project({status:200,timedOut:true}),{state:'UNKNOWN',reason:'TIMEOUT',result:null});
 assert.deepEqual(project({status:200,aborted:true}),{state:'UNKNOWN',reason:'CANCELLED',result:null});
});
test('transport errors are bounded, sanitized and not inferred from exception messages',()=>{
 for(const status of [null,NaN,0,600,'403',{},-1,200.5]){
  assert.deepEqual(project({status}),{state:'ERROR',error_code:'READ_FAILED',result:null});
 }
 assert.deepEqual(project({status:429}),{state:'ERROR',error_code:'RATE_LIMITED',result:null});
 assert.deepEqual(project({status:503}),{state:'ERROR',error_code:'READ_FAILED',result:null});
 assert.deepEqual(project({status:404}),{state:'UNKNOWN',reason:'NOT_FOUND',result:null});
});
test('projection is immutable and does not return browser-provided actor or secret fields',()=>{
 const value=project({status:403,actor:'other-tenant',token:'Bearer secret',records:['secret']});
 assert.equal(Object.isFrozen(value),true);
 assert.equal(JSON.stringify(value).includes('secret'),false);
 assert.equal(JSON.stringify(value).includes('other-tenant'),false);
});

test('accessors never execute, even for cancellation and status',()=>{
 for (const key of ['status','aborted','timedOut']) {
  let calls=0;
  const input={status:403};
  Object.defineProperty(input,key,{enumerable:true,get(){calls++;throw new Error('secret');}});
  assert.deepEqual(project(input),{state:'ERROR',error_code:'READ_FAILED',result:null});
  assert.equal(calls,0);
 }
});
test('inherited authorization-like status and flags are ignored',()=>{
 const input=Object.create({status:403,aborted:true,timedOut:true});
 assert.deepEqual(project(input),{state:'ERROR',error_code:'READ_FAILED',result:null});
});
test('hostile Proxy descriptors fail closed without exposing exceptions',()=>{
 const input=new Proxy({status:403},{getOwnPropertyDescriptor(){throw new Error('Bearer secret');}});
 assert.deepEqual(project(input),{state:'ERROR',error_code:'READ_FAILED',result:null});
});
test('own data descriptors preserve cancellation precedence and 403',()=>{
 assert.deepEqual(project({status:403}),{state:'UNKNOWN',reason:'TENANT_ACL_NOT_QUALIFIED',result:null});
 assert.deepEqual(project({status:403,aborted:true,timedOut:true}),{state:'UNKNOWN',reason:'CANCELLED',result:null});
});
