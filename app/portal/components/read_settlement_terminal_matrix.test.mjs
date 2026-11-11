import test from 'node:test';
import assert from 'node:assert/strict';
import {projectReadSettlement as settle} from './read_settlement_guard.mjs';

const stale={state:'UNKNOWN',reason:'STALE_RESPONSE',result:null};
const failed={state:'ERROR',error_code:'READ_FAILED',result:null};

test('superseded generation never evaluates hostile terminal accessors',()=>{
  let calls=0;
  const input={generation:1,activeGeneration:2};
  for(const name of ['cancelled','timedOut']){
    Object.defineProperty(input,name,{get(){calls++;throw Error('sensitive');}});
  }
  assert.deepEqual(settle(input),stale);
  assert.equal(calls,0);
});

test('superseded generation ignores hostile terminal Proxy descriptor traps',()=>{
  const input=new Proxy({generation:1,activeGeneration:2},{
    getOwnPropertyDescriptor(target,key){
      if(key==='cancelled'||key==='timedOut') throw Error('sensitive');
      return Reflect.getOwnPropertyDescriptor(target,key);
    }
  });
  assert.deepEqual(settle(input),stale);
});

test('current generation refuses terminal accessor without invoking it',()=>{
  let calls=0;
  const input={generation:3,activeGeneration:3,timedOut:false};
  Object.defineProperty(input,'cancelled',{get(){calls++;return true;}});
  assert.deepEqual(settle(input),failed);
  assert.equal(calls,0);
});

test('invalid current terminal flags never expose forged business payload',()=>{
  const result=settle({generation:4,activeGeneration:4,cancelled:1,timedOut:false,state:'READY',result:{secret:'not-for-client'}});
  assert.deepEqual(result,failed);
  assert.equal(Object.isFrozen(result),true);
  assert.equal(JSON.stringify(result).includes('secret'),false);
});
