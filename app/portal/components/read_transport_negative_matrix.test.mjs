import test from 'node:test';
import assert from 'node:assert/strict';
import {projectReadTransportFailure as project} from './read_transport_diagnostics.mjs';

// Read-only boundary: status must be supplied by a trusted Response adapter.
// These tests cannot qualify the source of that status or actor/tenant ACL.
test('401, 403, 404 and 429 produce explicit sanitized non-READY results',()=>{
  const expected=new Map([
    [401,{state:'UNKNOWN',reason:'AUTH_REQUIRED',result:null}],
    [403,{state:'UNKNOWN',reason:'TENANT_ACL_NOT_QUALIFIED',result:null}],
    [404,{state:'UNKNOWN',reason:'NOT_FOUND',result:null}],
    [429,{state:'ERROR',error_code:'RATE_LIMITED',result:null}]
  ]);
  for(const [status,output] of expected) assert.deepEqual(project({status}),output);
});
test('transport errors cannot self-declare timeout via message or payload',()=>{
  for(const status of [0,408,499,500,502,503,504,599]){
    const output=project({status,error:{message:'TIMEOUT',tenant:'secret'},payload:{timedOut:true}});
    assert.deepEqual(output,{state:'ERROR',error_code:'READ_FAILED',result:null});
    assert.equal(JSON.stringify(output).includes('secret'),false);
  }
});
test('inherited cancellation, timeout and status never qualify the read',()=>{
  const input=Object.create({status:403,aborted:true,timedOut:true});
  assert.deepEqual(project(input),{state:'ERROR',error_code:'READ_FAILED',result:null});
});
test('nonboolean timeout flags never become TIMEOUT',()=>{
  for(const flag of [null,0,1,'true',[],{},new Boolean(true)]){
    assert.deepEqual(project({status:500,timedOut:flag}),{state:'ERROR',error_code:'READ_FAILED',result:null});
  }
});
test('hostile status descriptor fails closed without disclosing exception',()=>{
  let called=0;
  const input={};
  Object.defineProperty(input,'status',{get(){called++;throw Error('Bearer secret');}});
  const output=project(input);
  assert.deepEqual(output,{state:'ERROR',error_code:'READ_FAILED',result:null});
  assert.equal(called,0);
});
test('trusted cancellation dominates timeout but never returns READY',()=>{
  assert.deepEqual(project({status:500,aborted:true,timedOut:true}),{state:'UNKNOWN',reason:'CANCELLED',result:null});
  assert.deepEqual(project({status:500,timedOut:true}),{state:'UNKNOWN',reason:'TIMEOUT',result:null});
});
