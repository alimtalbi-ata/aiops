import test from 'node:test';
import assert from 'node:assert/strict';
import {buildFsRealProjection} from './fs-real-server-projection.mjs';

const core = {glpi_ticket_id:147,synthetic:true,no_live_effects:true,
  state:'BLOCKED',run_id:'RUN-LAB147',incident_id:'INC-LAB147',evidence_id:'EVD-LAB147'};
const scoped = {authorize:async()=>true,principal:{actor:'reader',tenant:'lab'},
  mode:'lab147',ticketId:147,readCore:async()=>core};
const observation = {glpi_ticket_id:147,synthetic:true,no_live_effects:true,
  state:'WAITING_HUMAN',run_id:'RUN-LAB147'};

test('matching run and incident/evidence may be projected',async()=>{
  const p=await buildFsRealProjection({...scoped,
    readTemporal:async()=>({...observation,incident_id:core.incident_id,evidence_id:core.evidence_id})});
  assert.equal(p.temporal.state,'WAITING_HUMAN');
});
for (const [field,value] of [['incident_id','INC-OTHER'],['evidence_id','EVD-OTHER'],
  ['incident_id',''],['evidence_id',123]]) {
  test('reject Temporal/Policy contradictory '+field+' '+JSON.stringify(value),async()=>{
    const bad={...observation,[field]:value};
    const p=await buildFsRealProjection({...scoped,readTemporal:async()=>bad,readPolicy:async()=>bad});
    assert.equal(p.core.state,'BLOCKED');
    assert.equal(p.temporal.state,'UNKNOWN');
    assert.equal(p.policy.state,'UNKNOWN');
    assert.equal(p.approved,false);
    assert.equal(p.resolved,false);
  });
}
test('reject extra correlation when Core lacks the corresponding identifier',async()=>{
  const p=await buildFsRealProjection({...scoped,readCore:async()=>({...core,incident_id:undefined}),
    readTemporal:async()=>({...observation,incident_id:'INC-LAB147'})});
  assert.equal(p.temporal.state,'UNKNOWN');
});
