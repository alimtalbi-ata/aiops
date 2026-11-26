import tempfile
import unittest
from collections import Counter
from contextlib import closing
from enterprise_clock import EnterpriseClock, model
from enterprise_triage import modeled, evaluate, validate_graph
from test_enterprise_context import graph

EXPECTED=(
 "UNCORROBORATED_ALERT","INCIDENT_CANDIDATE","SECURITY_REVIEW","MAINTENANCE_REVIEW",
 "CONTRADICTORY_SIGNALS","INSUFFICIENT_FRESH_DATA","UNCORROBORATED_ALERT","NOMINAL_OBSERVATION",
 "INSUFFICIENT_FRESH_DATA","INCIDENT_CANDIDATE","INCIDENT_CANDIDATE","UNCORROBORATED_ALERT",
 "SECURITY_REVIEW","UNCORROBORATED_ALERT","INCIDENT_CANDIDATE","NOMINAL_OBSERVATION",
)

class TriageTest(unittest.TestCase):
    def test_scenarios_and_independent_labels(self):
        rows=[r for tick in range(1,9) for r in modeled(model(tick))]
        validate_graph(rows,graph())
        self.assertEqual(len({r["scenario_id"] for r in rows}),16)
        self.assertEqual(tuple(r["assessment"]["disposition"] for r in rows),EXPECTED)
        self.assertEqual(len(Counter(EXPECTED)),7)
        for r in rows:
            a=r["assessment"]
            self.assertEqual(a,evaluate(r["signals"],r["maintenance_active"],r["security_review"]))
            self.assertEqual(a,evaluate(list(reversed(r["signals"])),r["maintenance_active"],r["security_review"]))
            self.assertFalse(a["automatic_incident_created"])
            self.assertFalse(a["production_authorized"])
            self.assertFalse(a["compromise_established"])
            self.assertEqual(a["root_cause"],"UNKNOWN")
        self.assertEqual(rows[6]["assessment"]["unique_count"],1)
        self.assertEqual(rows[6]["assessment"]["abnormal_sources"],1)
        self.assertEqual(rows[5]["assessment"]["fresh_count"],0)
        self.assertTrue(rows[9]["maintenance_active"])
        self.assertEqual(rows[9]["assessment"]["disposition"],"INCIDENT_CANDIDATE")
        bad=dict(rows[0]["signals"][0],classification="MEASURED")
        with self.assertRaises(ValueError): evaluate([bad],False,False)

    def test_same_source_cannot_corroborate(self):
        s=modeled(model(1))[0]["signals"][0]
        self.assertEqual(evaluate([s,dict(s,kind="log")],False,False)["disposition"],"UNCORROBORATED_ALERT")
        self.assertEqual(evaluate([s,dict(s,source="other",kind="log",age_seconds=121)],False,False)["disposition"],"UNCORROBORATED_ALERT")

    def test_restart_and_tamper(self):
        with tempfile.TemporaryDirectory() as root:
            clock=EnterpriseClock(root)
            calls=[]
            def publish(rows):
                calls.append(rows)
                n=str(len(calls))
                return {"production_authorized":False,"core":{"run":{"mode":"DEMO","run_id":"RUN-"+n*16,"incident_id":"INC-CI-INGEST-"+n*32}},
                        "stored_evidence":[{"evidence_id":f"E{n}-{i}","payload_hash":str(i)*64} for i in range(4)]}
            for tick in range(1,9):
                clock.advance(tick,publish)
                before=clock.triage_timeline()
                clock.advance(tick,publish)
                clock=EnterpriseClock(root)
                self.assertEqual(clock.triage_timeline(),before)
            self.assertEqual(len(calls),2) # only existing E2 degraded runs
            self.assertEqual(len(before["records"]),16)
            self.assertEqual(before["unavailable_pre_e13_ticks"],[])
            with closing(clock.connect()) as db,db:
                db.execute("UPDATE triage SET payload='[]' WHERE tick=8")
            with self.assertRaises(ValueError): clock.triage_timeline()

if __name__=="__main__": unittest.main()
