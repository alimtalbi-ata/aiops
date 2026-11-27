// Independent static QA of prepared LAB receipts. No Docker or network access.
"use strict";
function verify(rows, source, manifest) {
  const fail = (condition, reason) => { if (!condition) throw new Error(reason); };
  const sha = x => typeof x === "string" && /^[a-f0-9]{64}$/.test(x);
  const run = x => typeof x === "string" && /^RUN-[A-F0-9]{16}$/.test(x);
  const services = ["postgres","core","twin","evidence","policy","temporal-postgres","temporal","worker","gamma"];
  const volumes = ["postgres-data","temporal-data","gamma-audit"];
  const same = (a,b) => Array.isArray(a) && JSON.stringify([...a].sort()) === JSON.stringify([...b].sort());
  const obj = x => x !== null && typeof x === "object" && !Array.isArray(x);
  fail(typeof source === "string" && /^[a-f0-9]{40}$/.test(source) && sha(manifest), "expected identities");
  fail(Array.isArray(rows) && rows.length === 3, "three receipts required");
  const containers = new Set(), volumeNames = new Set(), runs = new Set();
  for (let i=0;i<3;i++) {
    const r=rows[i], slot=i+1, project="v3-lab-install-"+slot;
    fail(obj(r) && r.classification==="V3_PREPARED_CLEAN_LAB_INSTALL" && r.result==="PASS" && r.production_authorized===false,"receipt status");
    fail(r.slot===slot && r.project===project,"slot or project");
    fail(r.source_sha===source && r.manifest_sha256===manifest,"source or manifest");
    fail(typeof r.elapsed_seconds==="number" && Number.isFinite(r.elapsed_seconds) && r.elapsed_seconds>=0 && r.elapsed_seconds<1800,"elapsed seconds");
    fail(obj(r.container_ids) && same(Object.keys(r.container_ids),services),"services");
    for (const id of Object.values(r.container_ids)) {
      fail(typeof id==="string" && /^[a-f0-9]{64}$/.test(id) && !containers.has(id),"container identity");
      containers.add(id);
    }
    fail(same(r.volumes,volumes.map(v=>project+"_"+v)),"volume names");
    for (const v of r.volumes) { fail(!volumeNames.has(v),"duplicate volume name"); volumeNames.add(v); }
    fail(JSON.stringify(r.db_delta)==="[1,2,2,1]","database delta");
    const b=r.boundary, g=r.gamma;
    fail(obj(b) && b.classification==="V3_TEMPORAL_BOUNDARY_RUNTIME" && b.result==="PASS" && b.production_authorized===false &&
      b.core_status==="BLOCKED" && b.business_stages_passed===0 && b.activities_completed===2 && Number.isInteger(b.history_events) && b.history_events>0 &&
      run(b.run_id) && b.workflow_id===b.run_id,"boundary receipt");
    fail(obj(g) && g.classification==="V3_PINNED_GAMMA_HITL_RUNTIME" && g.result==="PASS" && g.production_authorized===false && run(g.run_id),"gamma receipt");
    fail(Array.isArray(g.evidence) && g.evidence.length===2 && g.evidence.every(e=>obj(e)&&typeof e.evidence_id==="string"&&e.evidence_id.length>0&&sha(e.payload_hash)) &&
      new Set(g.evidence.map(e=>e.evidence_id)).size===2,"gamma evidence");
    fail(Array.isArray(g.decisions) && same(g.decisions.map(d=>d?.decision),["SIMULATE_ONLY","DENY"]) &&
      g.decisions.every(d=>obj(d)&&typeof d.receipt_id==="string"&&d.receipt_id.length>0&&sha(d.receipt_sha256)) &&
      new Set(g.decisions.map(d=>d.receipt_id)).size===2,"gamma decisions");
    for (const id of [b.run_id,g.run_id]) { fail(!runs.has(id),"duplicate run"); runs.add(id); }
  }
  return {classification:"V3_INDEPENDENT_LAB_RECEIPT_CONTRACT",result:"PASS",source_sha:source,manifest_sha256:manifest,receipts:3,container_ids:containers.size,volume_names:volumeNames.size,run_ids:runs.size,production_authorized:false,limitations:["Receipt consistency only; no runtime, signature, independent host, physical volume or secret uniqueness attestation."]};
}

