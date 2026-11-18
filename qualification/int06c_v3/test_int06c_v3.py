import asyncio,unittest
from copy import deepcopy
from test_worker_acme_simulated_hitl import fixtures,INTENT,NOW
from worker.acme_simulated_hitl import simulate_no_effect
from worker.int06a_contract import IDENTITY,STAGES,digest
from int06c_v3_bridge import exercise

def fixture():
    docs=fixtures()
    e={k:INTENT[k] for k in ("tenant_id","incident_id","run_id","attempt_id")}
    e.update(impact_incident_id="INC-IMPACT-001",snapshot_id="SNAP-001")
    rows={}
    for k,d in docs.items():
        content=dict(d,**INTENT,impact_incident_id=e["impact_incident_id"],snapshot_id=e["snapshot_id"])
        rows[k]=dict(authority=k,scope="RUNTIME_SANDBOX",source_id=k+"-001",source_ref="fixture:"+k,observed_at="2026-11-02T16:00:00Z",snapshot_id=e["snapshot_id"],content=content,content_sha256=digest(content))
    rows["core"]["content"].update(version=1,authority_manifest={k:digest(rows[k]) for k in ("twin","policy")})
    rows["core"]["content_sha256"]=digest(rows["core"]["content"])
    async def get(k,path): return deepcopy(docs[k])
    receipt=asyncio.run(simulate_no_effect(INTENT,get=get,now=NOW))
    identity={k:INTENT[k] for k in IDENTITY}
    common=dict(identity=identity,prepared_snapshot=e["snapshot_id"],impact_incident_id=e["impact_incident_id"])
    h=dict(common,receipt_sha256=receipt["receipt_sha256"],observed_at="2026-11-02T16:00:01Z")
    p=dict(common,history_sha256=digest(h),verified=True,observed_at="2026-11-02T16:00:02Z")
    t=dict(common,source="CORE",status="RESOLVED",version=99,sequence=99,snapshot_id="SNAP-002",postcheck_sha256=digest(p),observed_at="2026-11-02T16:00:03Z")
    stages=[dict(identity=identity,stage=s,status="PASS",version=j+1,sequence=j+1,source="CORE",observed_at="2026-11-02T16:00:02Z") for j,s in enumerate(STAGES)]
    images={k:"sha256:"+"b"*64 for k in ("core","twin","policy","worker","evidence","postgres","temporal","temporal_postgres")}
    m=dict(scope="RUNTIME_SANDBOX",executed_sha="a"*40,runtime_attested=False,identity=identity,images=images,worker_receipt=receipt,history_sha256=digest(h),transitions=stages,terminal=deepcopy(t))
    i=dict(identity=identity,scope=m["scope"],executed_sha=m["executed_sha"],images=deepcopy(images),worker_receipt_sha256=receipt["receipt_sha256"],history_sha256=digest(h),transitions_sha256=digest(stages),critic_decision="ALLOW",twin_state="QUALIFIED",policy_decision="SIMULATE",hitl_valid=True,external_effect_count=0,postcheck_verified=True,terminal=deepcopy(t),terminal_readback_sha256=digest(t))
    return e,rows,m,dict(history=h,postcheck=p,terminal=t,terminal_readback=deepcopy(t),independent=i)

class V3(unittest.TestCase):
    def run_case(self,f):
        e,rows,m,o=f
        return exercise(e,INTENT,{k:lambda k=k:deepcopy(rows[k]) for k in rows},{k+"-001":30 for k in rows},{k:k+"-001" for k in rows},"2026-11-02T16:00:04Z",m,o,"a"*40)
    def test_nominal(self):
        r=self.run_case(fixture())
        self.assertEqual(r["b"]["qualification"],"BLOCK")
        self.assertEqual(r["c"]["qualification"],"CONTRACT_ONLY")
        for k in ("runtime_attested","resolution_authorized","finish_authorized","go"): self.assertIs(r[k],False)
    def test_b_refusal(self):
        for field,value in (("snapshot_id","FOREIGN"),("observed_at","2026-11-02T15:59:00Z")):
            with self.subTest(field=field):
                f=fixture(); f[1]["twin"][field]=value
                r=self.run_case(f); self.assertIsNone(r["c"]); self.assertFalse(r["go"])
    def test_continuity(self):
        for role,field,value in (("history","receipt_sha256","f"*64),("postcheck","history_sha256","f"*64),("terminal","prepared_snapshot","FOREIGN"),("terminal_readback","version",100),("terminal","snapshot_id","SNAP-001"),("postcheck","observed_at","2026-11-02T16:00:00Z"),("independent","postcheck_verified",False),("independent","critic_decision","DENY"),("independent","external_effect_count",True)):
            with self.subTest(role=role,field=field):
                f=fixture(); f[3][role][field]=value
                with self.assertRaises(ValueError): self.run_case(f)
    def test_receipt(self):
        for field,value in (("effect_receipts",False),("core_request_sha256","f"*64),("twin_approval_nonce_sha256","f"*64),("live_effects_allowed",True)):
            with self.subTest(field=field):
                f=fixture(); r=f[2]["worker_receipt"]; r[field]=value
                r["receipt_sha256"]=digest({k:v for k,v in r.items() if k!="receipt_sha256"})
                with self.assertRaises(ValueError): self.run_case(f)
    def test_manifest(self):
        for field,value in (("runtime_attested",True),("executed_sha","f"*40),("terminal",None)):
            with self.subTest(field=field):
                f=fixture(); f[2][field]=value
                with self.assertRaises(ValueError): self.run_case(f)
        f=fixture(); f[2]["transitions"][1]["sequence"]=1
        f[3]["independent"]["transitions_sha256"]=digest(f[2]["transitions"])
        with self.assertRaises(ValueError): self.run_case(f)
