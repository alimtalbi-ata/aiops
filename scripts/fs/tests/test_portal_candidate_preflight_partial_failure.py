#!/usr/bin/env python3
"""Offline preflight regression: missing gates and partial success must block."""
import contextlib
import importlib.util
import io
import json
import pathlib
import subprocess
import unittest
from unittest import mock

PATH = pathlib.Path(__file__).with_name("portal_candidate_preflight.py")
spec = importlib.util.spec_from_file_location("portal_candidate_preflight_partial", PATH)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class PartialFailureTests(unittest.TestCase):
    def receipt(self, gates, executable, runner):
        output = io.StringIO()
        with mock.patch.object(preflight, "GATES", gates), \
             mock.patch.object(preflight.shutil, "which", side_effect=executable), \
             mock.patch.object(preflight.subprocess, "run", side_effect=runner) as run, \
             mock.patch.object(preflight.sys, "argv", ["preflight", "--json"]), \
             contextlib.redirect_stdout(output):
            exit_code = preflight.main()
        return exit_code, json.loads(output.getvalue()), run

    def assert_unqualified(self, receipt):
        self.assertEqual(receipt["kind"], "SYNTHETIC_OFFLINE_ONLY")
        self.assertEqual(receipt["host"], "NOT_VERIFIED")
        self.assertEqual(receipt["debian"], "NOT_VERIFIED")
        self.assertEqual(receipt["chromium"], "NOT_VERIFIED")
        self.assertEqual(receipt["live"], "UNKNOWN")

    def test_missing_executable_does_not_run_any_command(self):
        gates = [("missing", ["absent-executable", "-c", "pass"])]
        code, receipt, run = self.receipt(gates, lambda _: None,
                                          lambda *a, **kw: self.fail("runner called"))
        self.assertEqual(code, 1)
        self.assertEqual(receipt["gates"][0]["status"], "NOT_EXECUTED")
        run.assert_not_called()
        self.assert_unqualified(receipt)

    def test_missing_test_file_blocks_even_when_executable_exists(self):
        gates = [("missing-file", ["python3", "nonexistent-portal-gate-555.py"])]
        code, receipt, run = self.receipt(gates, lambda _: "/usr/bin/python3",
                                          lambda *a, **kw: self.fail("runner called"))
        self.assertEqual(code, 1)
        self.assertEqual(receipt["gates"][0]["status"], "NOT_EXECUTED")
        run.assert_not_called()
        self.assert_unqualified(receipt)

    def test_one_pass_cannot_mask_one_failure(self):
        gates = [("pass", ["python3", "-c", "pass"]),
                 ("fail", ["python3", "-c", "exit(1)"])]
        codes = iter([0, 7])
        def runner(command, **kwargs):
            return subprocess.CompletedProcess(command, next(codes),
                                               "SECRET_CANARY", "TOKEN_CANARY")
        code, receipt, run = self.receipt(gates, lambda _: "/usr/bin/python3", runner)
        self.assertEqual(code, 1)
        self.assertEqual([g["status"] for g in receipt["gates"]], ["PASS", "FAIL"])
        self.assertEqual(run.call_count, 2)
        self.assertNotIn("CANARY", json.dumps(receipt))
        self.assert_unqualified(receipt)


if __name__ == "__main__":
    unittest.main()
