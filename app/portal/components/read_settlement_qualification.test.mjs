import test from 'node:test';
import assert from 'node:assert/strict';
import {projectReadSettlement as settle} from './read_settlement_guard.mjs';

const fail = {state:'ERROR',error_code:'READ_FAILED',result:null};
const stale = {state:'UNKNOWN',reason:'STALE_RESPONSE',result:null};

test('inherited generations cannot qualify a response', () => {
  const input=Object.create({generation:1,activeGeneration:2});
  input.cancelled=false; input.timedOut=false;
  assert.deepEqual(settle(input),fail);
});
test('generation accessors are not executed', () => {
  let invoked=0;
  const input={activeGeneration:2,cancelled:false,timedOut:false};
  Object.defineProperty(input,'generation',{get(){invoked++;throw Error('sensitive');}});
  assert.deepEqual(settle(input),fail);
  assert.equal(invoked,0);
});
test('generation descriptor Proxy failure is sanitized', () => {
  const input=new Proxy({}, {getOwnPropertyDescriptor(){throw Error('secret transport');}});
  assert.deepEqual(settle(input),fail);
  assert.equal(JSON.stringify(settle(input)).includes('secret'),false);
});
test('malformed terminal signal fails closed even if cancellation is true', () => {
  assert.deepEqual(settle({generation:4,activeGeneration:4,cancelled:true,timedOut:'false'}),fail);
  assert.deepEqual(settle({generation:4,activeGeneration:4,cancelled:'true',timedOut:true}),fail);
});
test('stale response cannot be promoted by forged readiness or payload', () => {
  const input={generation:1,activeGeneration:2,ready:true,state:'READY',result:{secret:'x'}};
  const result=settle(input);
  assert.deepEqual(result,stale);
  assert.equal(Object.isFrozen(result),true);
  assert.equal(Object.hasOwn(result,'result'),true);
  assert.equal(result.result,null);
});
test('current response without terminal signals stays unqualified', () => {
  const result=settle({generation:7,activeGeneration:7,cancelled:false,timedOut:false,status:200,ready:true});
  assert.deepEqual(result,{state:'UNKNOWN',reason:'NOT_QUALIFIED',result:null});
  assert.equal(Object.isFrozen(result),true);
});
