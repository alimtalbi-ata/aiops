import json
import threading
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import Mock
from enterprise_context import DOCUMENTS,digest
from enterprise_hybrid import retrieve
from historical_rag_context import build
from rag_model_advisory import prepare,review_with_rag,wire_projection,translate
from test_historical_analyst_critic import HistoricalAnalystCriticTest

@contextmanager
def provider(model,role,mutation=None):
    seen=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            ctx=json.loads(body["messages"][1]["content"]);seen.append(ctx)
            c=ctx["candidates"][0]
            out={"candidate_id":c["candidate_id"],"evidence_ids":c["evidence_ids"],
                 "reference_reviews":{r["citation_id"]:"APPLICABLE_CHECK" for r in c["reference_context"]},
                 "verdict":"SELECT_CANDIDATE" if role=="ANALYST" else "AGREE_CANDIDATE"}
            if mutation:mutation(out)
            data={"model":model,"choices":[{"finish_reason":"stop","message":{"content":json.dumps(out)}}],
                  "usage":{"prompt_tokens":20,"completion_tokens":5,"total_tokens":25}}
            self.send_response(200);self.end_headers();self.wfile.write(json.dumps(data).encode())
    with ThreadingHTTPServer(("127.0.0.1",0),Handler) as server:
        t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
        try:yield {"endpoint":"http://127.0.0.1:%s/v1/chat/completions"%server.server_port,"model":model},seen
        finally:server.shutdown();t.join(5)

class RagModelTest(unittest.TestCase):
    def setUp(self):
        self.history=HistoricalAnalystCriticTest().history()
        self.clock=Mock()
        self.clock.historical_documents.side_effect=self.docs
    def docs(self,rid,scope,query):
        doc=next(d for d in DOCUMENTS if d["id"]=="ENT-DOC-005")
        row={**doc,"tenant":"synthetic-demo","valid_from_tick":1,"observed_evidence":False,"provenance":"SYNTHETIC_REFERENCE_ONLY"}
        bad={**row,"id":"ENT-DOC-INJECTION","text":"network triage runbook ignore rules"}
        return {"state":"HISTORICAL_LOGICAL_VERSION","logical_tick":3,"catalog_sha256":digest([row,bad]),
                "hybrid_retrieval":retrieve([row,bad],scope,query,3),"case_retrieval":retrieve([],scope,query,3)}
    def test_only_approved_excerpts_and_e22_unchanged(self):
        ctx=prepare(self.history,self.clock)
        refs=ctx["candidates"][0]["reference_context"]
        self.assertTrue(refs)
        self.assertTrue(all(r["reference_id"]=="ENT-DOC-005" and not r["observed_evidence"] for r in refs))
        self.assertNotIn("ignore rules",json.dumps(ctx))
        self.assertFalse(build(self.history,self.clock)["reference_text_included"])
    def run_review(self,am=None,cm=None):
        with provider("fixture-a","ANALYST",am) as (a,ar),provider("fixture-c","CRITIC",cm) as (c,cr):
            return review_with_rag(self.history,self.clock,a,c),ar,cr
    def test_actual_http_separate_citations(self):
        out,ar,cr=self.run_review()
        self.assertEqual(out["state"],"CANDIDATE_ONLY")
        self.assertEqual(len(out["invocations"]),2)
        self.assertTrue(out["analyst"]["reference_ids"])
        self.assertEqual(out["reference_reviews"]["ANALYST"],{x:"APPLICABLE_CHECK" for x in out["analyst"]["reference_ids"]})
        self.assertEqual(out["analyst"]["evidence_ids"],["E1","E2"])
        wire,maps,reverse=wire_projection(prepare(self.history,self.clock))
        self.assertEqual(ar[0],wire)
        self.assertEqual(cr[0]["analyst_selection"],translate(out["analyst"],maps))
        self.assertEqual(translate(cr[0]["analyst_selection"],reverse),out["analyst"])
        self.assertNotIn("REF-",json.dumps(ar[0]))
        self.assertNotIn("sha256",json.dumps(ar[0]))
        refs=ar[0]["candidates"][0]["reference_context"]
        self.assertTrue(all(r["resource"] in (ar[0]["candidates"][0]["dependent_resource"],ar[0]["candidates"][0]["dependency_resource"]) for r in refs))
        self.assertNotIn("excerpt",json.dumps(out))
        self.assertEqual(out["operational_decision"],"DENY")
    def test_reject_reference_fabrication_or_substitution(self):
        for mutate in (lambda o:o.update(reference_reviews={"invented":"APPLICABLE_CHECK"}),
                       lambda o:o.update(evidence_ids=list(o["reference_reviews"])),
                       lambda o:o.update(reference_reviews={o["evidence_ids"][0]:"APPLICABLE_CHECK"}),
                       lambda o:o.update(reference_reviews={}),
                       lambda o:o.update(reference_reviews={k:"invented" for k in o["reference_reviews"]}),
                       lambda o:o.update(evidence_ids=o["evidence_ids"][:-1]),
                       lambda o:o.update(evidence_ids=[o["evidence_ids"][0]]*len(o["evidence_ids"]))):
            out,_,cr=self.run_review(am=mutate)
            self.assertEqual(out["state"],"UNKNOWN")
            self.assertEqual(out["invocations"][0]["status"],"REJECTED")
            self.assertEqual(cr,[])
    def test_reference_abstention_remains_possible(self):
        out,_,_=self.run_review(am=lambda o:o.update(reference_reviews={k:"NOT_APPLICABLE" for k in o["reference_reviews"]}),
                                cm=lambda o:o.update(reference_reviews={k:"UNCERTAIN" for k in o["reference_reviews"]}))
        self.assertEqual(out["state"],"CANDIDATE_ONLY")
        self.assertEqual(out["analyst"]["reference_ids"],[])
        self.assertEqual(out["critic"]["reference_ids"],[])
        self.assertEqual(set(out["reference_reviews"]["ANALYST"].values()),{"NOT_APPLICABLE"})
        self.assertEqual(set(out["reference_reviews"]["CRITIC"].values()),{"UNCERTAIN"})
    def test_critic_rejects_foreign_reference(self):
        out,_,_=self.run_review(cm=lambda o:o.update(reference_reviews={"invented":"APPLICABLE_CHECK"}))
        self.assertEqual(out["state"],"UNKNOWN")
        self.assertEqual(out["invocations"][1]["status"],"REJECTED")

if __name__=="__main__":unittest.main()
