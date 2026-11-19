import unittest
from copy import deepcopy
from portal.acme_runtime_context import digest
from test_acme_authority_continuity import ContinuityTests
from worker.int07_offline_collector import collect

class CollectorTests(unittest.TestCase):
    def fixture(self):
        f=ContinuityTests(); f.setUp()
        vals=dict(prepared=f.prepared,receipt=f.receipt,history=f.history,postcheck=f.postcheck,
                  terminal=f.terminal,terminal_readback=f.second,manifest=f.manifest,independent=f.independent)
        env={k:dict(source_id=k+"-source",observed_at="2026-11-18T09:00:22Z",content=deepcopy(v),content_sha256=digest(v)) for k,v in vals.items()}
        for k in ("history","postcheck","terminal_readback"):
            env[k]["source_id"]=f.sources["terminal" if k=="terminal_readback" else k]
        f.registry.update({k:v["source_id"] for k,v in env.items()})
        f.policies.update({v["source_id"]:30 for v in env.values()})
        return f,env

    def invoke(self,f,env,second=None):
        readers={k:lambda k=k:deepcopy(f.rows[k]) for k in f.rows}
        obs={k:lambda k=k:deepcopy(env[k]) for k in env}
        calls=[]
        def terminal():
            calls.append(1)
            return deepcopy(second if second is not None and len(calls)==2 else env["terminal_readback"])
        obs["terminal_readback"]=terminal
        r=collect(f.e,f.i,readers,obs,f.policies,f.registry,"2026-11-18T09:00:30Z",f.sha)
        for k in ("go","runtime_attested","finish_authorized","resolution_authorized","live_remediation_authorized"):
            self.assertIs(r[k],False)
        self.assertIn(r["qualification"],("BLOCK","REJECT"))
        return r,calls

    def test_nominal(self):
        f,e=self.fixture(); r,calls=self.invoke(f,e)
        self.assertEqual(r["reason"],"OFFLINE_CONTINUITY_CONSISTENT_NOT_ATTESTED")
        self.assertEqual(len(calls),2)

    def test_second_changed(self):
        f,e=self.fixture(); second=deepcopy(e["terminal_readback"]); second["observed_at"]="2026-11-18T09:00:23Z"
        r,calls=self.invoke(f,e,second)
        self.assertEqual(r["reason"],"TERMINAL_CHANGED")
        self.assertEqual(len(calls),2)

    def test_adverse(self):
        for role,field,value,reason in [
            ("history","receipt_sha256","0"*64,"CONTINUITY_DIGEST_MISMATCH"),
            ("postcheck","verified",False,"CONTINUITY_DIGEST_MISMATCH"),
            ("independent","critic_decision","DENY","CONTINUITY_INVALID"),
            ("manifest","runtime_attested",True,"CONTINUITY_INVALID")]:
            with self.subTest(role=role,field=field):
                f,e=self.fixture(); e[role]["content"][field]=value
                e[role]["content_sha256"]=digest(e[role]["content"])
                self.assertEqual(self.invoke(f,e)[0]["reason"],reason)