function selfTest() {
  const source="a".repeat(40), manifest="b".repeat(64);
  const services=["postgres","core","twin","evidence","policy","temporal-postgres","temporal","worker","gamma"];
  const id=n=>n.toString(16).padStart(64,"0");
  const rid=n=>"RUN-"+n.toString(16).toUpperCase().padStart(16,"0");
  const fixture=()=>[1,2,3].map(slot=>{
    const project="v3-lab-install-"+slot;
    return {classification:"V3_PREPARED_CLEAN_LAB_INSTALL",result:"PASS",slot,project,source_sha:source,manifest_sha256:manifest,elapsed_seconds:12,production_authorized:false,container_ids:Object.fromEntries(services.map((s,i)=>[s,id(slot*100+i)])),volumes:["postgres-data","temporal-data","gamma-audit"].map(v=>project+"_"+v),db_delta:[1,2,2,1],boundary:{classification:"V3_TEMPORAL_BOUNDARY_RUNTIME",result:"PASS",production_authorized:false,core_status:"BLOCKED",business_stages_passed:0,activities_completed:2,history_events:12,run_id:rid(slot*2),workflow_id:rid(slot*2)},gamma:{classification:"V3_PINNED_GAMMA_HITL_RUNTIME",result:"PASS",production_authorized:false,run_id:rid(slot*2+1),evidence:[{evidence_id:"E1",payload_hash:manifest},{evidence_id:"E2",payload_hash:manifest}],decisions:[{decision:"SIMULATE_ONLY",receipt_id:"D1",receipt_sha256:manifest},{decision:"DENY",receipt_id:"D2",receipt_sha256:manifest}]}};
  });
  const cases=[
    ["missing slot",r=>r.pop()],
    ["repeat slot",r=>r[1].slot=1],
    ["wrong project",r=>r[1].project="other"],
    ["wrong source",r=>r[1].source_sha="c".repeat(40)],
    ["wrong manifest",r=>r[1].manifest_sha256="bad"],
    ["negative duration",r=>r[0].elapsed_seconds=-1],
    ["duration limit",r=>r[0].elapsed_seconds=1800],
    ["duplicate container",r=>r[1].container_ids.core=r[0].container_ids.core],
    ["missing service",r=>delete r[1].container_ids.core],
    ["wrong volume",r=>r[1].volumes[0]="unrelated"],
    ["wrong DB delta",r=>r[0].db_delta=[0,0,0,0]],
    ["boundary failure",r=>r[0].boundary.result="FAIL"],
    ["business stage bypass",r=>r[0].boundary.business_stages_passed=1],
    ["gamma failure",r=>r[0].gamma.result="FAIL"],
    ["missing evidence",r=>r[0].gamma.evidence.pop()],
    ["unsafe decision",r=>r[0].gamma.decisions[0].decision="LIVE"],
    ["duplicate run",r=>r[1].gamma.run_id=r[0].gamma.run_id],
    ["production flag",r=>r[0].production_authorized=true],
    ["nested production flag",r=>r[0].gamma.production_authorized=true]
  ];
  verify(fixture(),source,manifest);
  for (const [name,mutate] of cases) {
    const rows=fixture(); mutate(rows);
    let rejected=false; try {verify(rows,source,manifest);} catch(e) {rejected=true;}
    if (!rejected) throw new Error("accepted invalid fixture: "+name);
  }
  return {result:"PASS",positive:1,negative:cases.length,cases:cases.map(x=>x[0])};
}

if (require.main === module) {
  try {
    const args=process.argv.slice(2);
    if (args.length===1 && args[0]==="--self-test") {
      console.log(JSON.stringify(selfTest()));
    } else {
      if (args.length!==5) throw new Error("usage: node verify-lab-install-receipts.cjs EXPECTED_SOURCE_SHA manifest.json install-1.json install-2.json install-3.json");
      const fs=require("node:fs"), crypto=require("node:crypto");
      const [source,manifestPath,...paths]=args;
      const raw=fs.readFileSync(manifestPath);
      const manifest=JSON.parse(raw);
      if (manifest.classification!=="V3_DISPOSABLE_LAB_KIT" || manifest.source_sha!==source || manifest.production_authorized!==false) throw new Error("manifest metadata mismatch");
      const digest=crypto.createHash("sha256").update(raw).digest("hex");
      console.log(JSON.stringify(verify(paths.map(p=>JSON.parse(fs.readFileSync(p,"utf8"))),source,digest)));
    }
  } catch(e) {
    console.error(JSON.stringify({result:"FAIL",reason:e.message,production_authorized:false}));
    process.exitCode=1;
  }
}
module.exports={verify,selfTest};
