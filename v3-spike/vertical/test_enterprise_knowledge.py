import tempfile
import unittest
from contextlib import closing
from enterprise_clock import EnterpriseClock
from enterprise_context import P

class KnowledgeTest(unittest.TestCase):
    def test_source_scope_and_temporal_isolation(self):
        with tempfile.TemporaryDirectory() as root:
            clock=EnterpriseClock(root)
            runs=[]
            def publish(rows):
                n=str(len(runs)+1)
                run="RUN-"+n*16
                runs.append(run)
                return {"production_authorized":False,"core":{"run":{"mode":"DEMO","run_id":run,"incident_id":"INC-CI-INGEST-"+n*32}},
                        "stored_evidence":[{"evidence_id":f"E{n}-{i}","payload_hash":str(i)*64} for i in range(4)]}
            scope={P+"APP-PAY"}
            for tick in range(1,4): clock.advance(tick,publish)
            early=clock.historical_documents(runs[0],scope,"Payments latency")["lifecycle_citations"]
            self.assertEqual([x["kind"] for x in early],["CHANGE"])
            for tick in range(4,9):
                step=clock.advance(tick,publish)
                self.assertEqual(clock.advance(tick,publish),step)
            clock=EnterpriseClock(root)
            catalog=clock.knowledge_catalog()["documents"]
            self.assertEqual(len(catalog),6)
            self.assertEqual(clock.historical_documents(runs[0],scope,"Payments latency")["lifecycle_citations"],early)
            later=clock.historical_documents(runs[1],scope,"Payments latency")["lifecycle_citations"]
            self.assertEqual({x["valid_from_tick"] for x in later},{2,4,6})
            self.assertEqual(len(later),4)
            self.assertTrue(all(not x["observed_evidence"] for x in later))
            self.assertEqual({x["source"]["run_id"] for x in later if x["kind"]!="CHANGE"},{runs[0]})
            self.assertEqual(clock.historical_documents(runs[1],{P+"APP-HR"},"Payments latency")["lifecycle_citations"],[])
            for row in catalog:
                if row["kind"]!="CHANGE":
                    self.assertEqual(len(row["source"]["evidence_refs"]),4)
                    self.assertIn(row["source"]["run_id"],runs)
            with closing(clock.connect()) as db,db:
                db.execute("UPDATE knowledge SET payload='{}' WHERE valid_from_tick=8")
            with self.assertRaises(ValueError): clock.knowledge_catalog()

if __name__=="__main__": unittest.main()
