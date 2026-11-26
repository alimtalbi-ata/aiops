"""Actual local HTTP transport against deterministic fixtures; no real inference."""
import json
import threading
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from test_historical_analyst_critic import HistoricalAnalystCriticTest
from dual_model_advisory import review,usage,config

@contextmanager
def provider(model,role,mutation=None):
    received=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            received.append(body)
            context=json.loads(body["messages"][1]["content"])
            item=context["candidates"][0]
            result={"candidate_id":item["candidate_id"],"evidence_ids":item["evidence_ids"],
                    "verdict":"SELECT_CANDIDATE" if role=="ANALYST" else "AGREE_CANDIDATE"}
            payload={"model":model,"choices":[{"finish_reason":"stop","message":{"content":json.dumps(result)}}],
                     "usage":{"prompt_tokens":10,"completion_tokens":5,"total_tokens":15}}
            if mutation:mutation(payload,result)
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())
    with ThreadingHTTPServer(("127.0.0.1",0),Handler) as server:
        t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
        try:yield {"endpoint":"http://127.0.0.1:%s/v1/chat/completions"%server.server_port,"model":model},received
        finally:server.shutdown();t.join(5)

def change(payload,result,**changes):
    result.update(changes)
    payload["choices"][0]["message"]["content"]=json.dumps(result)

class DualModelTest(unittest.TestCase):
    def run_review(self,a_mut=None,c_mut=None,reverse=False):
        h=HistoricalAnalystCriticTest().history(dep_at="2026-01-01T09:00:02Z" if reverse else "2026-01-01T09:00:00Z")
        with provider("fixture-a","ANALYST",a_mut) as (a,ar),provider("fixture-c","CRITIC",c_mut) as (c,cr):
            return review(h,a,c),ar,cr
    def test_two_http_invocations_and_telemetry(self):
        d,ar,cr=self.run_review()
        self.assertEqual(d["state"],"CANDIDATE_ONLY")
        self.assertEqual((len(ar),len(cr)),(1,1))
        schema=ar[0]["response_format"]["json_schema"]["schema"]
        self.assertEqual(schema["properties"]["evidence_ids"]["items"]["enum"],d["analyst"]["evidence_ids"])
        self.assertEqual(schema["properties"]["verdict"]["enum"],["SELECT_CANDIDATE","ABSTAIN"])
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(json.loads(cr[0]["messages"][1]["content"])["analyst_selection"],d["analyst"])
        self.assertEqual([x["total_tokens"] for x in d["invocations"]],[15,15])
        self.assertTrue(all(x["latency_ms"]>=0 and x["cost"] is None for x in d["invocations"]))
        self.assertFalse(d["model_independence_attested"])
        self.assertFalse(d["production_authorized"])
        self.assertEqual(d["root_cause"],"UNKNOWN")
    def test_fabrication_rejected_before_critic(self):
        d,ar,cr=self.run_review(a_mut=lambda p,r:change(p,r,evidence_ids=["invented"]))
        self.assertEqual(d["state"],"UNKNOWN")
        self.assertEqual(d["invocations"][0]["status"],"REJECTED")
        self.assertEqual(d["invocations"][0]["rejection_code"],"CITATION_SET_MISMATCH")
        self.assertEqual(cr,[])
    def test_critic_challenge_and_reverse_order(self):
        d,_,_=self.run_review(c_mut=lambda p,r:change(p,r,verdict="CHALLENGE_CANDIDATE"))
        self.assertEqual(d["state"],"DISPUTED")
        d,_,_=self.run_review(reverse=True)
        self.assertEqual(d["state"],"DISPUTED")
    def test_malformed_model_and_unknown_usage(self):
        d,_,cr=self.run_review(a_mut=lambda p,r:p.update(model="different"))
        self.assertEqual(d["state"],"UNKNOWN")
        self.assertEqual(cr,[])
        self.assertIsNone(usage({"usage":{"prompt_tokens":1,"completion_tokens":2,"total_tokens":99}})["total_tokens"])
        d,_,_=self.run_review(c_mut=lambda p,r:p.pop("usage"))
        self.assertEqual(d["invocations"][1]["usage_source"],"unavailable")
    def test_invalid_schema_diagnostic_is_bounded(self):
        d,_,cr=self.run_review(a_mut=lambda p,r:change(p,r,unexpected="do not echo this"))
        self.assertEqual(d["state"],"UNKNOWN")
        self.assertEqual(d["invocations"][0]["rejection_code"],"SCHEMA_FIELDS_INVALID")
        self.assertNotIn("do not echo this",json.dumps(d))
        self.assertEqual(cr,[])
    def test_configuration_fail_closed(self):
        for endpoint in ("https://example.com/v1/chat/completions","http://127.0.0.1:7777/v1/chat/completions","http://localhost:12345/v1/chat/completions"):
            with self.assertRaises(ValueError):config({"endpoint":endpoint,"model":"fixture"})
        with provider("fixture","ANALYST") as (p,received):
            with self.assertRaises(ValueError):review(HistoricalAnalystCriticTest().history(),p,p)
            self.assertEqual(received,[])

if __name__=="__main__":unittest.main()
