import pathlib
import tempfile
import unittest
from unittest.mock import patch
import importlib.util

PATH = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "existing_host_task_executor.py"
spec = importlib.util.spec_from_file_location("task_executor", PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class TaskExecutorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        (self.root / "compose.yml").write_text("services: {}\n")
    def tearDown(self):
        self.temp.cleanup()
    def test_read_only_dry_run(self):
        result = mod.execute({"kind":"compose_status"}, self.root, {"core"})
        self.assertTrue(result["dry_run"])
    def test_unknown_rejected(self):
        with self.assertRaises(ValueError):
            mod.execute({"kind":"shell","command":"id"}, self.root, {"core"})
    def test_unlisted_service_rejected(self):
        with self.assertRaises(ValueError):
            mod.execute({"kind":"service_logs","service":"unknown"}, self.root, {"core"})
    def test_deploy_requires_sha_and_approval(self):
        with self.assertRaises(ValueError):
            mod.execute({"kind":"deploy_service","service":"core"}, self.root, {"core"})
    def test_deploy_fails_closed_even_approved(self):
        with self.assertRaises(ValueError):
            mod.execute({"kind":"deploy_service","service":"core","sha":"a"*40,"approval":"operator-approved"}, self.root, {"core"}, False)
    @patch.object(mod.subprocess, "run")
    def test_no_shell(self, run):
        run.return_value.returncode = 0
        result = mod.execute({"kind":"compose_validate"}, self.root, {"core"}, False)
        self.assertTrue(result["ok"])
        self.assertIsInstance(run.call_args.args[0], list)

if __name__ == "__main__":
    unittest.main()
