import copy
import json
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from enterprise_context import P,ROOT
from enterprise_historical_correlation import historical_preview
from historical_analyst_critic import analyze,critique,assess
from test_enterprise_context import graph
from test_enterprise_correlation import row,T
from test_enterprise_historical_correlation import A,B,fixture

class HistoricalAnalystCriticTest(unittest.TestCase):
    def history(self,dep_at=T,dependent_at="2026-01-01T09:00:01Z",other=P+"NET-LYO",ids=None):
        runs={A:fixture(A,row("wan",P+"WAN",dep_at),"E1"),
              B:fixture(B,row("other",other,dependent_at),"E2")}
        return historical_preview(ids or [A,B],120,graph(),runs.__getitem__)

    def test_provenance_and_determinism(self):
        h=self.history()
        d=assess(h)
        self.assertEqual(d,assess(self.history(ids=[B,A])))
        hypothesis=d["analyst"]["hypotheses"][0]
        self.assertEqual(hypothesis["dependency_evidence"][0]["run_id"],A)
        self.assertEqual(hypothesis["dependent_evidence"][0]["run_id"],B)
        self.assertEqual(hypothesis["dependency_evidence"][0]["payload_hash"],"a"*64)
        self.assertEqual(d["critic"]["checks"][0]["temporal_assessment"],"COMPATIBLE_NOT_PROOF")
        self.assertFalse(d["critic"]["causality_established"])
        self.assertEqual(d["operational_decision"],"DENY")
        self.assertIsNone(hypothesis["confidence"])

    def test_reverse_overlap_and_no_candidate(self):
        for history,verdict in ((self.history(dep_at="2026-01-01T09:00:02Z"),"REVERSE_ORDER_CHALLENGE"),
                                (self.history(dependent_at=T),"ORDER_UNRESOLVED")):
            self.assertEqual(assess(history)["critic"]["checks"][0]["temporal_assessment"],verdict)
        d=assess(self.history(dependent_at="2026-01-01T10:00:00Z"))
        self.assertEqual(d["analyst"]["state"],"UNKNOWN")
        self.assertEqual(d["critic"]["checks"],[])

    def test_critic_refuses_fabrication(self):
        h=self.history()
        for key,value in (("confidence",1),("root_cause","WAN"),("production_authorized",True)):
            proposed=analyze(h)
            proposed[key]=value
            self.assertFalse(critique(proposed,h)["projection_matches"])
        proposed=copy.deepcopy(analyze(h))
        proposed["hypotheses"][0]["dependent_evidence"][0]["payload_hash"]="b"*64
        self.assertFalse(critique(proposed,h)["projection_matches"])
        proposed=copy.deepcopy(analyze(h))
        proposed["hypotheses"][0]["candidate"]["path"]=[]
        self.assertFalse(critique(proposed,h)["projection_matches"])
        for bad in (dict(h,production_authorized=True),dict(h,tenant="foreign")):
            with self.assertRaises(ValueError):assess(bad)

    def test_http_server_owned_projection(self):
        from http_demo import server
        g=graph()
        raw={"nodes":list(g.nodes.values()),"edges":[{"source_id":a,"target_id":b,"relation_type":r} for a,b,r in g.edges]}
        runs={A:fixture(A,row("wan",P+"WAN",T),"E1"),
              B:fixture(B,row("other",P+"NET-LYO","2026-01-01T09:00:01Z"),"E2")}
        def load(port,token,rid,*args,**kwargs):return runs[rid]
        with server(core_config=(18001,"synthetic-token","unused"),context_config=(18101,18102,ROOT,"INC-CI-CONTEXT")) as http,patch("http_demo.get",return_value=raw),patch("http_demo.dynamic_context",side_effect=load),patch("http_demo.create_and_persist") as persist:
            t=threading.Thread(target=http.serve_forever,daemon=True)
            t.start()
            base="http://127.0.0.1:%d"%http.server_port
            def post(payload,origin=base):
                req=Request(base+"/api/v1/enterprise-correlation/assessment",data=json.dumps(payload).encode(),
                            headers={"Content-Type":"application/json","Origin":origin})
                with urlopen(req,timeout=5) as response:return json.load(response)
            try:
                payload={"run_ids":[A,B],"window_seconds":120}
                self.assertEqual(post(payload),assess(self.history()))
                for bad,origin in ((dict(payload,analysis={}),base),(payload,"http://foreign.invalid"),(dict(payload,run_ids=[A,A]),base)):
                    with self.assertRaises(HTTPError) as err:post(bad,origin)
                    self.assertEqual(err.exception.code,503)
                    self.assertEqual(json.load(err.exception)["policy"],"DENY")
                persist.assert_not_called()
            finally:
                http.shutdown()
                t.join(5)

if __name__=="__main__":unittest.main()
