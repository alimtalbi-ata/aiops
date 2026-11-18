import unittest
from copy import deepcopy
from portal.acme_runtime_context import digest
from test_acme_authority_continuity import ContinuityTests
from int06c_v4 import collect

class CollectorV4(unittest.TestCase):
    def fixture(self):
        f=ContinuityTests(); f.setUp()
        h=dict(identity=f.manifest["identity"],receipt_sha256=f.receipt["receipt_sha256"],observed_at="2026-11-18T09:00:08Z")
        q=dict(identity=f.manifest["identity"],history_sha256=digest(h),verified=True,observed_at="2026-11-18T09:00:15Z")
        a=f.independent["terminal"]; a["postcheck_sha256"]=digest(q)
        f.manifest["terminal"]=deepcopy(a)
        f.independent["history_sha256"]=f.manifest["history_sha256"]=digest(h)
        f.independent["terminal_readback_sha256"]=digest(a)
        f.terminal["payload"]["terminal_readback_sha256"]=digest(a); f.seal(f.terminal)
        vals=dict(prepared=f.prepared,receipt=f.receipt,history=h,postcheck=q,terminal=f.terminal,terminal_readback=a,manifest=f.manifest,independent=f.independent)
        env={k:dict(source_id=k+"-source",observed_at="2026-11-18T09:00:22Z",content=deepcopy(v),content_sha256=digest(v)) for k,v in vals.items()}
        f.registry.update({k:v["source_id"] for k,v in env.items()}); f.policies.update({v["source_id"]:30 for v in env.values()})
        return f,env
    def invoke(self,f,env,second=None):
        readers={k:lambda k=k:deepcopy(f.rows[k]) for k in f.rows}
        obs={k:lambda k=k:deepcopy(env[k]) for k in env}
        if second is not None:
            it=iter([env["terminal_readback"],second]); obs["terminal_readback"]=lambda:deepcopy(next(it))
        r=collect(f.e,f.i,readers,obs,f.policies,f.registry,"2026-11-18T09:00:30Z",f.sha)
        for k in ("go","runtime_attested","finish_authorized","resolution_authorized","live_remediation_authorized"): self.assertIs(r[k],False)
        self.assertIn(r["qualification"],("BLOCK","REJECT"))
        return r
    def test_nominal(self):
        f,e=self.fixture(); self.assertEqual(self.invoke(f,e)["reason"],"OFFLINE_CONTINUITY_CONSISTENT_NOT_ATTESTED")
    def test_second(self):
        f,e=self.fixture(); s=deepcopy(e["terminal_readback"]); s["observed_at"]="2026-11-18T09:00:23Z"
        self.assertEqual(self.invoke(f,e,s)["reason"],"TERMINAL_CHANGED")
    def test_adverse(self):
        for role,field,value,reason in [
          ("history","receipt_sha256","0"*64,"CONTINUITY_DIGEST"),
          ("postcheck","verified",False,"CONTINUITY_DIGEST"),
          ("terminal","observed_at","2026-11-18T09:00:00Z","CHRONOLOGY"),
          ("terminal_readback","postcheck_sha256","0"*64,"CONTINUITY_DIGEST"),
          ("manifest","runtime_attested",True,"CONTINUITY_INVALID"),
          ("independent","critic_decision","DENY","CONTINUITY_INVALID")]:
            with self.subTest(role=role,field=field):
                f,e=self.fixture(); e[role]["content"][field]=value; e[role]["content_sha256"]=digest(e[role]["content"])
                self.assertEqual(self.invoke(f,e)["reason"],reason)
    def test_freshness(self):
        f,e=self.fixture(); del f.policies["history-source"]
        self.assertEqual(self.invoke(f,e)["reason"],"FRESHNESS_POLICY_MISSING:history")
        f,e=self.fixture(); f.policies["history-source"]=1
        self.assertEqual(self.invoke(f,e)["reason"],"STALE:history")
    def test_nonce(self):
        f,e=self.fixture(); f.rows["twin"]["content"]["approval_nonce"]="é"
        f.rows["twin"]["content_sha256"]=digest(f.rows["twin"]["content"])
        f.rows["core"]["content"]["authority_manifest"]["twin"]=digest(f.rows["twin"])
        f.rows["core"]["content_sha256"]=digest(f.rows["core"]["content"])
        self.assertEqual(self.invoke(f,e)["reason"],"NONCE_ASCII")
