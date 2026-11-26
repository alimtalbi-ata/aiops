import tempfile,unittest,json,threading
from contextlib import closing
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from ai_invocation_ledger import InvocationLedger
from enterprise_clock import EnterpriseClock
from gamma_ai_telemetry import snapshot
from test_historical_analyst_critic import HistoricalAnalystCriticTest
from test_dual_model_advisory import provider
from http_demo import server

def fixture(ledger):
    history=HistoricalAnalystCriticTest().history()
    with provider("fixture-a","ANALYST") as (a,ar),provider("fixture-c","CRITIC",lambda p,r:p.pop("usage")) as (c,cr):
        result=ledger.execute(history,a,c)
    return history["run_ids"],result["review_id"]

class GammaTelemetryTest(unittest.TestCase):
    def test_missing_table_read_only(self):
        with tempfile.TemporaryDirectory() as root:
            clock=EnterpriseClock(root)
            self.assertEqual(snapshot(clock,["RUN-"+"A"*16])["state"],"NO_RECEIPTS")
            with closing(clock.connect()) as db:self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='ai_invocation_reviews'").fetchone())
    def test_scope_and_http(self):
        with tempfile.TemporaryDirectory() as root:
            ledger=InvocationLedger(root)
            ids,review=fixture(ledger)
            self.assertEqual(snapshot(ledger.clock,[ids[0]])["state"],"NO_RECEIPTS")
            with server(enterprise_clock=ledger.clock) as http:
                t=threading.Thread(target=http.serve_forever,daemon=True);t.start()
                base="http://127.0.0.1:%d"%http.server_port
                def post(payload,origin=base):
                    req=Request(base+"/api/v1/ai-telemetry",data=json.dumps(payload).encode(),
                                headers={"Origin":origin,"Content-Type":"application/json"})
                    with urlopen(req,timeout=5) as r:return json.load(r)
                try:
                    d=post({"run_ids":ids})
                    self.assertEqual(d["invocation_count"],2)
                    self.assertEqual(d["reviews"][0]["review_id"],review)
                    self.assertIsNone(d["groups"][1]["total_tokens"])
                    self.assertIsNone(d["groups"][1]["cost"])
                    self.assertEqual(d["groups"][0]["total_tokens"],15)
                    self.assertEqual(d,post({"run_ids":list(reversed(ids))}))
                    for bad in ({"run_ids":ids,"receipts":[]},{"run_ids":[ids[0],ids[0]]}):
                        with self.assertRaises(HTTPError):post(bad)
                    with self.assertRaises(HTTPError):post({"run_ids":ids},"http://foreign.invalid")
                    with closing(ledger.clock.connect()) as db,db:db.execute("UPDATE ai_invocation_reviews SET payload_hash=?",("0"*64,))
                    with self.assertRaises(HTTPError):post({"run_ids":ids})
                finally:http.shutdown();t.join(5)

if __name__=="__main__":unittest.main()
