"""Same Golden/V4 run through existing B and C offline functions."""
from copy import deepcopy
import pytest
from portal.acme_runtime_context import digest, RECEIPT
from worker.acme_simulated_hitl import verify_no_effect_receipt
from worker.int07_offline_collector import collect
from worker.int06a_contract import STAGES
from test_int09b_preterminal import chain, invoke

@pytest.mark.parametrize("case", ["nominal","foreign","prefix","terminal_drift"])
def test_golden_final(case):
    f=chain()
    expected,intent,admission,second,registry,phase,sources,policies=f
    assert invoke(f)["contract_status"]=="CONTRACT_ONLY"
    receipt=phase["receipt"]["content"]
    seven={k:intent[k] for k in RECEIPT}
    assert verify_no_effect_receipt(receipt,seven)
    rows={k:admission[k]["content"] for k in ("core","twin","policy")}
    ident={k:expected[k] for k in ("tenant_id","incident_id","impact_incident_id","run_id","attempt_id")}
    def seal(row):
        row["manifest_sha256"]=digest({k:v for k,v in row.items() if k not in ("manifest_sha256","collected_at")})
    prepared=dict(identity=ident,snapshot_id=expected["snapshot_id"],parent_snapshot_id=None,version=1,phase="PREPARED",observed_at=rows["core"]["observed_at"],collected_at="2026-11-18T12:00:01Z",payload=dict(core_sha256=digest(rows["core"]),authority_manifest=rows["core"]["content"]["authority_manifest"]))
    seal(prepared)
    common=dict(identity=seven,parent_snapshot_id=expected["snapshot_id"],impact_incident_id=expected["impact_incident_id"])
    history=dict(common,source_id="final-history",observed_at="2026-11-18T12:00:02Z",receipt_sha256=receipt["receipt_sha256"],prefix_sha256=digest(phase["history_prefix"]["content"]))
    post=dict(common,source_id="final-postcheck",observed_at="2026-11-18T12:00:03Z",history_sha256=digest(history),verified=True)
    actual=dict(common,source="CORE",source_id="final-terminal_readback",status="RESOLVED",version=20,sequence=20,observed_at="2026-11-18T12:00:20Z",snapshot_id="SNAP-002",postcheck_sha256=digest(post))
    terminal=dict(identity=ident,snapshot_id="SNAP-002",parent_snapshot_id=expected["snapshot_id"],version=20,phase="TERMINAL",observed_at=actual["observed_at"],collected_at="2026-11-18T12:00:21Z",payload=dict(terminal_readback_sha256=digest(actual),prepared_manifest_sha256=prepared["manifest_sha256"],receipt_sha256=receipt["receipt_sha256"]))
    seal(terminal)
    images={k:"sha256:"+"b"*64 for k in ("core","twin","policy","worker","evidence","postgres","temporal","temporal_postgres")}
    transitions=[dict(identity=seven,stage=k,status="PASS",version=n,sequence=n,observed_at="2026-11-18T12:00:10Z",source="CORE") for n,k in enumerate(STAGES,2)]
    sha="c"*40
    manifest=dict(scope="RUNTIME_SANDBOX",executed_sha=sha,runtime_attested=False,identity=seven,images=images,worker_receipt=receipt,history_sha256=digest(history),transitions=transitions,terminal=actual)
    independent=dict(phase["postcheck"]["content"],executed_sha=sha,scope="RUNTIME_SANDBOX",images=images,worker_receipt_sha256=receipt["receipt_sha256"],history_sha256=digest(history),transitions_sha256=digest(transitions),terminal=actual,terminal_readback_sha256=digest(actual))
    vals=dict(prepared=prepared,receipt=receipt,history=history,postcheck=post,terminal=terminal,terminal_readback=actual,manifest=manifest,independent=independent)
    if case=="foreign": vals["terminal"]=deepcopy(terminal); vals["terminal"]["identity"]=dict(ident,tenant_id="FOREIGN"); seal(vals["terminal"])
    if case=="prefix": vals["history"]=dict(history,prefix_sha256="0"*64)
    env={k:dict(source_id="final-"+k,observed_at="2026-11-18T12:00:22Z",content=v,content_sha256=digest(v)) for k,v in vals.items()}
    reg={k:registry[k] for k in rows}|{k:v["source_id"] for k,v in env.items()}
    policies.update({v:300 for v in reg.values()})
    readers={k:lambda k=k: deepcopy(rows[k]) for k in rows}
    observers={k:lambda k=k: deepcopy(env[k]) for k in env}
    calls=[]
    def terminal_read():
        calls.append(1)
        value=deepcopy(env["terminal_readback"])
        if case=="terminal_drift" and len(calls)==2: value["observed_at"]="2026-11-18T12:00:23Z"
        return value
    observers["terminal_readback"]=terminal_read
    result=collect(expected,intent,readers,observers,policies,reg,"2026-11-18T12:00:30Z",sha)
    assert (result["reason"]=="OFFLINE_CONTINUITY_CONSISTENT_NOT_ATTESTED")== (case=="nominal"),result
    for k in ("go","runtime_attested","finish_authorized","resolution_authorized","live_remediation_authorized"): assert result[k] is False
