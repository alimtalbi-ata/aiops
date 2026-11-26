import runpy
import tempfile
import unittest
from pathlib import Path
from enterprise_context import P, normalize, validate_telemetry
from enterprise_clock import EnterpriseClock
from ingestion_demo import ingest
from test_enterprise_context import graph

COLLECTOR=Path(__file__).resolve().parent.parent/"kit"/"poc-technical-observed.py"

class TechnicalTelemetryTest(unittest.TestCase):
    def test_real_bounded_collector_and_scope(self):
        with tempfile.TemporaryDirectory() as root:
            batches=runpy.run_path(str(COLLECTOR))["collect"](root)
            self.assertEqual(list(Path(root).iterdir()),[])
            self.assertEqual(len(batches),4)
            g=graph()
            for rows in batches:
                self.assertEqual(len(rows),3)
                result=ingest(rows)
                self.assertEqual(len(result["incidents"]),1)
                for row in rows:
                    g.validate_signal(row["resource"],normalize(row["enterprise"],row["kind"]))
                metric=rows[0]["enterprise"]["telemetry"]
                self.assertEqual(validate_telemetry(metric),metric)
                for bad in (dict(metric,value=True),dict(metric,value=float("nan")),dict(metric,unit="invalid"),dict(metric,method="unknown")):
                    with self.assertRaises(ValueError): validate_telemetry(bad)
                if rows[0]["resource"]!=P+"DB-PAY":
                    with self.assertRaises(ValueError):
                        g.validate_signal(P+"DB-PAY",dict(rows[0]["enterprise"],asset_id=P+"DB-PAY"))
                mixed=dict(rows[0],observation={"metric":"latency_ms","phase":"baseline","value":10})
                with self.assertRaises(ValueError): ingest([mixed])

    def test_retry_after_partial_publication(self):
        with tempfile.TemporaryDirectory() as root:
            clock=EnterpriseClock(root)
            clock.advance(1,lambda _:self.fail("nominal must not publish"))
            batches=runpy.run_path(str(COLLECTOR))["collect"](root)
            collected=[]
            def collect():
                collected.append(1)
                return batches
            calls=[]
            def publish(rows):
                index=next(i for i,b in enumerate(batches,1) if b==rows)
                calls.append(index)
                if index==2 and calls.count(2)==1:
                    raise RuntimeError("interrupted")
                return {"production_authorized":False,"core":{"run":{"mode":"DEMO","run_id":"RUN-"+str(index)*16,"incident_id":"INC-CI-INGEST-"+str(index)*32}},
                        "stored_evidence":[{"evidence_id":f"E{index}-{i}","payload_hash":str(i)*64} for i in range(3)]}
            with self.assertRaises(RuntimeError): clock.capture_technical(1,collect,publish)
            clock=EnterpriseClock(root)
            self.assertEqual(clock.status()["latest"]["technical_capture"]["state"],"PENDING")
            with self.assertRaises(ValueError): clock.advance(2,publish)
            complete=clock.capture_technical(1,collect,publish)
            self.assertEqual(complete,clock.capture_technical(1,collect,publish))
            self.assertEqual(len(collected),1)
            self.assertEqual(len(complete["incidents"]),4)
            clock.advance(2,publish)
            self.assertEqual(EnterpriseClock(root).status()["recent"][0]["technical_capture"],complete)

if __name__=="__main__": unittest.main()
