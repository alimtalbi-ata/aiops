import tempfile
import unittest
from contextlib import closing
from enterprise_clock import EnterpriseClock
from enterprise_parametric import plan,validate_graph
from test_enterprise_context import graph

CFG={"seed":42,"horizon":32,"frequency_pct":100,"min_duration":1,"max_duration":5,"max_users":5}

class ParametricTest(unittest.TestCase):
    def test_seed_bounds_and_population(self):
        rows=plan(CFG)
        self.assertEqual(rows,plan(dict(CFG)))
        self.assertNotEqual(rows,plan(dict(CFG,seed=43)))
        self.assertEqual(len(rows),31)
        self.assertEqual(plan(dict(CFG,frequency_pct=0)),[])
        self.assertGreater(len({x["duration_ticks"] for x in rows}),1)
        self.assertEqual({x["severity"] for x in rows},{"warning","critical"})
        self.assertGreater(len({x["family"] for x in rows}),3)
        validate_graph(rows,graph())
        validate_graph(plan(dict(CFG,max_users=1)),graph())
        self.assertTrue(all(len(x["modeled_exposed_user_ids"])==1 for x in plan(dict(CFG,max_users=1))))
        self.assertTrue(all(x["recovery_tick"]<=CFG["horizon"] for x in rows))
        for bad in (dict(CFG,seed=True),dict(CFG,horizon=121),dict(CFG,min_duration=6),dict(CFG,max_users=6)):
            with self.assertRaises(ValueError): plan(bad)

    def test_config_immutable_restart_and_no_extra_publication(self):
        with tempfile.TemporaryDirectory() as root:
            clock=EnterpriseClock(root)
            calls=[]
            def publish(rows):
                calls.append(rows)
                n=str(len(calls))
                return {"production_authorized":False,"core":{"run":{"mode":"DEMO","run_id":"RUN-"+n*16,"incident_id":"INC-CI-INGEST-"+n*32}},
                        "stored_evidence":[{"evidence_id":f"E{n}-{i}","payload_hash":str(i)*64} for i in range(4)]}
            self.assertEqual(clock.parametric_timeline()["state"],"DISABLED")
            cfg=dict(CFG,horizon=8)
            initial=clock.configure_parametric(cfg,graph())
            self.assertEqual(initial["records"],[])
            self.assertEqual(initial,clock.configure_parametric(cfg,graph()))
            with self.assertRaises(ValueError): clock.configure_parametric(dict(cfg,seed=43),graph())
            for tick in range(1,10):
                clock.advance(tick,publish)
                data=clock.parametric_timeline()
                self.assertEqual(data,EnterpriseClock(root).parametric_timeline())
                self.assertTrue(all(r["tick"]<=tick and not r["observed_outage_established"] for r in data["records"]))
            self.assertEqual(len(calls),2)
            self.assertEqual(data["state"],"HORIZON_COMPLETE")
            self.assertEqual(len({r["episode_id"] for r in data["records"]}),7)
            self.assertEqual(sum(r["phase"]=="MODEL_RECOVERY" for r in data["records"]),7)
            self.assertEqual(data["plan_sha256"],initial["plan_sha256"])
            with closing(clock.connect()) as db,db:
                db.execute("UPDATE parametric_ticks SET payload='[]' WHERE tick=1")
            with self.assertRaises(ValueError): clock.parametric_timeline()
        with tempfile.TemporaryDirectory() as root:
            clock=EnterpriseClock(root)
            clock.advance(1,lambda _:self.fail("nominal cannot publish"))
            with self.assertRaises(ValueError): clock.configure_parametric(CFG,graph())

if __name__=="__main__": unittest.main()
