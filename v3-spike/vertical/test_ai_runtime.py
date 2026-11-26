import json,tempfile,threading,unittest,os
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from contextlib import closing
from ai_runtime import read_config,provider_pair,AdvisoryRuntime
from ai_invocation_ledger import InvocationLedger
from enterprise_clock import EnterpriseClock
from http_demo import server
from poc_real_rag import seed
from test_rag_model_advisory import provider
from test_enterprise_context import graph

class RuntimeTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.ledger=InvocationLedger(self.root)
        self.history,self.ctx=seed(self.ledger)
    def test_explicit_config_and_ports(self):
        self.assertIsNone(read_config(self.root))
        a={"endpoint":"http://127.0.0.1:18001/v1/chat/completions","model":"fixture-a"}
        c={"endpoint":"http://127.0.0.1:18002/v1/chat/completions","model":"fixture-c"}
        data={"analyst":a,"critic":c}
        p=self.root/"ai-runtime.json";p.write_text(json.dumps(data));p.chmod(0o600)
        self.assertEqual(read_config(self.root),data)
        with self.assertRaises(ValueError):provider_pair(data,[18001])
        p.chmod(0o644)
        with self.assertRaises(ValueError):read_config(self.root)
        p.unlink();p.symlink_to(self.root/"missing")
        with self.assertRaises(OSError):read_config(self.root)
    def request(self,http,payload,origin=None):
        base="http://127.0.0.1:%d"%http.server_port
        req=Request(base+"/api/v1/enterprise-correlation/ai-review",data=json.dumps(payload).encode(),
            headers={"Origin":origin or base,"Content-Type":"application/json"})
        with urlopen(req,timeout=10) as r:return json.load(r)
    def test_disabled_default(self):
        with server(enterprise_clock=self.ledger.clock) as http:
            t=threading.Thread(target=http.serve_forever,daemon=True);t.start()
            try:
                with self.assertRaises(HTTPError):self.request(http,{"run_ids":self.history["run_ids"],"window_seconds":240})
            finally:http.shutdown();t.join(5)
    def test_verified_history_and_persisted_review(self):
        with provider("fixture-a","ANALYST") as (a,ar),provider("fixture-c","CRITIC") as (c,cr):
            # Service boundary fixtures here; real Core/Evidence smoke is separate.
            g=graph()
            raw={"nodes":list(g.nodes.values()),"edges":[{"source_id":x,"target_id":y,"relation_type":z} for x,y,z in g.edges]}
            with server(core_config=(18001,"synthetic-token","unused"),context_config=(18101,18102,"NODE-CI-ROOT","INC-CI-CONTEXT"),
                    enterprise_clock=self.ledger.clock,ai_providers={"analyst":a,"critic":c}) as http,patch("http_demo.get",return_value=raw),patch("enterprise_historical_correlation.historical_preview",return_value=self.history) as history:
                t=threading.Thread(target=http.serve_forever,daemon=True);t.start()
                payload={"run_ids":self.history["run_ids"],"window_seconds":240}
                try:
                    for bad in (dict(payload,providers={}),dict(payload,documents=[])):
                        with self.assertRaises(HTTPError):self.request(http,bad)
                    with self.assertRaises(HTTPError):self.request(http,payload,"http://foreign.invalid")
                    self.assertEqual(ar,[])
                    http.ai_runtime.lock.acquire()
                    try:
                        with self.assertRaises(HTTPError):self.request(http,payload)
                    finally:http.ai_runtime.lock.release()
                    self.assertEqual(ar,[])
                    result=self.request(http,payload)
                    self.assertEqual(result["assessment"]["state"],"CANDIDATE_ONLY")
                    self.assertEqual(result["operational_decision"],"DENY")
                    self.assertEqual(result["run_ids"],sorted(self.history["run_ids"]))
                    self.assertEqual((len(ar),len(cr)),(1,1))
                    history.assert_called_once()
                    reopened=InvocationLedger(self.root)
                    self.assertEqual(reopened.read(result["review_id"])["receipt_sha256"],result["receipt_sha256"])
                    base="http://127.0.0.1:%d"%http.server_port
                    req=Request(base+"/api/v1/ai-telemetry",data=json.dumps({"run_ids":self.history["run_ids"]}).encode(),headers={"Origin":base,"Content-Type":"application/json"})
                    with urlopen(req,timeout=5) as response:telemetry=json.load(response)
                    self.assertEqual(telemetry["invocation_count"],2)
                    self.assertEqual(telemetry["reviews"][0]["review_id"],result["review_id"])
                    self.assertEqual(telemetry["reviews"][0]["receipt_sha256"],result["receipt_sha256"])
                    self.assertEqual(telemetry["operational_decision"],"DENY")
                    self.assertEqual((len(ar),len(cr)),(1,1))
                finally:http.shutdown();t.join(5)

if __name__=="__main__":unittest.main()
