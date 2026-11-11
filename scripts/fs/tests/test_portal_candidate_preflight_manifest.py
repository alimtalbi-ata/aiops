#!/usr/bin/env python3
"""Fail-closed static contract for the offline Portal candidate gate manifest.

Synthetic-only: this does not qualify Chromium, CSP, tenant ACL, Debian or E2E.
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import portal_candidate_preflight as preflight


class PortalPreflightManifestContract(unittest.TestCase):
    def test_required_regression_gates_remain_present(self):
        commands = {name: tuple(cmd) for name, cmd in preflight.GATES}
        required = {
            "history-matrix", "history-empty-a11y", "history-accessible-context",
            "history-aria-busy", "history-contract", "history-auth",
            "readonly-and-components", "http-404-405",
        }
        self.assertTrue(required.issubset(commands), required - commands.keys())
        self.assertEqual(len(commands), len(preflight.GATES), "duplicate gate name")
        for marker in ("operational_state.test.mjs", "evidence_filter.test.mjs",
                       "test_portal_navigation_supersession.mjs"):
            self.assertTrue(any(marker in part for part in commands["readonly-and-components"]), marker)
        for marker in ("test_portal_error_response_security_20261110.py",
                       "test_portal_method_error_security_20261110.py"):
            self.assertTrue(any(marker in part for part in commands["http-404-405"]), marker)

    def test_gate_commands_are_local_and_non_mutating(self):
        allowed = {"python3", "node"}
        forbidden = {"docker", "kubectl", "ssh", "scp", "rsync", "curl", "wget",
                     "git", "bash", "sh", "sudo", "systemctl", "cron", "crontab"}
        for name, cmd in preflight.GATES:
            with self.subTest(gate=name):
                self.assertIsInstance(cmd, list)
                self.assertGreaterEqual(len(cmd), 2)
                self.assertIn(cmd[0], allowed)
                self.assertFalse(forbidden.intersection(cmd))
                self.assertNotIn("-c", cmd)
                self.assertNotIn("--eval", cmd)
                for part in cmd:
                    self.assertNotIn("://", part)
                    self.assertNotIn("..", pathlib.PurePosixPath(part).parts)
                    self.assertFalse(part.startswith("/"))

    def test_reporting_cannot_claim_host_qualification(self):
        import inspect
        source = inspect.getsource(preflight.main)
        for expected in ('SYNTHETIC_OFFLINE_ONLY', 'NOT_VERIFIED', 'UNKNOWN'):
            self.assertIn(expected, source)
        self.assertNotIn('shell=True', source)


if __name__ == "__main__":
    unittest.main()
