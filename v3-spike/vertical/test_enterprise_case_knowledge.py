import tempfile
import unittest
from contextlib import closing
from enterprise_clock import EnterpriseClock
from enterprise_context import P, digest
from enterprise_scenarios import CATALOG

class CaseKnowledgeTest(unittest.TestCase):
    def test_all_cases_historical_scope_and_restore(self):
        with tempfile.TemporaryDirectory() as root:
            clock=EnterpriseClock(root)
            runs={}
            def publish(rows):
                key=rows[0]["id"]
                if key not in runs:
                    n=f"{len(runs)+1:016X}"
                    runs[key]={"production_authorized":False,"core":{"run":{"mode":"DEMO","run_id":"RUN-"+n,"incident_id":"INC-CI-INGEST-"+n.lower()*2}},
                               "stored_evidence":[{"evidence_id":n+str(i),"payload_hash":str(i)*64} for i in range(4)]}
                return runs[key]
            receipts=[]
            for tick in range(1,9):
                clock.advance(tick,publish)
                capture=clock.capture_scenarios(tick,publish)
                receipts.extend(capture["incidents"])
                self.assertEqual(clock.case_catalog()["total_documents"],(tick-1)*2)
            before=clock.case_catalog()
            self.assertEqual(before["total_documents"],14)
            clock=EnterpriseClock(root)
            self.assertEqual(clock.case_catalog(),before)
            clock.advance(9,publish)
            catalog=clock.case_catalog()
            self.assertEqual(catalog["total_documents"],16)
            self.assertEqual({d["scenario_id"] for d in catalog["documents"]},{d[0] for d in CATALOG})
            self.assertEqual(len({d["family"] for d in catalog["documents"]}),7)
            by_run={r["run_id"]:r for r in receipts}
            for doc in catalog["documents"]:
                source=doc["source"]
                self.assertEqual(source["logical_tick"]+1,doc["valid_from_tick"])
                self.assertEqual(source["evidence_refs"],by_run[source["run_id"]]["evidence"])
                self.assertFalse(doc["observed_evidence"])
                self.assertEqual(doc["sha256"],digest({k:v for k,v in doc.items() if k!="sha256"}))
                old=clock.historical_documents(source["run_id"],set(doc["scope"]),doc["title"])["case_retrieval"]
                self.assertNotIn(doc["id"],{x["id"] for x in old["citations"]})
            again=clock.capture_scenarios(9,publish)
            wan=again["incidents"][0]["run_id"]
            found=clock.historical_documents(wan,{P+"WAN"},"packet loss WAN")["case_retrieval"]
            self.assertEqual(found["citations"][0]["scenario_id"],"WAN_LOSS")
            self.assertEqual(found["citations"][0]["source"]["run_id"],receipts[0]["run_id"])
            self.assertEqual(clock.historical_documents(wan,{P+"APP-HR"},"packet loss WAN")["case_retrieval"]["state"],"NO_MATCH")
            fin=next(d for d in catalog["documents"] if d["scenario_id"]=="FIN_DEVICE_FAILURE")
            fin_scope=set(fin["scope"])
            self.assertIn(P+"USER-FIN-01",fin_scope)
            self.assertEqual(clock.historical_documents(wan,fin_scope-{P+"USER-FIN-01"},"Finance workstation")["case_retrieval"]["state"],"NO_MATCH")
            self.assertEqual(clock.historical_documents(wan,(fin_scope-{P+"USER-FIN-01"})|{P+"USER-FIN-02"},"Finance workstation")["case_retrieval"]["state"],"NO_MATCH")
            correct=clock.historical_documents(wan,fin_scope,"Finance workstation")["case_retrieval"]
            self.assertEqual(correct["citations"][0]["id"],fin["id"])
            crm=next(d for d in catalog["documents"] if d["scenario_id"]=="CRM_TIMEOUT")
            self.assertEqual(clock.historical_documents(wan,{P+"ASSET-PAR","NODE-CI-ROOT",P+"APP-PAY"},"CRM timeout")["case_retrieval"]["state"],"NO_MATCH")
            with closing(clock.connect()) as db,db:
                db.execute("UPDATE case_knowledge SET payload='{}' WHERE doc_id=?",(crm["id"],))
            with self.assertRaises(ValueError): clock.case_catalog()

if __name__=="__main__": unittest.main()
