import test from 'node:test';
import assert from 'node:assert/strict';
import {buildFsRealProjection} from './fs-real-server-projection.mjs';

const principal={actor:'reader',tenant:'lab'};
const trusted={glpi_ticket_id:147,synthetic:true,no_live_effects:true,state:'BLOCKED',run_id:'RUN-LAB147'};
const base={mode:'insufficient',ticketId:147,principal,authorize:async()=>true};

for (const [label,core] of [
  ['missing Core',null],
  ['ticket 146', {...trusted,glpi_ticket_id:146}],
  ['LIVE mismatch', {...trusted,synthetic:false}],
  ['missing no-live guarantee', {...trusted,no_live_effects:false}]
]) {
  test('does not invoke human question reader on '+label,async()=>{
    let reads=0;
    const projection=await buildFsRealProjection({...base,readCore:async()=>core,
      readQuestions:async()=>{reads++;return ['Secret question'];}});
    assert.equal(reads,0);
    assert.deepEqual(projection.questions,[]);
    assert.equal(projection.approved,false);
    assert.equal(projection.resolved,false);
  });
}

test('reads human questions only after Core confirms GLPI 147',async()=>{
  const order=[];
  const projection=await buildFsRealProjection({...base,
    readCore:async()=>{order.push('core');return trusted;},
    readQuestions:async({principal:who,ticketId,mode})=>{
      order.push('questions');
      assert.equal(who,principal);
      assert.equal(ticketId,147);
      assert.equal(mode,'insufficient');
      return ['Quelle preuve manque ?'];
    }});
  assert.deepEqual(order,['core','questions']);
  assert.deepEqual(projection.questions,['Quelle preuve manque ?']);
  assert.equal(projection.approved,false);
  assert.equal(projection.resolved,false);
});

test('lab button never invokes human question reader',async()=>{
  let reads=0;
  const projection=await buildFsRealProjection({...base,mode:'lab147',
    readCore:async()=>trusted,
    readQuestions:async()=>{reads++;return ['Not for lab'];}});
  assert.equal(reads,0);
  assert.deepEqual(projection.questions,[]);
});
