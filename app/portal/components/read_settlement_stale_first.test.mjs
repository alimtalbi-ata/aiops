import test from 'node:test';
import assert from 'node:assert/strict';
import {projectReadSettlement as settle} from './read_settlement_guard.mjs';

const base = () => ({generation:2, activeGeneration:3, cancelled:false, timedOut:false});
test('stale generation skips hostile terminal accessors', () => {
  const input=base(); let invoked=0;
  Object.defineProperty(input,'cancelled',{get(){invoked++;throw Error('secret');}});
  Object.defineProperty(input,'timedOut',{get(){invoked++;throw Error('secret');}});
  assert.deepEqual(settle(input),{state:'UNKNOWN',reason:'STALE_RESPONSE',result:null});
  assert.equal(invoked,0);
});
test('stale generation ignores missing terminal fields', () => {
  assert.deepEqual(settle({generation:2,activeGeneration:3}),{state:'UNKNOWN',reason:'STALE_RESPONSE',result:null});
});
test('current generation rejects missing or hostile terminal fields', () => {
  assert.deepEqual(settle({generation:3,activeGeneration:3}),{state:'ERROR',error_code:'READ_FAILED',result:null});
  const x={generation:3,activeGeneration:3,timedOut:false};
  Object.defineProperty(x,'cancelled',{get(){throw Error('private');}});
  assert.deepEqual(settle(x),{state:'ERROR',error_code:'READ_FAILED',result:null});
});
test('generation validation still fails closed before stale decision', () => {
  assert.deepEqual(settle({generation:'2',activeGeneration:3}),{state:'ERROR',error_code:'READ_FAILED',result:null});
  assert.deepEqual(settle({generation:2,activeGeneration:-1}),{state:'ERROR',error_code:'READ_FAILED',result:null});
});
