import test from 'node:test';
import assert from 'node:assert/strict';
import {projectReadSettlement as settle} from './read_settlement_guard.mjs';
const event=(overrides={})=>({generation:4,activeGeneration:4,cancelled:false,timedOut:false,...overrides});
test('late response cannot promote a previous generation',()=>{
  const value=settle(event({generation:3,state:'READY',records:[{secret:'private'}]}));
  assert.deepEqual(value,{state:'UNKNOWN',reason:'STALE_RESPONSE',result:null});
  assert.equal(Object.isFrozen(value),true);
});
test('terminal precedence on current generation: cancellation before timeout',()=>{
  assert.deepEqual(settle(event({cancelled:true,timedOut:true})),{state:'UNKNOWN',reason:'CANCELLED',result:null});
  assert.deepEqual(settle(event({timedOut:true})),{state:'UNKNOWN',reason:'TIMEOUT',result:null});
});
test('successful read never qualified by settlement helper',()=>{
  assert.deepEqual(settle(event({status:200,authorized:true,provenance:'trusted',freshness:'fresh'})),{state:'UNKNOWN',reason:'NOT_QUALIFIED',result:null});
});
test('malformed, inherited, accessor and proxy values fail closed',()=>{
  for(const x of [event({generation:'4'}),event({activeGeneration:NaN}),event({cancelled:1}),Object.create(event()),null,new Proxy(event(),{getOwnPropertyDescriptor(){throw Error('secret')}})]){
    assert.deepEqual(settle(x),{state:'ERROR',error_code:'READ_FAILED',result:null});
  }
  let invoked=0;
  const x=event();
  Object.defineProperty(x,'generation',{get(){invoked++;return 4;}});
  assert.deepEqual(settle(x),{state:'ERROR',error_code:'READ_FAILED',result:null});
  assert.equal(invoked,0);
});
