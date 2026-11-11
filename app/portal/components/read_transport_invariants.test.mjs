import test from 'node:test';
import assert from 'node:assert/strict';
import {projectReadTransportFailure as project} from './read_transport_diagnostics.mjs';

// A diagnostic is never an authorization, freshness or payload qualification.
const safe = output => {
  assert.equal(output.result, null);
  assert.notEqual(output.state, 'READY');
  assert.equal(Object.isFrozen(output), true);
  assert.deepEqual(Object.keys(output).sort(), output.state === 'ERROR'
    ? ['error_code', 'result', 'state'] : ['reason', 'result', 'state']);
};
test('every HTTP status (100..599) remains a sanitized, immutable non-READY diagnostic', () => {
  for (let status=100; status<=599; status++) {
    const output=project({status, payload:{token:'secret', tenant:'other'}, actor:'forged'});
    safe(output);
    assert.equal(JSON.stringify(output).includes('secret'), false);
    assert.equal(JSON.stringify(output).includes('other'), false);
    assert.equal(JSON.stringify(output).includes('forged'), false);
  }
});
test('malformed status and flags never authorize or reveal records', () => {
  for (const status of [NaN, Infinity, -Infinity, 99, 600, 200.5, '403', null, undefined, {}, []]) {
    const output=project({status, aborted:'true', timedOut:1, records:[{secret:'s'}]});
    assert.deepEqual(output,{state:'ERROR',error_code:'READ_FAILED',result:null});
    safe(output);
  }
});
test('hostile Proxy descriptors fail closed without propagating exceptions', () => {
  const hostile=new Proxy({}, {getOwnPropertyDescriptor(){throw Error('Bearer SECRET');}});
  const output=project(hostile);
  assert.deepEqual(output,{state:'ERROR',error_code:'READ_FAILED',result:null});
  safe(output);
});
test('untrusted provenance and freshness fields cannot promote a transport result', () => {
  const output=project({status:200, provenance:'trusted', observed_at:'2099-01-01T00:00:00Z',
    authorized:true, tenant_id:'other', state:'READY', result:{secret:'s'}});
  assert.deepEqual(output,{state:'ERROR',error_code:'READ_FAILED',result:null});
  safe(output);
});
