import unittest
import tempfile
from enterprise_context import P, digest
from enterprise_clock import EnterpriseClock
from enterprise_hybrid import retrieve, METHOD

def fixture(ident,scope,text,tick=1,tenant="synthetic-demo"):
    return {"id":ident,"version":1,"title":text,"text":text,"scope":[scope],
            "valid_from_tick":tick,"tenant":tenant,"observed_evidence":False}

class HybridTest(unittest.TestCase):
    def test_vector_only_typo_and_scope_before_ranking(self):
        scope={P+"APP-PAY"}
        correct=fixture("PAY",P+"APP-PAY","authentication")
        wrong=fixture("HR",P+"APP-HR","authentcation")
        future=fixture("FUTURE",P+"APP-PAY","authentcation",8)
        foreign=fixture("FOREIGN",P+"APP-PAY","authentcation",tenant="foreign")
        rows=[wrong,future,foreign,correct]
        result=retrieve(rows,scope,"authentcation",3)
        self.assertEqual(result["candidate_count"],1)
        self.assertEqual(result["state"],"MATCHED")
        self.assertEqual(result["method"],METHOD)
        self.assertEqual(result["citations"][0]["id"],"PAY")
        self.assertEqual(result["citations"][0]["bm25_score"],0)
        self.assertGreater(result["citations"][0]["vector_cosine"],.18)
        self.assertEqual(result,retrieve([correct],scope,"authentcation",3))
        self.assertEqual(result,retrieve(list(reversed(rows)),scope,"authentcation",3))
        self.assertFalse(result["learned_embeddings"])
        self.assertFalse(result["llm_inference_performed"])
        self.assertEqual(retrieve(rows,scope,"zzzzzzzz",3)["state"],"NO_MATCH")
        self.assertEqual(retrieve(rows,scope,"the and",3)["citations"],[])
        with self.assertRaises(ValueError):
            retrieve([dict(correct,sha256="a"*64)],scope,"authentication",3)
        with self.assertRaises(ValueError):
            retrieve([correct,correct],scope,"authentication",3)

    def test_actual_clock_corpus_relevance(self):
        with tempfile.TemporaryDirectory() as root:
            clock=EnterpriseClock(root)
            runs=[]
            def publish(rows):
                n=str(len(runs)+1)
                run="RUN-"+n*16
                runs.append(run)
                return {"production_authorized":False,"core":{"run":{"mode":"DEMO","run_id":run,"incident_id":"INC-CI-INGEST-"+n*32}},
                        "stored_evidence":[{"evidence_id":f"E{n}-{i}","payload_hash":str(i)*64} for i in range(4)]}
            for tick in range(1,9): clock.advance(tick,publish)
            scope={P+"APP-PAY",P+"ASSET-PAR",P+"GROUP-FIN"}
            first=clock.historical_documents(runs[0],scope,"Payments latency runbook")["hybrid_retrieval"]
            second=clock.historical_documents(runs[1],scope,"Payments latency runbook")["hybrid_retrieval"]
            self.assertEqual(first["citations"][0]["id"],"ENT-DOC-001")
            self.assertEqual(first["citations"][0]["version"],2)
            self.assertEqual(second["citations"][0]["id"],"ENT-DOC-001")
            self.assertEqual(second["citations"][0]["version"],3)
            self.assertEqual(first,EnterpriseClock(root).historical_documents(runs[0],scope,"Payments latency runbook")["hybrid_retrieval"])
            for res,tick in ((first,3),(second,7)):
                self.assertTrue(all(r["valid_from_tick"]<=tick and set(r["scope"])&scope for r in res["citations"]))
                self.assertTrue(all(r["observed_evidence"] is False for r in res["citations"]))
            recovery=clock.historical_documents(runs[1],scope,"recovery remediation measured")["hybrid_retrieval"]
            self.assertEqual(recovery["citations"][0]["kind"],"RECOVERY")
            self.assertEqual(recovery["citations"][0]["source"]["run_id"],runs[0])
            hr=clock.historical_documents(runs[1],{P+"APP-HR"},"HR portal")["hybrid_retrieval"]
            self.assertEqual([r["id"] for r in hr["citations"]],["ENT-DOC-004"])
            self.assertEqual(clock.historical_documents(runs[1],scope,"zzzzzzzz")["hybrid_retrieval"]["state"],"NO_MATCH")

if __name__=="__main__": unittest.main()
