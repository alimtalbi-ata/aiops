import tempfile
import unittest
from pathlib import Path
from enterprise_clock import EnterpriseClock, model, batch

class ClockTest(unittest.TestCase):
    def test_restart_outbox_and_next_cycle(self):
        with tempfile.TemporaryDirectory() as root:
            clock=EnterpriseClock(root)
            calls=[]
            def publish(rows):
                calls.append(rows)
                if len(calls)==1:
                    raise RuntimeError("simulated remote failure")
                return {"production_authorized":False,"core":{"run":{"mode":"DEMO","run_id":"RUN-1234567890ABCDEF","incident_id":"INC-CI-INGEST-"+"a"*32}},
                        "stored_evidence":[{"evidence_id":"E"+str(i),"payload_hash":str(i)*64} for i in range(4)]}
            self.assertEqual(clock.status()["current_tick"],0)
            self.assertEqual(clock.advance(1,publish)["phase"],"NOMINAL")
            self.assertEqual(clock.advance(2,publish)["phase"],"CHANGE")
            with self.assertRaises(RuntimeError):
                clock.advance(3,publish)
            clock=EnterpriseClock(root)
            self.assertTrue(clock.status()["pending"])
            with self.assertRaises(ValueError):
                clock.advance(4,publish)
            step=clock.advance(3,publish)
            self.assertEqual(calls[0],calls[1])
            self.assertEqual(step,clock.advance(3,publish))
            self.assertEqual(len(calls),2)
            self.assertEqual(step["publication"]["state"],"PUBLISHED")
            self.assertEqual(clock.advance(4,publish)["phase"],"MODEL_RECOVERY")
            self.assertEqual(EnterpriseClock(root).advance(5,publish)["cycle"],2)
            self.assertEqual(len(EnterpriseClock(root).status()["recent"]),5)
            with self.assertRaises(ValueError):
                clock.advance(3,publish)
            self.assertNotEqual(batch(model(3)),batch(model(7)))
            self.assertEqual((Path(root)/"enterprise-e2"/"world.sqlite3").stat().st_mode & 0o777,0o600)
    def test_measured_outbox_retry(self):
        from copy import deepcopy
        from enterprise_context import P, LYON
        with tempfile.TemporaryDirectory() as root:
            clock=EnterpriseClock(root)
            calls=[]
            def receipt(rows):
                number=1 if rows[0]["resource"]!=LYON else 2
                return {"production_authorized":False,"core":{"run":{"mode":"DEMO","run_id":"RUN-"+str(number)*16,"incident_id":"INC-CI-INGEST-"+str(number)*32}},
                        "stored_evidence":[{"evidence_id":f"E{number}-{i}","payload_hash":str(i)*64} for i in range(4)]}
            for n in range(1,4):
                clock.advance(n,receipt)
            paris=batch(model(3))
            for row in paris[:2]:
                row["enterprise"]["measurement"]={"classification":"MEASURED_SYNTHETIC_LAB","samples_ms":[row["observation"]["value"]]*5,"method":"HTTP_MONOTONIC_MEDIAN_5"}
            lyon=deepcopy(paris)
            for row in lyon:
                row["resource"]=LYON
                row["id"]="lyon-"+row["id"]
                row["enterprise"].update(asset_id=P+"ASSET-LYO",application_id=P+"APP-HR")
            lyon[2]["enterprise"].update(group_id=P+"GROUP-HR",user_id=P+"USER-HR-01")
            collections=[]
            def collect():
                collections.append(1)
                return [paris,lyon]
            def fail_second(rows):
                calls.append(rows)
                if rows[0]["resource"]==LYON: raise RuntimeError("publication interrupted")
                return receipt(rows)
            with self.assertRaises(RuntimeError):
                clock.capture(3,collect,fail_second)
            clock=EnterpriseClock(root)
            self.assertEqual(clock.status()["latest"]["measured_capture"]["state"],"PENDING")
            with self.assertRaises(ValueError): clock.advance(4,receipt)
            completed=clock.capture(3,collect,receipt)
            self.assertEqual(len(collections),1)
            self.assertEqual(completed,clock.capture(3,collect,receipt))
            self.assertEqual(len(collections),1)
            self.assertEqual(len(completed["incidents"]),2)
            clock.advance(4,receipt)
            self.assertEqual(EnterpriseClock(root).status()["recent"][2]["measured_capture"],completed)

    def test_reject_symlink_directory(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as other:
            (Path(root)/"enterprise-e2").symlink_to(other,target_is_directory=True)
            with self.assertRaises(ValueError): EnterpriseClock(root)

if __name__=="__main__": unittest.main()
