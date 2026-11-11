#!/usr/bin/env python3
"""Fail-closed coverage contract for the offline Portal preflight manifest.

This is a synthetic manifest test, NOT a Debian/Chromium/E2E qualification.
"""
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
PREFLIGHT = ROOT / "scripts/fs/tests/portal_candidate_preflight.py"

class PortalPreflightCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("portal_candidate_preflight", PREFLIGHT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.gates = module.GATES

    def test_unique_gate_names_and_commands(self):
        names = [name for name, _ in self.gates]
        commands = [tuple(command) for _, command in self.gates]
        self.assertEqual(len(names), len(set(names)), "duplicate gate name")
        self.assertEqual(len(commands), len(set(commands)), "duplicate gate command")
        self.assertTrue(names, "empty preflight must not qualify")

    def test_historical_navigation_evidence_and_denial_coverage(self):
        files = {
            token for _, command in self.gates for token in command
            if token.endswith((".py", ".mjs"))
        }
        required = {
            "scripts/fs/tests/test_fs1113_history_matrix_supersession.py",
            "scripts/fs/tests/test_fs1113_history_empty_accessibility.py",
            "scripts/fs/tests/test_fs1113_history_accessible_context.py",
            "scripts/fs/tests/test_fs1113_history_aria_busy.py",
            "scripts/fs/tests/test_fs1113_history_contract_failclosed.py",
            "scripts/fs/tests/test_fs1113_history_auth_denial.py",
            "app/portal/components/operational_state.test.mjs",
            "app/portal/components/evidence_filter.test.mjs",
            "tests/test_portal_consolidated_readonly_contract.mjs",
            "tests/test_portal_navigation_supersession.mjs",
            "tests/test_portal_error_response_security_20261110.py",
            "tests/test_portal_method_error_security_20261110.py",
        }
        self.assertFalse(required - files, "mandatory safety gate missing")

    def test_commands_only_reference_local_test_files(self):
        for name, command in self.gates:
            with self.subTest(gate=name):
                self.assertIn(command[0], ("python3", "node"))
                self.assertNotIn("-c", command)
                self.assertNotIn("-e", command)
                for token in command:
                    if token.endswith((".py", ".mjs")):
                        path = pathlib.PurePosixPath(token)
                        self.assertFalse(path.is_absolute())
                        self.assertNotIn("..", path.parts)
                        self.assertTrue(
                            token.startswith(("scripts/fs/tests/", "tests/", "app/portal/components/"))
                        )
                        self.assertTrue(token.endswith((".test.mjs", ".py")))

if __name__ == "__main__":
    unittest.main()
