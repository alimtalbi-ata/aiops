import os,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"app"))
from policy import main,autonomy_store
class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old=autonomy_store.PATH
        autonomy_store.PATH=Path(self.tmp.name)/"policy.sqlite3"
        self.previous=main.INTERNAL_TOKEN
        main.INTERNAL_TOKEN="isolated-test-token"
    def tearDown(self):
        autonomy_store.PATH=self.old
        main.INTERNAL_TOKEN=self.previous
        self.tmp.cleanup()
    def test_summary_zero_then_one(self):
        auth="Bearer isolated-test-token"
        self.assertEqual(main.simulation_summary(auth)["reservations_recorded"],0)
        autonomy_store.set_mode("NORMAL","operator","Isolated test normal mode",0)
        x=main.SimulationAdmission(operation_id="demo-1",expected_revision=1,operation_class="STANDARD_CHANGE")
        result=main.simulation_reserve(x,auth)
        self.assertTrue(result["admitted"])
        self.assertFalse(result["execution_allowed"])
        self.assertEqual(main.simulation_summary(auth)["reservations_recorded"],1)
    def test_no_production_effect_in_default_stop(self):
        result=main.simulation_reserve(main.SimulationAdmission(operation_id="demo-2",expected_revision=0,operation_class="AUTONOMOUS_REMEDIATION"),"Bearer isolated-test-token")
        self.assertFalse(result["admitted"])
        self.assertFalse(result["execution_allowed"])
    def test_authentication_required(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            main.simulation_summary(None)
        self.assertEqual(ctx.exception.status_code,401)
if __name__=="__main__":unittest.main()
