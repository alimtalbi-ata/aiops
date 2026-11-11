import test from 'node:test';
import assert from 'node:assert/strict';
import {projectReadTransportFailure as project} from './read_transport_diagnostics.mjs';

// A transport diagnostic is never a read-model success projector.
test('all successful and redirect HTTP statuses fail closed without READY', () => {
  for (let status = 200; status <= 399; status++) {
    const result = project({status, records:[{secret:'tenant-private'}], state:'READY'});
    assert.deepEqual(result, {state:'ERROR', error_code:'READ_FAILED', result:null});
    assert.equal(Object.isFrozen(result), true);
  }
});

test('status cannot be synthesized from prototype, accessors or response payload', () => {
  let invoked=0;
  const inherited=Object.create({status:403});
  Object.defineProperty(inherited,'status',{get(){invoked++;return 403;}, configurable:true});
  assert.deepEqual(project(inherited), {state:'ERROR',error_code:'READ_FAILED',result:null});
  assert.equal(invoked,0);
  assert.deepEqual(project({response:{status:403}, body:{status:403}}), {state:'ERROR',error_code:'READ_FAILED',result:null});
});

test('trusted terminal flags bypass hostile HTTP status but never payload qualification', () => {
  let statusAccess=0;
  const input={aborted:false,timedOut:true,tenant:'forged',freshness:'fresh',state:'READY'};
  Object.defineProperty(input,'status',{get(){statusAccess++;throw Error('secret');}});
  const result=project(input);
  assert.deepEqual(result,{state:'UNKNOWN',reason:'TIMEOUT',result:null});
  assert.equal(statusAccess,0);
  assert.equal(Object.isFrozen(result),true);
});
