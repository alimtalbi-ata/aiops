import test from "node:test";
import assert from "node:assert/strict";
import {projectFsReal} from "./fs-real-readonly-projection.mjs";
const ctx={tenant:"lab",actor:"analyst"};
const core={glpi_ticket_id:"147",run_id:"RUN-147",mode:"LIVE",no_live_effects:true,status:"BLOCKED",evidence_ids:["E1"]};
const downstream={glpi_ticket_id:"147",run_id:"RUN-147",mode:"LIVE",status:"BLOCKED"};
const questions={glpi_ticket_id:"147",run_id:"RUN-147",mode:"LIVE",questions:[{id:"Q1",source:"GLPI",text:"Quel fichier conserver ?"},{id:"Q2",source:"Copilot",text:"Quelle dépendance ?"}]};
const adapters=(extra={})=>({authz:async()=>true,readCore:async()=>core,readTemporal:async()=>downstream,readPolicy:async()=>downstream,readQuestions:async()=>questions,...extra});
test("unauthorized: no backend reads",async()=>{
 let called=false;
 const r=await projectFsReal(adapters({authz:async()=>false,readCore:async()=>{called=true;return core}}),ctx,"incident");
 assert.equal(r.httpStatus,403);assert.equal(called,false);
});
test("incident: truthful correlated states, no questions or approval",async()=>{
 let called=false;
 const r=await projectFsReal(adapters({readQuestions:async()=>{called=true;return questions}}),ctx,"incident");
 assert.equal(r.body.core,"BLOCKED");assert.equal(r.body.temporal,"BLOCKED");
 assert.equal(r.body.policy,"BLOCKED");assert.equal(r.body.run_id,"RUN-147");
 assert.equal(r.body.approved,false);assert.equal(r.body.resolved,false);
 assert.equal(r.body.remediation_allowed,false);assert.equal(called,false);
});
test("insufficient: only bound human questions",async()=>{
 const r=await projectFsReal(adapters(),ctx,"insufficient");
 assert.deepEqual(r.body.questions.map(q=>q.source),["GLPI","Copilot"]);
 assert.equal(r.body.outcome,"BLOCKED");
});
for(const bad of [null,{...core,glpi_ticket_id:"146"},{...core,mode:"DEMO"},{...core,no_live_effects:false}]) {
 test("unbound core fails closed: "+JSON.stringify(bad),async()=>{
  let called=false;
  const r=await projectFsReal(adapters({readCore:async()=>bad,readQuestions:async()=>{called=true;return questions}}),ctx,"insufficient");
  assert.equal(r.body.core,"UNKNOWN");assert.equal(r.body.temporal,"UNKNOWN");
  assert.equal(r.body.policy,"UNKNOWN");assert.deepEqual(r.body.questions,[]);
  assert.equal(called,false);
 });
}
test("mismatched downstream run and questions fail closed",async()=>{
 const r=await projectFsReal(adapters({readPolicy:async()=>({...downstream,run_id:"RUN-146"}),readQuestions:async()=>({...questions,glpi_ticket_id:"146"})}),ctx,"insufficient");
 assert.equal(r.body.policy,"UNKNOWN");assert.deepEqual(r.body.questions,[]);
});
test("reader failures never imply success",async()=>{
 const r=await projectFsReal(adapters({readTemporal:async()=>{throw Error("offline")},readQuestions:async()=>{throw Error("offline")}}),ctx,"insufficient");
 assert.equal(r.body.temporal,"UNKNOWN");assert.deepEqual(r.body.questions,[]);
});
