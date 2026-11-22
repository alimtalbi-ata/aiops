import sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"app"))
from policy import autonomy_store as store
from policy.acme_walkthrough import run_simulation
class WalkthroughTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old=store.PATH
        store.PATH=Path(self.tmp.name)/"isolated.sqlite3"
    def tearDown(self):
        store.PATH=self.old
        self.tmp.cleanup()
    def test_stop_prevents_next_step(self):
        r=run_simulation()
        events={x["step"]:x for x in r["events"]}
        self.assertTrue(events["POLICY_RESERVATION"]["admitted"])
        self.assertEqual(events["FINAL_POLICY_CHECK"]["reason"],"STALE_POLICY_REVISION")
        self.assertFalse(events["FINAL_POLICY_CHECK"]["execution_allowed"])
        self.assertEqual(r["live_effects"],0)
    def test_trace_and_kpis(self):
        r=run_simulation()
        self.assertEqual([x["mode"] for x in r["policy_history"]],["STOP_AUTO","NORMAL"])
        self.assertEqual(r["policy_kpis"]["reservations_recorded"],1)
        self.assertFalse(r["model_inference_performed"])
        self.assertTrue(r["decision_audit"])
    def test_requires_isolated_database(self):
        run_simulation()
        with self.assertRaises(RuntimeError):run_simulation()
if __name__=="__main__":unittest.main()
