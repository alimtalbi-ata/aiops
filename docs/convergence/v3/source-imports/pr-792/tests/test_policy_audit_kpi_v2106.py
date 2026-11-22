import sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"app"))
from policy import autonomy_store as store
from policy.execution_fence import reserve,summary,decisions
class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old=store.PATH
        store.PATH=Path(self.temp.name)/"policy.sqlite3"
    def tearDown(self):
        store.PATH=self.old
        self.temp.cleanup()
    def test_refusal_and_admission_both_counted(self):
        self.assertEqual(reserve("blocked",0,"AUTONOMOUS_REMEDIATION")["reason"],"AUTONOMY_SUSPENDED")
        store.set_mode("NORMAL","operator","Simulation normal mode for testing",0)
        self.assertTrue(reserve("allowed",1,"STANDARD_CHANGE")["admitted"])
        report=summary()
        self.assertEqual(report["refusals_recorded"],1)
        self.assertEqual(report["reservations_recorded"],1)
        self.assertEqual(len(decisions()),2)
    def test_stale_policy_refusal_audited(self):
        self.assertEqual(reserve("stale",99,"STANDARD_CHANGE")["reason"],"STALE_POLICY_REVISION")
        self.assertEqual(decisions()[0]["reason"],"STALE_POLICY_REVISION")
    def test_empty_report_not_fabricated(self):
        self.assertEqual(summary()["refusals_recorded"],0)
        self.assertEqual(decisions(),[])
if __name__=="__main__":unittest.main()
