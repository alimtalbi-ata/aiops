import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

PATH=Path(__file__).resolve().parents[2]/"scripts/ops/publish_platform_evidence.py"
spec=importlib.util.spec_from_file_location("publish_platform_evidence",PATH)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class TestEvidence(unittest.TestCase):
    def test_schema_and_allowlist(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"report.json"
            p.write_text(json.dumps({"schema":"aiops2-platform-readiness-v1","read_only":True,
              "utc":"2026-11-08T12:00:00+00:00","verdict":"HOLD","secret":"MUST_NOT_LEAK",
              "runtime":{"core":{"state":"running","image":"test","Env":["SECRET=abc"],"networks":["control"]}},
              "probes":{"core":{"http":200}}}))
            clean=module.sanitize(p)
            self.assertNotIn("secret",clean)
            self.assertNotIn("Env",clean["runtime"]["core"])
            self.assertEqual(clean["probes"]["core"]["http"],200)
    def test_reject_unknown_schema(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"report.json"
            p.write_text('{"schema":"other","read_only":true}')
            with self.assertRaises(ValueError): module.sanitize(p)
    def test_no_force_push(self):
        self.assertNotIn("--force",PATH.read_text().split('run(["git","push"')[1].split(")",1)[0])
if __name__=="__main__":
    unittest.main()
