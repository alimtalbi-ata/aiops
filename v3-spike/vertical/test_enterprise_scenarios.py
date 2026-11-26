import tempfile
import unittest
from enterprise_clock import EnterpriseClock, model
from enterprise_context import P, normalize
from enterprise_scenarios import CATALOG, batches, describe, root_of
from ingestion_demo import ingest
from test_enterprise_context import graph

class ScenarioTest(unittest.TestCase):
    def test_all_domains_and_scopes(self):
        g=graph()
        seen=set()
        for tick in range(1,9):
            for rows in batches(model(tick)):
                meta=rows[0]["enterprise"]["scenario"]
                ident=meta["scenario_id"]
                seen.add(ident)
                self.assertEqual(len(rows),4)
                for row in rows:
                    g.validate_signal(row["resource"],normalize(row["enterprise"],row["kind"]))
                incident=ingest(rows)["incidents"][0]
                self.assertEqual(incident["alert_count"],4)
                self.assertTrue(all("observation" not in e and e["enterprise"]["scenario"]["scenario_id"]==ident for e in incident["evidence"]))
                invalid=dict(rows[0],enterprise=dict(rows[0]["enterprise"],scenario=dict(meta,value=True)))
                with self.assertRaises(ValueError): ingest([invalid])
                wrong=dict(rows[0],enterprise=dict(rows[0]["enterprise"],asset_id=P+"IDENTITY"))
                if rows[0]["resource"]!=P+"IDENTITY":
                    with self.assertRaises(ValueError): ingest([wrong])
        self.assertEqual(len(seen),16)
        self.assertEqual(len({x["family"] for x in describe()}),7)
        self.assertEqual(batches(model(1))[0][0]["enterprise"]["scenario"]["value"],0)
        self.assertEqual(g.scope(P+"PC-HR-01")["users"],{P+"USER-HR-01"})
        for tick in range(1,9):
            original=batches(model(tick))
            self.assertEqual(original,batches(model(tick)))
            self.assertEqual(len({rows[0]["resource"] for rows in original}),2)
            for rows in original:
                self.assertEqual({r["enterprise"]["scenario"]["phase"] for r in rows},{"baseline","incident","log","event"})
                for r in rows:
                    self.assertTrue(r["synthetic"])
                    self.assertEqual(r["tenant"],"synthetic-demo")
                raw=rows[0]["enterprise"]
                for bad in (dict(raw,scenario=dict(raw["scenario"],tick=tick+1)),dict(raw,scenario=dict(raw["scenario"],unit="invalid")),dict(raw,scenario=dict(raw["scenario"],classification="MEASURED"))):
                    with self.assertRaises(ValueError): normalize(bad,"metric")

    def test_durable_campaign_and_retry(self):
        with tempfile.TemporaryDirectory() as root:
            clock=EnterpriseClock(root)
            runs={}
            fail=[True]
            def publish(rows):
                key=rows[0]["id"]
                if key.startswith("e10-1-disk_full") and fail[0]:
                    fail[0]=False
                    raise RuntimeError("partial publication")
                if key not in runs:
                    n=f"{len(runs)+1:016X}"
                    runs[key]={"production_authorized":False,"core":{"run":{"mode":"DEMO","run_id":"RUN-"+n,"incident_id":"INC-CI-INGEST-"+n.lower()*2}},
                               "stored_evidence":[{"evidence_id":n+str(i),"payload_hash":str(i)*64} for i in range(4)]}
                return runs[key]
            clock.advance(1,publish)
            with self.assertRaises(RuntimeError): clock.capture_scenarios(1,publish)
            clock=EnterpriseClock(root)
            self.assertEqual(clock.status()["latest"]["scenario_capture"]["state"],"PENDING")
            with self.assertRaises(ValueError): clock.advance(2,publish)
            captures=[]
            for tick in range(1,9):
                if tick>1: clock.advance(tick,publish)
                result=clock.capture_scenarios(tick,publish)
                self.assertEqual(result,clock.capture_scenarios(tick,publish))
                captures.extend(result["incidents"])
                clock=EnterpriseClock(root)
            self.assertEqual(len({r["run_id"] for r in captures}),16)
            self.assertEqual({r["scenario_id"] for r in captures},{r[0] for r in CATALOG})
            first=captures[0]
            history=clock.historical_documents(first["run_id"],{P+"WAN"},"network")
            self.assertEqual(history["logical_tick"],1)
            self.assertEqual([x["id"] for x in history["citations"]],["ENT-DOC-005"])
            self.assertEqual(len(runs),18)
            self.assertEqual(clock.status()["recent"][0]["scenario_capture"]["incidents"][0],first)

if __name__=="__main__": unittest.main()
