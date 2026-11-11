import test from 'node:test';
import assert from 'node:assert/strict';
import {projectReadTransportFailure as project} from './read_transport_diagnostics.mjs';

const fail = {state:'ERROR',error_code:'READ_FAILED',result:null};
const unknown = reason => ({state:'UNKNOWN',reason,result:null});
function assertSafe(value, expected) {
  assert.deepEqual(value, expected);
  assert.equal(Object.isFrozen(value), true);
  assert.equal(value.result, null);
  assert.notEqual(value.state, 'READY');
}
test('inherited and symbol claims cannot override trusted own status', () => {
  const source = Object.create({status:403,aborted:true,timedOut:true,actor:'forged'});
  Object.defineProperty(source, Symbol.for('status'), {value:401});
  assertSafe(project(source), fail);
  Object.defineProperty(source,'status',{value:401,enumerable:true});
  assertSafe(project(source),unknown('AUTH_REQUIRED'));
});
test('only literal true abort/timeout flags count, not truthy objects or strings', () => {
  for (const flag of ['true',1,{},[],new Boolean(true)]) {
    assertSafe(project({status:503,aborted:flag,timedOut:flag}),fail);
  }
  assertSafe(project({status:503,aborted:false,timedOut:true}),unknown('TIMEOUT'));
  assertSafe(project({status:503,aborted:true,timedOut:true}),unknown('CANCELLED'));
});
test('non-own and accessor status cannot trigger authorization labels', () => {
  let invoked=0;
  const input={aborted:false,timedOut:false};
  Object.defineProperty(input,'status',{get(){invoked++;return 403;}});
  assertSafe(project(input),fail);
  assert.equal(invoked,0);
});
test('a throwing descriptor trap is contained and its message is not reflected', () => {
  const hostile=new Proxy({status:401},{getOwnPropertyDescriptor(){throw Error('Bearer private-token');}});
  const result=project(hostile);
  assertSafe(result,fail);
  assert.equal(JSON.stringify(result).includes('private-token'),false);
});
test('status is diagnostic only even when caller asserts READY and freshness', () => {
  for (const status of [200,204,304,401,403,404,429,500]) {
    const result=project({status,state:'READY',authorized:true,observed_at:'2099-01-01T00:00:00Z',tenant_id:'victim',result:{secret:'x'}});
    const expected=status===401?unknown('AUTH_REQUIRED'):status===403?unknown('TENANT_ACL_NOT_QUALIFIED'):status===404?unknown('NOT_FOUND'):status===429?{state:'ERROR',error_code:'RATE_LIMITED',result:null}:fail;
    assertSafe(result,expected);
    assert.equal(JSON.stringify(result).includes('victim'),false);
  }
});
