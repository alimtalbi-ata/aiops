import importlib.util
import pathlib
import unittest
from unittest.mock import patch

PATH = pathlib.Path(__file__).resolve().parents[2] / "scripts/ops/run_linkage_gate.py"
spec = importlib.util.spec_from_file_location("run_linkage_gate", PATH)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

class GateTests(unittest.TestCase):
    def test_run_id_validation(self):
        self.assertTrue(gate.RUN_RE.fullmatch("RUN-8CA56A39E58944F1"))
        self.assertFalse(gate.RUN_RE.fullmatch("RUN-'; DROP TABLE aiops.runs;--"))
    def test_no_mutating_commands(self):
        with patch.object(gate.subprocess, "run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = '{"run":null}\n'
            gate.pg_query("SELECT json_build_object('run',null)::text;")
            args = run.call_args.args[0]
            self.assertEqual(args[:3], ["docker","exec","-i"])
            self.assertIn("READ ONLY",run.call_args.kwargs["input"])
    def test_external_ticket_is_not_verified(self):
        self.assertIn("NOT_API_VERIFIED", PATH.read_text())
    def test_parser_supports_wrappers(self):
        source = PATH.read_text()
        self.assertIn("('run','data','result')",source)
        self.assertIn("'parse_status':'UNRECOGNIZED'",source)
        self.assertIn('"AUTH_REQUIRED"',source)
    def test_no_side_effectful_http(self):
        source=PATH.read_text()
        self.assertNotIn("urllib.request.Request(",source)
        self.assertNotIn("method='POST'",source)
        self.assertNotIn("docker restart",source)

if __name__ == "__main__":
    unittest.main()
