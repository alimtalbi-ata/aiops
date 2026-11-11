import test from 'node:test';
import assert from 'node:assert/strict';
import {projectReadTransportFailure as project} from './read_transport_diagnostics.mjs';

// Contract-only negative suite. The transport input is NOT an authorization proof.
test('HTTP success and redirects never qualify data or produce READY',()=>{
  for(const status of [100,101,200,201,204,206,301,302,304,307,308]){
    assert.deepEqual(project({status}),{state:'ERROR',error_code:'READ_FAILED',result:null});
  }
});
test('forged truthy cancellation and timeout flags are ignored',()=>{
  for(const flag of ['true',1,{},[],new Boolean(true)]){
    assert.deepEqual(project({status:403,aborted:flag}),{state:'UNKNOWN',reason:'TENANT_ACL_NOT_QUALIFIED',result:null});
    assert.deepEqual(project({status:403,timedOut:flag}),{state:'UNKNOWN',reason:'TENANT_ACL_NOT_QUALIFIED',result:null});
  }
});
test('invalid own status cannot be replaced by inherited or payload status',()=>{
  const input=Object.assign(Object.create({status:403}),{status:'403',payload:{status:403,tenant:'victim'}});
  assert.deepEqual(project(input),{state:'ERROR',error_code:'READ_FAILED',result:null});
});
test('hostile own descriptors never invoke payload getters',()=>{
  let calls=0;
  const input={status:403};
  Object.defineProperty(input,'payload',{get(){calls++;throw Error('secret');}});
  assert.deepEqual(project(input),{state:'UNKNOWN',reason:'TENANT_ACL_NOT_QUALIFIED',result:null});
  assert.equal(calls,0);
});
test('hostile descriptor trap on flags cannot be converted to timeout',()=>{
  const input=new Proxy({status:403,timedOut:true},{getOwnPropertyDescriptor(target,key){
    if(key==='timedOut') throw Error('TIMEOUT Bearer secret');
    return Reflect.getOwnPropertyDescriptor(target,key);
  }});
  assert.deepEqual(project(input),{state:'ERROR',error_code:'READ_FAILED',result:null});
});
