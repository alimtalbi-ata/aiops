import test from "node:test";
import assert from "node:assert/strict";
import {renderFsV28,refreshFsV28} from "./fs-v28-view-bridge.mjs";
import {IDS,project} from "./fs-v28-readonly-adapter.mjs";
const makeRoot=()=>{const nodes=new Map();return {nodes,querySelector(selector){const key=selector.match(/^\[data-fs-v28="([^"]+)"\]$/)?.[1];if(!key)return null;if(!nodes.has(key))nodes.set(key,{textContent:""});return nodes.get(key)}}};
const get=(r,k)=>r.nodes.get(k)?.textContent;
const good={incident_id:IDS.incident,run_id:IDS.run,evidence_id:IDS.evidence,source:"CORE_EVIDENCE_READONLY",synthetic:true,no_live_effects:true,incident_state:"OPEN",core_state:"INVESTIGATING",temporal_state:"UNKNOWN",policy_state:"BLOCKED",evidence_state:"OPEN"};
test("connected readonly projection renders same incident run evidence",()=>{const r=makeRoot();renderFsV28(r,project(good));assert.equal(get(r,"incident-id"),IDS.incident);assert.equal(get(r,"run-id"),IDS.run);assert.equal(get(r,"evidence-id"),IDS.evidence);assert.equal(get(r,"core"),"INVESTIGATING");assert.equal(get(r,"availability"),"READONLY_CONNECTED");assert.equal(get(r,"mode"),"SYNTHETIC");assert.equal(get(r,"effects"),"NO_LIVE_EFFECTS");assert.equal(get(r,"approval"),"NOT_ATTESTED");assert.equal(get(r,"resolution"),"NOT_ATTESTED")});
test("unavailable overwrites stale connected state",()=>{const r=makeRoot();renderFsV28(r,project(good));renderFsV28(r,null);assert.equal(get(r,"core"),"UNKNOWN");assert.equal(get(r,"availability"),"UNAVAILABLE");assert.equal(get(r,"source"),"UNAVAILABLE");assert.equal(get(r,"resolution"),"NOT_ATTESTED")});
test("never inject HTML into view",()=>{const r=makeRoot();renderFsV28(r,{...project(good),core:"<img src=x onerror=alert(1)>"});assert.equal(get(r,"core"),"<img src=x onerror=alert(1)>");assert.equal(r.nodes.get("core").innerHTML,undefined)});
test("401 never shows connected",async()=>{const r=makeRoot();await refreshFsV28(r,{fetchImpl:async()=>({ok:false,status:401})});assert.equal(get(r,"availability"),"UNAVAILABLE");assert.equal(get(r,"reason"),"AUTH_REQUIRED")});
test("refresh uses same-origin read-only endpoint",async()=>{const r=makeRoot();let request;await refreshFsV28(r,{fetchImpl:async(...args)=>{request=args;return {ok:true,headers:{get:()=>"application/json"},json:async()=>good}}});assert.equal(request[0],"/api/portal/demo/fs-v28");assert.equal(request[1].method,"GET");assert.equal(get(r,"core"),"INVESTIGATING")});

test("older success cannot overwrite newer 401 denial",async()=>{
  const r=makeRoot();
  let finish;
  const old=refreshFsV28(r,{fetchImpl:()=>new Promise(resolve=>{finish=resolve})});
  const newer=await refreshFsV28(r,{fetchImpl:async()=>({ok:false,status:401})});
  assert.equal(newer.reason,"AUTH_REQUIRED");
  finish({ok:true,headers:{get:()=>"application/json"},json:async()=>good});
  const stale=await old;
  assert.equal(stale.reason,"SUPERSEDED_REFRESH");
  assert.equal(get(r,"availability"),"UNAVAILABLE");
  assert.equal(get(r,"reason"),"AUTH_REQUIRED");
  assert.equal(get(r,"core"),"UNKNOWN");
});
test("older 401 cannot overwrite newer connected result",async()=>{
  const r=makeRoot();
  let finish;
  const old=refreshFsV28(r,{fetchImpl:()=>new Promise(resolve=>{finish=resolve})});
  await refreshFsV28(r,{fetchImpl:async()=>({ok:true,headers:{get:()=>"application/json"},json:async()=>good})});
  finish({ok:false,status:401});
  assert.equal((await old).reason,"SUPERSEDED_REFRESH");
  assert.equal(get(r,"availability"),"READONLY_CONNECTED");
  assert.equal(get(r,"core"),"INVESTIGATING");
});
