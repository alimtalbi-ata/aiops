import tempfile
import unittest
from contextlib import closing
from enterprise_clock import EnterpriseClock
from enterprise_context import P, digest
from enterprise_corpus import references

class CorpusTest(unittest.TestCase):
    def test_versions_scope_and_history(self):
        with tempfile.TemporaryDirectory() as root:
            clock=EnterpriseClock(root)
            runs=[]
            def publish(rows):
                n=str(len(runs)+1)
                run="RUN-"+n*16
                runs.append(run)
                return {"production_authorized":False,"core":{"run":{"mode":"DEMO","run_id":run,"incident_id":"INC-CI-INGEST-"+n*32}},
                        "stored_evidence":[{"evidence_id":f"E{n}-{i}","payload_hash":str(i)*64} for i in range(4)]}
            self.assertEqual(clock.document_catalog()["documents"],[])
            for tick in range(1,5): clock.advance(tick,publish)
            scope={P+"APP-PAY",P+"GROUP-FIN"}
            first=clock.historical_documents(runs[0],scope,"Payments latency baseline")
            self.assertEqual(first["state"],"HISTORICAL_LOGICAL_VERSION")
            self.assertEqual(first["logical_tick"],3)
            self.assertEqual([x["id"] for x in first["citations"]],["ENT-DOC-001","ENT-DOC-003"])
            self.assertEqual(first["citations"][0]["version"],2)
            for tick in range(5,9): clock.advance(tick,publish)
            clock=EnterpriseClock(root)
            second=clock.historical_documents(runs[1],scope,"Payments latency baseline")
            self.assertEqual(second["citations"][0]["version"],3)
            self.assertNotEqual(first["citations"][0]["sha256"],second["citations"][0]["sha256"])
            self.assertEqual(clock.historical_documents(runs[0],scope,"Payments latency baseline"),first)
            self.assertEqual(clock.historical_documents(runs[1],{P+"APP-HR"},"Payments latency")[ "citations"][0]["id"],"ENT-DOC-004")
            self.assertEqual(clock.historical_documents("RUN-"+"F"*16,scope,"Payments")["state"],"UNBOUND_LEGACY")
            catalog=clock.document_catalog()
            self.assertEqual(len(catalog["documents"]),10)
            for row in catalog["documents"]:
                self.assertEqual(row["sha256"],digest({k:v for k,v in row.items() if k!="sha256"}))
            with closing(clock.connect()) as db,db:
                db.execute("UPDATE corpus SET payload='{}' WHERE doc_id='ENT-DOC-001' AND version=2")
            with self.assertRaises(ValueError): clock.document_catalog()
    def test_pre_e7_not_fabricated(self):
        with tempfile.TemporaryDirectory() as root:
            clock=EnterpriseClock(root)
            def publish(rows):
                return {"production_authorized":False,"core":{"run":{"mode":"DEMO","run_id":"RUN-"+"A"*16,"incident_id":"INC-CI-INGEST-"+"a"*32}},
                        "stored_evidence":[{"evidence_id":f"E{i}","payload_hash":str(i)*64} for i in range(4)]}
            for tick in range(1,4): clock.advance(tick,publish)
            with closing(clock.connect()) as db,db:
                db.execute("DELETE FROM corpus")
            clock.advance(4,publish)
            self.assertEqual(clock.historical_documents("RUN-"+"A"*16,{P+"APP-PAY"},"latency"),{"state":"PRE_E7_UNAVAILABLE","logical_tick":3,"citations":[]})
            self.assertTrue(all(d["valid_from_tick"]==4 for d in clock.document_catalog()["documents"]))

if __name__=="__main__": unittest.main()
