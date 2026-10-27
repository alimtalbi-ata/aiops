import importlib.util
import pathlib
import unittest

path = pathlib.Path(__file__).resolve().parents[1] / "deploy" / "portal-port-audit.py"
spec = importlib.util.spec_from_file_location("portal_port_audit", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class PortalPortAuditTests(unittest.TestCase):
    def test_expected_port(self):
        self.assertEqual(module.analyze({"services": {"aiops2-portal": {"ports": [{"published": "17777", "target": 777}]}}})["status"], "PASS")
    def test_old_port_is_blocked(self):
        self.assertEqual(module.analyze({"services": {"aiops2-portal": {"ports": [{"published": "7777", "target": 777}]}}})["status"], "BLOCKED")
    def test_missing_portal_is_blocked(self):
        self.assertEqual(module.analyze({"services": {}})["status"], "BLOCKED")
    def test_no_runtime_claim(self):
        self.assertIn("does not prove", module.analyze({"services": {"aiops2-portal": {"ports": ["17777:777"]}}})["note"])

if __name__ == "__main__":
    unittest.main()
