"""Synthetic negative checks: runner failures cannot leak secrets or claim host qualification."""
import contextlib
import importlib.util
import io
import json
import pathlib
import subprocess
import sys
import unittest
from unittest import mock

MODULE_PATH = pathlib.Path(__file__).with_name("portal_candidate_preflight.py")
spec = importlib.util.spec_from_file_location("portal_candidate_preflight_runner_failures", MODULE_PATH)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)

SECRET = "SYNTHETIC_SECRET_DO_NOT_EMIT"


class RunnerFailureContract(unittest.TestCase):
    def check_failure(self, outcome, expected_reason=None, expected_code=None):
        stdout = io.StringIO()
        gate = ("runner-negative", ["python3", "tests/synthetic.py"])
        with (mock.patch.object(preflight, "GATES", [gate]),
              mock.patch.object(sys, "argv", ["preflight", "--json"]),
              mock.patch.object(preflight.shutil, "which", return_value="/usr/bin/python3"),
              mock.patch.object(pathlib.Path, "is_file", return_value=True),
              mock.patch.object(preflight.subprocess, "run", side_effect=outcome) as runner,
              contextlib.redirect_stdout(stdout)):
            self.assertEqual(preflight.main(), 1)
        runner.assert_called_once()
        self.assertEqual(runner.call_args.kwargs["cwd"], preflight.ROOT)
        self.assertEqual(runner.call_args.kwargs["timeout"], 120)
        self.assertTrue(runner.call_args.kwargs["capture_output"])
        self.assertTrue(runner.call_args.kwargs["text"])
        self.assertNotIn("shell", runner.call_args.kwargs)
        raw = stdout.getvalue()
        self.assertNotIn(SECRET, raw)
        receipt = json.loads(raw)
        self.assertEqual(receipt["kind"], "SYNTHETIC_OFFLINE_ONLY")
        self.assertEqual(receipt["live"], "UNKNOWN")
        for field in ("host", "debian", "chromium"):
            self.assertEqual(receipt[field], "NOT_VERIFIED")
        self.assertEqual(len(receipt["gates"]), 1)
        result = receipt["gates"][0]
        self.assertEqual(result["gate"], "runner-negative")
        self.assertEqual(result["status"], "FAIL")
        if expected_reason:
            self.assertEqual(result["reason"], expected_reason)
        if expected_code is not None:
            self.assertEqual(result["exit_code"], expected_code)

    def test_nonzero_exit_does_not_emit_captured_logs(self):
        self.check_failure(
            subprocess.CompletedProcess(["python3"], 7, stdout=SECRET, stderr=SECRET),
            expected_code=7)

    def test_timeout_does_not_emit_exception_payload(self):
        self.check_failure(
            subprocess.TimeoutExpired(["python3", SECRET], 120, output=SECRET, stderr=SECRET),
            expected_reason="timeout 120s")

    def test_oserror_does_not_emit_exception_payload(self):
        self.check_failure(OSError(SECRET), expected_reason="runner unavailable")


if __name__ == "__main__":
    unittest.main()
