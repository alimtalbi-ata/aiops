import test from 'node:test';
import assert from 'node:assert/strict';
import {createEvidenceRequestGate} from './evidence_request_gate.mjs';

test('synthetic FS1113 out-of-order completion cannot publish stale results',async()=>{
  const gate=createEvidenceRequestGate();
  let finishOld,finishNew;
  const old=new Promise(resolve=>{finishOld=resolve;});
  const newer=new Promise(resolve=>{finishNew=resolve;});
  const published=[];
  const a=gate.issue();
  const oldTask=old.then(value=>{if(gate.isCurrent(a))published.push(value);});
  const b=gate.issue();
  const newTask=newer.then(value=>{if(gate.isCurrent(b))published.push(value);});
  finishNew('SYNTHETIC_NEW');await newTask;
  finishOld('SYNTHETIC_STALE');await oldTask;
  assert.deepEqual(published,['SYNTHETIC_NEW']);
});

test('synthetic errors from superseded requests cannot replace current state',()=>{
  const gate=createEvidenceRequestGate();
  const stale=gate.issue();
  const current=gate.issue();
  assert.equal(gate.isCurrent(stale),false);
  assert.equal(gate.isCurrent(current),true);
  gate.invalidate();
  assert.equal(gate.isCurrent(current),false);
});

test('synthetic unmount and malformed tokens fail closed',()=>{
  const gate=createEvidenceRequestGate();
  const token=gate.issue();
  for(const invalid of [null,undefined,0,-1,NaN,Infinity,'1',{},1.5])
    assert.equal(gate.isCurrent(invalid),false);
  gate.dispose();
  assert.equal(gate.isCurrent(token),false);
  assert.equal(gate.issue(),null);
  assert.equal(gate.isCurrent(null),false);
});
