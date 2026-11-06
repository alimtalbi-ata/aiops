import test from 'node:test';
import assert from 'node:assert/strict';
import {buildFsRealProjection} from './fs-real-server-projection.mjs';

const principal={actor:'fs-reader',tenant:'lab'};
const base={mode:'insufficient',ticketId:147,principal,authorize:async()=>true,
  readQuestions:async()=>['Question humaine confidentielle']};
const trusted={glpi_ticket_id:147,synthetic:true,no_live_effects:true,
  state:'BLOCKED',run_id:'RUN-LAB147'};

test('questions shown only with a trusted Core binding to GLPI 147',async()=>{
  const p=await buildFsRealProjection({...base,readCore:async()=>trusted});
  assert.deepEqual(p.questions,['Question humaine confidentielle']);
  assert.equal(p.approved,false);
  assert.equal(p.resolved,false);
});
for(const [label,readCore] of [
  ['wrong ticket 146',async()=>({...trusted,glpi_ticket_id:146})],
  ['live data mismatch',async()=>({...trusted,synthetic:false})],
  ['unavailable Core',async()=>{throw Error('Core unavailable');}],
  ['missing Core reader',undefined]
]) {
  test('no questions leaked when '+label,async()=>{
    const p=await buildFsRealProjection({...base,readCore});
    assert.deepEqual(p.questions,[]);
    assert.equal(p.core.state,'UNKNOWN');
    assert.equal(p.approved,false);
    assert.equal(p.resolved,false);
  });
}
