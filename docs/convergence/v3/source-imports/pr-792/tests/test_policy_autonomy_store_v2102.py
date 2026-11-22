import importlib.util,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
p=Path(__file__).resolve().parents[1]/"app/policy/autonomy_store.py"
spec=importlib.util.spec_from_file_location("autonomy_store_test",p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class StateTests(unittest.TestCase):
    def setUp(self):
        self.dir=tempfile.TemporaryDirectory()
        self.original=m.PATH
        m.PATH=Path(self.dir.name)/"autonomy.sqlite3"
    def tearDown(self):
        m.PATH=self.original
        self.dir.cleanup()
    def test_safe_default(self):
        self.assertEqual(m.status()["mode"],"STOP_AUTO")
        self.assertEqual(m.status()["revision"],0)
    def test_revisioned_audit(self):
        s=m.set_mode("STOP_AUTO","operator","Urgent stop for payroll freeze",0)
        self.assertEqual(s["revision"],1)
        self.assertEqual(m.history()[0]["actor"],"operator")
        with self.assertRaises(RuntimeError):
            m.set_mode("STOP_AUTO","operator","Replay with stale revision",0)
    def test_invalid_reason_rejected(self):
        with self.assertRaises(ValueError):
            m.set_mode("NORMAL","admin","short",0)
    def test_bad_storage_fails_closed(self):
        m.PATH=Path(self.dir.name)/"file"
        m.PATH.write_text("not a directory")
        m.PATH=m.PATH/"sqlite.db"
        s=m.status()
        self.assertEqual(s["mode"],"STOP_AUTO")
        self.assertFalse(s["healthy"])
if __name__=="__main__":unittest.main()
