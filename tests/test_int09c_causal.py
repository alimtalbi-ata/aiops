"""Test-only causal connection of existing B/C contracts, no runtime scheduler."""
from copy import deepcopy
from datetime import datetime, timezone
import pytest
from portal.acme_int08_phases import admission_v1, preterminal_v1
from portal.acme_runtime_context import digest
from worker.acme_simulated_hitl import simulate_no_effect, verify_no_effect_receipt
from worker.int06a_contract import IDENTITY
from test_int07_offline_collector import CollectorTests
from test_worker_acme_simulated_hitl import fixtures
from test_int08c_arc08 import history_pair

CLOCK="2026-11-18T09:00:30Z"

import asyncio

def fixture():
    f,e=CollectorTests().fixture()
    # Enrich existing V4 fixture with actual Worker fixture fields, retaining identities.
    for role,content in fixtures().items():
        f.rows[role]["content"]={**content,**f.rows[role]["content"]}
    twin=f.rows["twin"]["content"]
    twin.update(issued_at="2026-11-18T08:59:50Z",expires_at="2026-11-18T09:02:00Z")
    for role in ("twin","policy"):
        f.rows[role]["content_sha256"]=digest(f.rows[role]["content"])
    core=f.rows["core"]["content"]
    core["authority_manifest"]={k:digest(f.rows[k]) for k in ("twin","policy")}
    f.rows["core"]["content_sha256"]=digest(core)
    f.prepared["payload"]={"core_sha256":digest(f.rows["core"]),"authority_manifest":core["authority_manifest"]}
    f.seal(f.prepared)
    e["prepared"]["content"]=deepcopy(f.prepared)
    e["terminal"]["content"]["payload"]["prepared_manifest_sha256"]=f.prepared["manifest_sha256"]
    f.seal(e["terminal"]["content"])
    identity={k:f.i[k] for k in IDENTITY}
    identity["impact_incident_id"]=f.e["impact_incident_id"]
    registry={k:f.registry[k] for k in ("core","twin","policy")}
    registry.update(critic="critic-source",hitl="hitl-source")
    def envelope(role,content,source,at):
        return dict(role=role,source_id=source,classification="STORY_OFFLINE",identity=identity,
                    snapshot_id=f.e["snapshot_id"],observed_at=at,content=content,content_sha256=digest(content))
    rows={k:envelope(k,v,registry[k],v["observed_at"]) for k,v in f.rows.items()}
    rows["critic"]=envelope("critic",dict(decision="ALLOW",core_sha256=digest(f.rows["core"]),twin_sha256=digest(f.rows["twin"])),registry["critic"],"2026-11-18T09:00:01Z")
    rows["hitl"]=envelope("hitl",dict(kind="SIMULATED",human_approved=False,execution_allowed=False,effect_allowed=False,twin_sha256=digest(f.rows["twin"]),policy_sha256=digest(f.rows["policy"])),registry["hitl"],"2026-11-18T09:00:01Z")
    pr={k:k+"-phase-source" for k in ("receipt","history_prefix","postcheck")}
    f.policies.update({v:40 for v in (*registry.values(),*pr.values())})
    return f,e,rows,registry,pr,envelope

@pytest.mark.parametrize("case",["nominal","admission_missing","live","worker_changed","postcheck","terminal_missing","terminal_changed"])
def test_actual_phase_order(case):
    f,e,rows,reg,pr,env=fixture()
    second=deepcopy(rows["core"])
    if case=="live": f.i["mode"]="LIVE"
    a=admission_v1(f.e,f.i,None if case=="admission_missing" else rows,second,reg,f.policies,as_of_utc=CLOCK)
    calls=[]
    if case in ("admission_missing","live"):
        assert a["contract_status"]!="CONTRACT_ONLY"
        assert not calls
        return
    assert a["reason"]=="ADMISSION_CONSISTENT_NOT_ATTESTED",a
    async def get(role,path):
        calls.append(role)
        v=deepcopy(f.rows[role]["content"])
        if case=="worker_changed" and len(calls)>3 and role=="twin": v["approval_nonce"]="changed"
        return v
    from worker.acme_simulated_hitl import SandboxDenied
    if case=="worker_changed":
        with pytest.raises(SandboxDenied): asyncio.run(simulate_no_effect(f.i,get=get,now=datetime(2026,11,18,9,0,2,tzinfo=timezone.utc)))
        return
    receipt=asyncio.run(simulate_no_effect(f.i,get=get,now=datetime(2026,11,18,9,0,2,tzinfo=timezone.utc)))
    assert len(calls)==6
    assert verify_no_effect_receipt(receipt,{k:f.i[k] for k in IDENTITY})
    assert receipt==e["receipt"]["content"]
    history=dict(phase="PREFIX",receipt_sha256=receipt["receipt_sha256"],admission_sha256=digest(rows))
    post={k:e["independent"]["content"][k] for k in ("identity","critic_decision","twin_state","policy_decision","hitl_valid","external_effect_count","postcheck_verified")}
    post["history_prefix_sha256"]=digest(history)
    if case=="postcheck": post["postcheck_verified"]=False
    phase={k:env(k,v,pr[k],at) for k,v,at in (
        ("receipt",receipt,"2026-11-18T09:00:02Z"),("history_prefix",history,"2026-11-18T09:00:05Z"),("postcheck",post,"2026-11-18T09:00:15Z"))}
    p=preterminal_v1(f.e,f.i,rows,second,reg,phase,pr,f.policies,as_of_utc=CLOCK)
    assert p["finish_authorized"] is False
    if case=="postcheck":
        assert p["contract_status"]!="CONTRACT_ONLY"
        return
    assert p["reason"]=="PRETERMINAL_CONSISTENT_NOT_ATTESTED",p
    # Final evidence is the separately supplied synthetic V4 fixture, never a Core write.
    if case=="terminal_missing": del e["terminal"]
    for v in e.values(): v["content_sha256"]=digest(v["content"])
    changed=deepcopy(e["terminal_readback"])
    changed["observed_at"]="2026-11-18T09:00:23Z"
    result,_=CollectorTests().invoke(f,e,changed if case=="terminal_changed" else None)
    assert (result["reason"]=="OFFLINE_CONTINUITY_CONSISTENT_NOT_ATTESTED")== (case=="nominal"),result
