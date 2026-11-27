// Exercise the real CLI with synthetic on-disk reports, not a Docker runtime.
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const crypto = require("node:crypto");
const {spawnSync} = require("node:child_process");
const dir = fs.mkdtempSync(path.join(os.tmpdir(), "v3-receipt-cli-"));
const cli = path.join(__dirname, "verify-lab-install-receipts.cjs");
const source = "a".repeat(40);
const manifest = {classification:"V3_DISPOSABLE_LAB_KIT",source_sha:source,production_authorized:false,files:{}};
const raw = JSON.stringify(manifest) + "\n";
const digest = crypto.createHash("sha256").update(raw).digest("hex");
const services = ["postgres","core","twin","evidence","policy","temporal-postgres","temporal","worker","gamma"];
const volumes = ["postgres-data","temporal-data","gamma-audit"];
const run = n => "RUN-" + n.toString(16).toUpperCase().padStart(16,"0");
const id = n => n.toString(16).padStart(64,"0");
const manifestPath = path.join(dir,"manifest.json");
const reportPaths = [1,2,3].map(n=>path.join(dir,`install-${n}.json`));
function fixture(slot) {
  const project = `v3-lab-install-${slot}`;
  return {classification:"V3_PREPARED_CLEAN_LAB_INSTALL",result:"PASS",production_authorized:false,slot,project,
    source_sha:source,manifest_sha256:digest,elapsed_seconds:42,
    container_ids:Object.fromEntries(services.map((name,i)=>[name,id(slot*100+i)])),
    volumes:volumes.map(v=>`${project}_${v}`),db_delta:[1,2,2,1],
    boundary:{classification:"V3_TEMPORAL_BOUNDARY_RUNTIME",result:"PASS",production_authorized:false,
      core_status:"BLOCKED",business_stages_passed:0,activities_completed:2,history_events:12,
      run_id:run(slot*2),workflow_id:run(slot*2)},
    gamma:{classification:"V3_PINNED_GAMMA_HITL_RUNTIME",result:"PASS",production_authorized:false,run_id:run(slot*2+1),
      evidence:[{evidence_id:`EVD-${slot}-1`,payload_hash:id(slot*10+1)},{evidence_id:`EVD-${slot}-2`,payload_hash:id(slot*10+2)}],
      decisions:[{decision:"SIMULATE_ONLY",receipt_id:`D-${slot}-1`,receipt_sha256:id(slot*10+3)},
        {decision:"DENY",receipt_id:`D-${slot}-2`,receipt_sha256:id(slot*10+4)}]}};
}
function reset() {
  fs.writeFileSync(manifestPath,raw);
  reportPaths.forEach((p,i)=>fs.writeFileSync(p,JSON.stringify(fixture(i+1))));
}
const args = [source,manifestPath,...reportPaths];
let count=0;
function execute(name,expected,argv=args) {
  const p=spawnSync(process.execPath,[cli,...argv],{encoding:"utf8",timeout:5000});
  assert.ifError(p.error);
  assert.equal(p.signal,null,name);
  assert.equal(p.status,expected,`${name}: ${p.stderr}`);
  const out=JSON.parse(expected===0?p.stdout:p.stderr);
  assert.equal(out.result,expected===0?"PASS":"FAIL",name);
  if(expected!==0) { assert.equal(p.stdout,"",name); assert.equal(out.production_authorized,false); }
  count++;
  return out;
}
try {
  reset();
  const valid=execute("valid files",0);
  assert.deepEqual([valid.receipts,valid.container_ids,valid.volume_names,valid.run_ids],[3,27,9,6]);
  assert.equal(valid.manifest_sha256,digest);
  execute("missing argument",1,args.slice(0,-1));
  execute("incorrect expected source",1,["b".repeat(40),...args.slice(1)]);
  execute("reordered slots",1,[source,manifestPath,reportPaths[1],reportPaths[0],reportPaths[2]]);
  fs.appendFileSync(manifestPath," "); execute("changed manifest bytes",1); reset();
  fs.writeFileSync(manifestPath,JSON.stringify({...manifest,production_authorized:true})); execute("unsafe manifest",1); reset();
  fs.writeFileSync(reportPaths[1],"not-json"); execute("malformed report",1); reset();
  fs.unlinkSync(reportPaths[1]); execute("missing report",1); reset();
  fs.writeFileSync(reportPaths[1],JSON.stringify({...fixture(2),db_delta:[0,0,0,0]})); execute("incorrect DB delta",1); reset();
  const copyProofs = (field) => {
    const target=fixture(2);
    target.gamma[field]=fixture(1).gamma[field];
    fs.writeFileSync(reportPaths[1],JSON.stringify(target));
  };
  copyProofs("evidence"); execute("cross-slot copied Evidence",1); reset();
  copyProofs("decisions"); execute("cross-slot copied HITL",1); reset();
  const both=fixture(2); both.gamma.evidence=fixture(1).gamma.evidence; both.gamma.decisions=fixture(1).gamma.decisions;
  fs.writeFileSync(reportPaths[1],JSON.stringify(both)); execute("cross-slot copied proofs",1); reset();
  const single=fixture(2); single.gamma.evidence[0].evidence_id=fixture(1).gamma.evidence[0].evidence_id;
  fs.writeFileSync(reportPaths[1],JSON.stringify(single)); execute("cross-slot single Evidence ID",1); reset();
  const decision=fixture(2); decision.gamma.decisions[0].receipt_id=fixture(1).gamma.decisions[0].receipt_id;
  fs.writeFileSync(reportPaths[1],JSON.stringify(decision)); execute("cross-slot single HITL ID",1); reset();
  const repeatedHashes=fixture(2);
  repeatedHashes.gamma.evidence[0].payload_hash=fixture(1).gamma.evidence[0].payload_hash;
  repeatedHashes.gamma.decisions[0].receipt_sha256=fixture(1).gamma.decisions[0].receipt_sha256;
  fs.writeFileSync(reportPaths[1],JSON.stringify(repeatedHashes)); execute("equal hashes with distinct IDs",0); reset();
  console.log(JSON.stringify({classification:"V3_STATIC_LAB_RECEIPT_CLI_TEST",result:"PASS",cases:count,positive:2,negative:count-2,production_authorized:false}));
} finally { fs.rmSync(dir,{recursive:true,force:true}); }
