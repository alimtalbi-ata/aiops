#!/usr/bin/env python3
"""Synthetic unit checks for the offline Portal preflight orchestrator; no host qualification."""
import contextlib
import io
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

import portal_candidate_preflight as preflight


class PreflightSelfTest(unittest.TestCase):
    def invoke(self, gates, root, run=None, executable="/usr/bin/python3"):
        output = io.StringIO()
        with mock.patch.object(preflight, "GATES", gates), \
             mock.patch.object(preflight, "ROOT", pathlib.Path(root)), \
             mock.patch.object(preflight.shutil, "which", return_value=executable), \
             mock.patch.object(preflight.subprocess, "run", side_effect=run), \
             mock.patch.object(sys, "argv", ["preflight", "--json"]), \
             contextlib.redirect_stdout(output):
            code = preflight.main()
        return code, json.loads(output.getvalue())

    def test_missing_file_is_not_executed_and_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            code, report = self.invoke([("missing", ["python3", "absent.py"])], root)
        self.assertEqual(code, 1)
        self.assertEqual(report["gates"][0]["status"], "NOT_EXECUTED")
        self.assertEqual(report["host"], "NOT_VERIFIED")
        self.assertEqual(report["debian"], "NOT_VERIFIED")
        self.assertEqual(report["chromium"], "NOT_VERIFIED")
        self.assertEqual(report["live"], "UNKNOWN")

    def test_missing_executable_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            code, report = self.invoke([("tool", ["nonexistent-tool"])], root, executable=None)
        self.assertEqual(code, 1)
        self.assertEqual(report["gates"][0]["status"], "NOT_EXECUTED")

    def test_nonzero_exit_and_timeout_fail_closed(self):
        for failure in (mock.Mock(returncode=2, stdout="", stderr="failed"),
                        preflight.subprocess.TimeoutExpired(["python3"], 120)):
            with self.subTest(failure=type(failure).__name__), tempfile.TemporaryDirectory() as root:
                code, report = self.invoke([("failed", ["python3"])], root, run=failure if isinstance(failure, Exception) else lambda *a, **k: failure)
                self.assertEqual(code, 1)
                self.assertEqual(report["gates"][0]["status"], "FAIL")

    def test_success_is_synthetic_only(self):
        with tempfile.TemporaryDirectory() as root:
            code, report = self.invoke([("ok", ["python3"])], root,
                run=lambda *a, **k: mock.Mock(returncode=0, stdout="ok", stderr=""))
        self.assertEqual(code, 0)
        self.assertEqual(report["kind"], "SYNTHETIC_OFFLINE_ONLY")
        self.assertEqual(report["host"], "NOT_VERIFIED")
        self.assertEqual(report["gates"][0]["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
