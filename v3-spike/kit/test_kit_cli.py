"""Synthetic CLI planner tests: no Docker invocation, no host mutation."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

MODULE = Path(__file__).with_name("kit_cli.py")
spec = importlib.util.spec_from_file_location("kit_cli", MODULE)
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)
DIGEST = "registry.example.invalid/fixture@sha256:" + "a" * 64
ENV = {"GAMMA_IMAGE": DIGEST, "CORE_IMAGE": DIGEST, "DEMO_IMAGE": DIGEST}

class KitCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.compose = self.root / "docker-compose.yml"
        self.compose.write_text(MODULE.with_name("docker-compose.yml").read_text(encoding="utf-8"), encoding="utf-8")
        self.patch = mock.patch.dict(os.environ, ENV)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_seven_actions_are_defined(self):
        self.assertEqual(len(cli.ACTIONS), 7)
        for action in cli.ACTIONS:
            receipt = cli.plan(action, self.root)
            self.assertEqual(receipt["mode"], "DRY_RUN_ONLY")
            self.assertFalse(receipt["runtime_attested"])
            self.assertFalse(receipt["host_mutated"])

    def test_one_canonical_compose_in_every_command(self):
        for action in cli.ACTIONS:
            for command in cli.plan(action, self.root)["commands_not_executed"]:
                self.assertEqual(command[:3], ["docker", "compose", "--file"])
                self.assertEqual(command[3], str(self.compose))

    def test_destructive_operations_fail_closed(self):
        for action in ("backup", "restore", "rollback"):
            receipt = cli.plan(action, self.root)
            self.assertTrue(receipt["blocked"])
            self.assertEqual(receipt["commands_not_executed"], [])
            self.assertIn("snapshot", receipt["reason"])

    def test_missing_compose_rejected(self):
        self.compose.unlink()
        with self.assertRaises(ValueError):
            cli.plan("install", self.root)

    def test_symlink_compose_rejected(self):
        self.compose.unlink()
        target = self.root / "other.yml"
        target.write_text("services: {}\n")
        self.compose.symlink_to(target)
        with self.assertRaises(ValueError):
            cli.plan("install", self.root)

    def test_invalid_action_rejected(self):
        with self.assertRaises(ValueError):
            cli.plan("shell", self.root)

    def test_cli_exit_codes_and_json(self):
        ok = subprocess.run([sys.executable, str(MODULE), "preflight", "--kit-dir", str(self.root)],
                            capture_output=True, text=True, check=False, env=os.environ.copy())
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(json.loads(ok.stdout)["action"], "preflight")
        blocked = subprocess.run([sys.executable, str(MODULE), "restore", "--kit-dir", str(self.root)],
                                 capture_output=True, text=True, check=False, env=os.environ.copy())
        self.assertEqual(blocked.returncode, 3, blocked.stderr)
        self.assertTrue(json.loads(blocked.stdout)["blocked"])

    def test_reject_empty_and_invalid_yaml(self):
        for source in ("services: {}\n", "services: [\n", "services: {gamma: {image: latest}}\n"):
            with self.subTest(source=source):
                self.compose.write_text(source)
                with self.assertRaises(ValueError):
                    cli.plan("install", self.root)

    def test_reject_mutable_and_missing_digests(self):
        for variable, value in (("CORE_IMAGE", "python:latest"), ("GAMMA_IMAGE", ""), ("DEMO_IMAGE", "demo:latest")):
            with self.subTest(variable=variable):
                with mock.patch.dict(os.environ, {variable: value}):
                    with self.assertRaises(ValueError):
                        cli.plan("install", self.root)

    def test_reject_duplicate_keys_and_unsafe_profiles(self):
        original = self.compose.read_text()
        for mutated in (original + "\nservices: {}\n", original.replace("profiles: [demo]", "profiles: [enterprise]")):
            self.assertNotEqual(mutated, original)
            self.compose.write_text(mutated)
            with self.assertRaises(ValueError):
                cli.plan("install", self.root)

    def test_reject_symlink_parent(self):
        link = self.root / "link"
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            cli.plan("install", link)

    def test_no_docker_subprocess_from_planner(self):
        with mock.patch.object(subprocess, "run", side_effect=AssertionError("unexpected Docker execution")):
            self.assertEqual(cli.plan("install", self.root)["action"], "install")

if __name__ == "__main__":
    unittest.main()
