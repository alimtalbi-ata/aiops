import sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"app"))
from policy import autonomy_store as store
from policy.execution_fence import reserve

class FenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old=store.PATH
        store.PATH=Path(self.temp.name)/"fence.sqlite3"
    def tearDown(self):
        store.PATH=self.old
        self.temp.cleanup()
    def test_default_stop_prevents_auto(self):
        result=reserve("op-1",0,"AUTONOMOUS_REMEDIATION")
        self.assertFalse(result["admitted"])
        self.assertEqual(result["reason"],"AUTONOMY_SUSPENDED")
    def test_stale_revision_rejected_after_stop_commit(self):
        store.set_mode("NORMAL","test","Test authorized sandbox policy",0)
        self.assertTrue(reserve("first",1,"AUTONOMOUS_REMEDIATION")["admitted"])
        store.set_mode("STOP_AUTO","test","Emergency incident response stop",1)
        blocked=reserve("second",1,"AUTONOMOUS_REMEDIATION")
        self.assertFalse(blocked["admitted"])
        self.assertEqual(blocked["reason"],"STALE_POLICY_REVISION")
    def test_duplicate_never_replayed(self):
        store.set_mode("NORMAL","test","Test sandbox normal admission",0)
        self.assertTrue(reserve("same",1,"STANDARD_CHANGE")["admitted"])
        self.assertEqual(reserve("same",1,"STANDARD_CHANGE")["reason"],"DUPLICATE_OPERATION")
    def test_reserved_does_not_mean_live_execution(self):
        store.set_mode("FREEZE","test","Authorized sandbox freeze test",0)
        allowed=reserve("routine",1,"ROUTINE_PREAPPROVED")
        self.assertTrue(allowed["admitted"])
        self.assertFalse(allowed["execution_allowed"])
        self.assertEqual(reserve("auto",1,"AUTONOMOUS_REMEDIATION")["reason"],"FREEZE_RESTRICTS_OPERATION")
    def test_policy_unavailable_fails_closed(self):
        store.PATH=Path(self.temp.name)/"invalid"
        store.PATH.write_text("not a directory")
        store.PATH=store.PATH/"fence.sqlite3"
        result=reserve("op",0,"AUTONOMOUS_REMEDIATION")
        self.assertFalse(result["admitted"])
        self.assertEqual(result["reason"],"POLICY_STORE_UNAVAILABLE")
if __name__=="__main__":unittest.main()
