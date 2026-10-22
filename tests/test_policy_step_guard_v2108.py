import sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"app"))
from policy import autonomy_store as store
from policy.execution_fence import reserve
from policy.step_guard import validate_step
class FinalStepTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old=store.PATH
        store.PATH=Path(self.tmp.name)/"state.sqlite3"
    def tearDown(self):
        store.PATH=self.old
        self.tmp.cleanup()
    def test_old_reservation_fails_after_stop(self):
        store.set_mode("NORMAL","qa","Test initial policy approval state",0)
        self.assertTrue(reserve("op-a",1,"AUTONOMOUS_REMEDIATION")["admitted"])
        self.assertTrue(validate_step("op-a",1)["valid"])
        store.set_mode("STOP_AUTO","operator","Freeze autonomous work immediately",1)
        result=validate_step("op-a",1)
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"],"STALE_POLICY_REVISION")
    def test_no_reservation_denied(self):
        self.assertEqual(validate_step("absent",0)["reason"],"NO_RESERVATION")
    def test_valid_step_never_enables_live(self):
        store.set_mode("FREEZE","qa","Test routine simulated reservation",0)
        self.assertTrue(reserve("routine",1,"ROUTINE_PREAPPROVED")["admitted"])
        result=validate_step("routine",1)
        self.assertTrue(result["valid"])
        self.assertFalse(result["execution_allowed"])
    def test_storage_error_fails_closed(self):
        bad=Path(self.tmp.name)/"file"
        bad.write_text("x")
        store.PATH=bad/"sqlite.db"
        self.assertEqual(validate_step("x",0)["reason"],"POLICY_STORE_UNAVAILABLE")
if __name__=="__main__":unittest.main()
