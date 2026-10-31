import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location(
    "debian_readonly_reporter",
    Path(__file__).resolve().parents[1] / "scripts" / "debian-readonly-reporter.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DebianReadonlyReporterTests(unittest.TestCase):
    def test_fixed_command_never_uses_shell(self):
        with mock.patch.object(MODULE.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=0, stdout="ok", stderr="")
            result = MODULE.fixed_command(["uptime", "-p"])
        self.assertTrue(result["available"])
        self.assertFalse(run.call_args.kwargs.get("shell", False))

    def test_collect_contains_only_allowlisted_probe_families(self):
        with mock.patch.object(MODULE, "fixed_command", return_value={
            "available": True, "returncode": 0, "stdout": "up", "stderr": ""
        }), mock.patch.object(MODULE, "docker_inventory", return_value={
            "available": True, "containers": [], "truncated": False
        }), mock.patch.object(MODULE, "tcp_probe", return_value={"reachable": False}):
            report = MODULE.collect()
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(set(report["tcp_loopback"]), {"5432", "7233", "17777", "3000", "9090"})
        self.assertNotIn("environment", report)
        self.assertNotIn("logs", report)
        self.assertNotIn("credentials", report)

    def test_token_permissions_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            token = Path(tmp) / "token"
            token.write_text("ghp-not-a-real-token")
            token.chmod(0o644)
            with mock.patch.object(MODULE, "TOKEN_PATH", token):
                with self.assertRaisesRegex(RuntimeError, "permissions 0600"):
                    MODULE.publish({"schema_version": 1})

    def test_report_size_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_state, old_lock, old_latest = MODULE.STATE_DIR, MODULE.LOCK_PATH, MODULE.LATEST_PATH
            MODULE.STATE_DIR = Path(tmp)
            MODULE.LOCK_PATH = Path(tmp) / "lock"
            MODULE.LATEST_PATH = Path(tmp) / "latest.json"
            try:
                report = {"payload": "x" * (MODULE.MAX_REPORT_BYTES + 1)}
                with mock.patch.object(MODULE, "collect", return_value=report):
                    with self.assertRaisesRegex(RuntimeError, "size limit"):
                        MODULE.main()
            finally:
                MODULE.STATE_DIR, MODULE.LOCK_PATH, MODULE.LATEST_PATH = old_state, old_lock, old_latest


if __name__ == "__main__":
    unittest.main()
