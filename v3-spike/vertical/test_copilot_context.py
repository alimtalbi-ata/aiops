import unittest
from copilot_context import answer

class CopilotTest(unittest.TestCase):
    def test_context(self):
        core={"production_authorized":False,"run":{"run_id":"RUN-CI-X","incident_id":"INC-CI-X"}}
        ctx={"classification":"SYNTHETIC_LAB_CONTEXT","production_authorized":False,"run_id":"RUN-CI-X","policy":"DENY","affected":[{"node_id":"NODE-CI-X"}],"evidence":[{"evidence_id":"E1","payload_hash":"a"*64}]}
        result=answer(core,ctx)
        self.assertEqual(result["sources"],ctx["evidence"])
        self.assertIsNone(result["confidence"])
        self.assertEqual(result["root_cause"],"UNKNOWN")
        self.assertEqual(result["operational_decision"],"DENY")
        with self.assertRaises(ValueError):
            answer(core,dict(ctx,run_id="RUN-CI-Y"))
        with self.assertRaises(ValueError):
            answer(core,dict(ctx,production_authorized=True))

    def test_retrieval(self):
        from evidence_retrieval import retrieve
        from rca_preview import preview
        core={"production_authorized":False,"run":{"run_id":"RUN-CI-X","incident_id":"INC-CI-X","mode":"DEMO"}}
        e=[{"evidence_id":"E3","payload_hash":"c"*64},{"evidence_id":"E1","payload_hash":"a"*64},{"evidence_id":"E2","payload_hash":"b"*64}]
        ctx={"classification":"SYNTHETIC_LAB_CONTEXT","production_authorized":False,"run_id":"RUN-CI-X","policy":"DENY","affected":[],"evidence":e}
        self.assertEqual(answer(core,ctx)["retrieval"]["state"],"UNKNOWN")
        ctx["diagnosis"]=preview([{"synthetic":True,"metric":"latency_ms","phase":p,"value":v,"evidence_id":eid} for p,v,eid in (("baseline",40,"E1"),("incident",160,"E2"))])
        result=answer(core,ctx)["retrieval"]
        self.assertEqual([m["evidence_id"] for m in result["matches"]],["E1","E2"])
        self.assertFalse(result["llm_inference_performed"])
        self.assertFalse(result["causality_established"])
        self.assertEqual(result["operational_decision"],"DENY")
        all_evidence=retrieve(core,ctx,"evidence",limit=1)
        self.assertEqual(all_evidence["matches"][0]["evidence_id"],"E1")
        self.assertTrue(all_evidence["truncated"])
        self.assertEqual(all_evidence["match_count"],3)
        for invalid in (dict(ctx,run_id="RUN-CI-Y"),dict(ctx,evidence=e+[e[0]]),dict(ctx,diagnosis=dict(ctx["diagnosis"],evidence_ids=["FOREIGN"])),dict(ctx,evidence=[dict(e[0],payload_hash="invalid")]),dict(ctx,diagnosis=dict(ctx["diagnosis"],root_cause="invented"))):
            with self.assertRaises(ValueError):
                answer(core,invalid)
        with self.assertRaises(ValueError):
            retrieve(core,ctx,"execute")
        with self.assertRaises(ValueError):
            retrieve(core,ctx,limit=True)

    def test_document_retrieval(self):
        from document_retrieval import references, load_catalog
        from rca_preview import preview
        import hashlib
        import json
        core={"production_authorized":False,"run":{"run_id":"RUN-CI-X","incident_id":"INC-CI-X","mode":"DEMO"}}
        evidence=[{"evidence_id":"E1","payload_hash":"a"*64},{"evidence_id":"E2","payload_hash":"b"*64}]
        ctx={"classification":"SYNTHETIC_LAB_CONTEXT","production_authorized":False,"run_id":"RUN-CI-X","policy":"DENY","root":"NODE-CI-ROOT","affected":[],"evidence":evidence}
        self.assertEqual(answer(core,ctx)["document_retrieval"]["state"],"UNKNOWN")
        ctx["diagnosis"]=preview([{"synthetic":True,"metric":"latency_ms","phase":p,"value":v,"evidence_id":eid} for p,v,eid in (("baseline",40,"E1"),("incident",160,"E2"))])
        result=answer(core,ctx)
        docs=result["document_retrieval"]
        self.assertEqual(docs["state"],"MATCHED")
        self.assertEqual(docs["citations"][0]["doc_id"],"SYN-LATENCY-001")
        self.assertEqual(result["sources"],evidence)
        self.assertFalse(docs["llm_inference_performed"])
        self.assertFalse(docs["causality_established"])
        rows,digest=load_catalog()
        self.assertEqual(docs["catalog_sha256"],digest)
        for citation in docs["citations"]:
            row=next(r for r in rows if r["doc_id"]==citation["doc_id"])
            self.assertEqual(citation["doc_sha256"],hashlib.sha256(json.dumps(row,sort_keys=True,separators=(",",":")).encode()).hexdigest())
            self.assertFalse(citation["observed_evidence"])
        self.assertEqual(answer(core,dict(ctx,root="NODE-CI-OTHER"))["document_retrieval"]["state"],"UNKNOWN")
        self.assertEqual(answer(core,ctx,topic="evidence")["document_retrieval"]["state"],"UNKNOWN")
        self.assertTrue(references(ctx,result["retrieval"],limit=1)["truncated"])
        with self.assertRaises(ValueError):
            references(ctx,dict(result["retrieval"],run_id="FOREIGN"))
