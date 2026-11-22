const test = require("node:test");
const assert = require("node:assert/strict");
const {selectableRunId,mountRunSelection} = require("../app/portal/portal_usability.js");
test("only exact Core Run syntax, no synthetic labels or URL injection",()=>{
  for(const id of ["SIM-ACME-ABC","RUN-a","RUN-../x","RUN-aa?token=x","RUN-aa\n",null]) assert.equal(selectableRunId(id),false);
  assert.equal(selectableRunId("RUN-abc_123"),true);
});
test("selection prepares input without navigation or auth",()=>{
  const cell={textContent:"RUN-abc",querySelector(){return this.button},appendChild(b){this.button=b}};
  const row={cells:[cell,{},{},{},{}],hidden:false};
  const rows={rows:[row],contains(r){return this.rows.includes(r)}};
  const input={value:"",addEventListener(){},focus(){this.focused=true}};
  const status={textContent:""};
  const doc={getElementById:id=>({"portal-runs":rows,"run-detail-id":input,"run-selection-status":status}[id]),createElement(){return {setAttribute(){},addEventListener(k,f){this.click=f}}}};
  assert.equal(mountRunSelection(doc),true);
  cell.button.click(); assert.equal(input.value,"RUN-abc");assert.equal(input.focused,true);
  assert.match(status.textContent,/ACL/);
  row.hidden=true;input.value="";cell.button.click();assert.equal(input.value,"");
});
