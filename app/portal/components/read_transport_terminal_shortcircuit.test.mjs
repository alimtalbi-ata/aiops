import test from 'node:test';
import assert from 'node:assert/strict';
import {projectReadTransportFailure as project} from './read_transport_diagnostics.mjs';

test('trusted abort and timeout do not inspect hostile HTTP status', () => {
  for (const flags of [{aborted:true,timedOut:false,reason:'CANCELLED'}, {aborted:false,timedOut:true,reason:'TIMEOUT'}, {aborted:true,timedOut:true,reason:'CANCELLED'}]) {
    let calls=0;
    const input={aborted:flags.aborted,timedOut:flags.timedOut};
    Object.defineProperty(input,'status',{get(){calls++;throw Error('secret');}});
    const output=project(input);
    assert.deepEqual(output,{state:'UNKNOWN',reason:flags.reason,result:null});
    assert.equal(Object.isFrozen(output),true);
    assert.equal(calls,0);
  }
});
test('terminal signal skips throwing status descriptor trap', () => {
  let statusTraps=0;
  const input=new Proxy({aborted:true,timedOut:false}, {
    getOwnPropertyDescriptor(target,key) {
      if(key==='status'){statusTraps++;throw Error('secret');}
      return Reflect.getOwnPropertyDescriptor(target,key);
    }
  });
  assert.deepEqual(project(input),{state:'UNKNOWN',reason:'CANCELLED',result:null});
  assert.equal(statusTraps,0);
});
test('without terminal signal, hostile status remains fail closed', () => {
  const input={aborted:false,timedOut:false};
  Object.defineProperty(input,'status',{get(){throw Error('secret');}});
  const output=project(input);
  assert.deepEqual(output,{state:'ERROR',error_code:'READ_FAILED',result:null});
  assert.equal(JSON.stringify(output).includes('secret'),false);
});
test('hostile terminal flag still fails closed rather than bypassing validation', () => {
  const input={timedOut:true,status:403};
  Object.defineProperty(input,'aborted',{get(){throw Error('secret');}});
  assert.deepEqual(project(input),{state:'ERROR',error_code:'READ_FAILED',result:null});
});
