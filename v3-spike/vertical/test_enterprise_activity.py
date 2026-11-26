import json
import tempfile
import unittest
from contextlib import closing
from enterprise_clock import EnterpriseClock
from enterprise_context import P, normalize
from test_enterprise_context import graph

class ActivityTest(unittest.TestCase):
    def test_nominal_alert_incident_and_restart(self):
        with tempfile.TemporaryDirectory() as root:
            clock=EnterpriseClock(root)
            calls=[]
            def publish(rows):
                calls.append(rows)
                number=str(len(calls))
                return {"production_authorized":False,"core":{"run":{"mode":"DEMO","run_id":"RUN-"+number*16,"incident_id":"INC-CI-INGEST-"+number*32}},
                        "stored_evidence":[{"evidence_id":f"E{number}-{i}","payload_hash":str(i)*64} for i in range(4)]}
            for tick in range(1,9):
                step=clock.advance(tick,publish)
                self.assertEqual(step,clock.advance(tick,publish))
                clock=EnterpriseClock(root)
            self.assertEqual(len(calls),2)
            data=clock.activity()
            self.assertEqual(data["current_tick"],8)
            self.assertEqual(len(data["records"]),24)
            self.assertEqual(data["unavailable_pre_e6_ticks"],[])
            g=graph()
            counts={}
            for row in data["records"]:
                counts[row["disposition"]]=counts.get(row["disposition"],0)+1
                g.validate_signal(row["resource"],normalize(row["scope"],"metric"))
                self.assertEqual([x["kind"] for x in row["signals"]],["metric","log","event"])
                self.assertFalse(row["observed_outage_established"])
                self.assertEqual(bool(row["run_id"]),row["disposition"]=="INCIDENT_LINKED")
                if row["scope"]["application_id"]==P+"APP-HR":
                    self.assertEqual(row["disposition"],"OBSERVATION_ONLY")
            self.assertEqual(counts,{"OBSERVATION_ONLY":20,"ALERT_ONLY":2,"INCIDENT_LINKED":2})
            self.assertTrue(any(r["scope"]["user_id"]==P+"USER-DIRECT-01" and "group_id" not in r["scope"] for r in data["records"]))
            self.assertEqual(data,EnterpriseClock(root).activity())
            with closing(clock.connect()) as db,db:
                db.execute("UPDATE activity SET payload='[]' WHERE tick=8")
            with self.assertRaises(ValueError): clock.activity()

    def test_pending_and_pre_e6_gap(self):
        with tempfile.TemporaryDirectory() as root:
            clock=EnterpriseClock(root)
            for tick in (1,2): clock.advance(tick,lambda _:self.fail("nominal cannot publish"))
            with closing(clock.connect()) as db,db:
                db.execute("DELETE FROM activity WHERE tick=1")
            def fail(_): raise RuntimeError("interrupted")
            with self.assertRaises(RuntimeError): clock.advance(3,fail)
            data=EnterpriseClock(root).activity()
            self.assertEqual(data["unavailable_pre_e6_ticks"],[1])
            pending=[r for r in data["records"] if r["disposition"]=="PENDING_INCIDENT"]
            self.assertEqual(len(pending),1)
            self.assertIsNone(pending[0]["run_id"])
            self.assertEqual(pending[0]["scope"]["application_id"],P+"APP-PAY")

if __name__=="__main__": unittest.main()
