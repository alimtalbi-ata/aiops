import tempfile
import unittest
from contextlib import closing
from enterprise_clock import EnterpriseClock, model
from enterprise_episodes import modeled, validate_graph
from test_enterprise_context import graph

class EpisodeTest(unittest.TestCase):
    def test_graph_and_model(self):
        g=graph()
        rows=[r for tick in range(1,9) for r in modeled(model(tick))]
        validate_graph(rows,g)
        self.assertEqual(len(rows),32)
        self.assertEqual(len({r["episode_id"] for r in rows}),4)
        self.assertEqual(len({r["episode_type"] for r in rows}),4)
        self.assertTrue(all(not r["causality_established"] and not r["observed_recovery_established"] for r in rows))
        lyon=[r for r in rows if r["scenario"]=="LYON_INTERMITTENT"]
        self.assertEqual([r["tick"] for r in lyon if r["phase"]=="RECURRENCE"],[4,6])
        self.assertEqual([r["observations"][0]["value"] for r in lyon],[0,20,0,25,0,65,5,0])
        individual=[r for r in rows if r["scenario"]=="INDIVIDUAL_FINANCE" and r["phase"]=="ONSET"][0]
        self.assertEqual(individual["resources"],["NODE-CI-ENT-PC-FIN-01","NODE-CI-ENT-USER-FIN-01"])
        g.edges.remove(("NODE-CI-ENT-DB-PAY","NODE-CI-ENT-STORAGE-PAR","requires"))
        with self.assertRaises(ValueError): validate_graph(rows,g)

    def test_durable_timeline_and_receipts(self):
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
            receipts={}
            for tick in range(1,9):
                clock.advance(tick,publish)
                for item in clock.capture_scenarios(tick,publish)["incidents"]:
                    receipts[item["scenario_id"]]=item
                clock=EnterpriseClock(root)
            data=clock.episode_timeline()
            self.assertEqual(len(data["records"]),32)
            self.assertEqual(data["unavailable_pre_e12_ticks"],[])
            links=[link for row in data["records"] for link in row["related_cases"]]
            self.assertEqual(len(links),8)
            for link in links:
                self.assertEqual(link["evidence_refs"],receipts[link["scenario_id"]]["evidence"])
                self.assertEqual(link["run_id"],receipts[link["scenario_id"]]["run_id"])
            self.assertEqual(data,EnterpriseClock(root).episode_timeline())
            with closing(clock.connect()) as db,db:
                db.execute("UPDATE episodes SET payload='[]' WHERE tick=8")
            with self.assertRaises(ValueError): clock.episode_timeline()

if __name__=="__main__": unittest.main()
