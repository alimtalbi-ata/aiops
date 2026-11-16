import importlib.util,unittest
from pathlib import Path
p=Path(__file__).resolve().parents[1]/"tools/acme_demo_readiness_v297.py"
spec=importlib.util.spec_from_file_location("readiness",p)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
class ReadyTests(unittest.TestCase):
    def test_all_checks_pass(self):
        health={k:"healthy" for k in m.SERVICES}
        checks=m.assess(health,{"/timeline":200},{"required":["ACME-A"],"available":["ACME-A"]})
        self.assertTrue(all(x["status"]=="PASS" for x in checks))
    def test_missing_cmdb_fails(self):
        checks=m.assess({}, {"/timeline":200},{"required":["ACME-B"],"available":[]})
        self.assertIn("ACME-B",str(checks))
        self.assertTrue(any(x["status"]=="FAIL" for x in checks))
    def test_http_failure_fails(self):
        checks=m.assess({k:"healthy" for k in m.SERVICES},{"/copilot":503},
             {"required":[],"available":[]})
        self.assertTrue(any(x["name"]=="http:/copilot" and x["status"]=="FAIL" for x in checks))
if __name__=="__main__":unittest.main()
