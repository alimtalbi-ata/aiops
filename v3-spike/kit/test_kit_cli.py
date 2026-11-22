"""No Docker invocation or filesystem mutation; synthetic planner tests."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).with_name("kit_cli.py")
spec = importlib.util.spec_from_file_location("kit_cli", MODULE)
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)

class KitCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "docker-compose.yml").write_text("services: {}\n")

    def test_seven_actions_are_defined(self):
        self.assertEqual(len(cli.ACTIONS), 7)
        for action in cli.ACTIONS:
            receipt = cli.plan(action, self.root)
            self.assertEqual(receipt["mode"], "DRY_RUN_ONLY")
            self.assertFalse(receipt["runtime_attested"])
            self.assertFalse(receipt["host_mutated"])

    def test_one_canonical_compose_in_every_command(self):
        for action in cli.ACTIONS:
            receipt = cli.plan(action, self.root)
            for command in receipt["commands_not_executed"]:
                self.assertEqual(command[:3], ["docker", "compose", "--file"])
                self.assertEqual(command[3], str(self.root / "docker-compose.yml"))

    def test_destructive_operations_fail_closed(self):
        for action in ("backup", "restore", "rollback"):
            receipt = cli.plan(action, self.root)
            self.assertTrue(receipt["blocked"])
            self.assertEqual(receipt["commands_not_executed"], [])
            self.assertIn("snapshot", receipt["reason"])

    def test_missing_compose_rejected(self):
        (self.root / "docker-compose.yml").unlink()
        with self.assertRaises(ValueError):
            cli.plan("install", self.root)

    def test_symlink_compose_rejected(self):
        (self.root / "docker-compose.yml").unlink()
        target = self.root / "other.yml"
        target.write_text("services: {}\n")
        (self.root / "docker-compose.yml").symlink_to(target)
        with self.assertRaises(ValueError):
            cli.plan("install", self.root)

    def test_invalid_action_rejected(self):
        with self.assertRaises(ValueError):
            cli.plan("shell", self.root)

    def test_cli_exit_codes_and_json(self):
        ok = subprocess.run([sys.executable, str(MODULE), "preflight", "--kit-dir", str(self.root)],
                            capture_output=True, text=True, check=False)
        self.assertEqual(ok.returncode, 0)
        self.assertEqual(json.loads(ok.stdout)["action"], "preflight")
        blocked = subprocess.run([sys.executable, str(MODULE), "restore", "--kit-dir", str(self.root)],
                                 capture_output=True, text=True, check=False)
        self.assertEqual(blocked.returncode, 3)
        self.assertTrue(json.loads(blocked.stdout)["blocked"])

if __name__ == "__main__":
    unittest.main()
