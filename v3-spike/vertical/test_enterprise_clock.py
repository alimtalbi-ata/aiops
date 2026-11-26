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
    def test_reject_symlink_directory(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as other:
            (Path(root)/"enterprise-e2").symlink_to(other,target_is_directory=True)
            with self.assertRaises(ValueError): EnterpriseClock(root)

if __name__=="__main__": unittest.main()
