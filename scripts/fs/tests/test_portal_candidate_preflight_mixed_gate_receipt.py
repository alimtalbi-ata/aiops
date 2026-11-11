"""Offline mixed-gate receipt regression: partial success is never a release pass."""
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
spec = importlib.util.spec_from_file_location("portal_candidate_preflight_mixed", MODULE_PATH)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)

SECRET = "SYNTHETIC_TOKEN_NEVER_LOG"


class MixedGateReceiptContract(unittest.TestCase):
    def test_pass_failure_and_missing_dependency_stay_distinct(self):
        gates = [
            ("history-pass", ["python3", "tests/pass.py"]),
            ("http-denial-fail", ["python3", "tests/fail.py"]),
            ("missing-contract", ["python3", "tests/missing.py"]),
        ]
        calls = []

        def file_exists(path):
            return not str(path).endswith("tests/missing.py")

        def run(command, **kwargs):
            calls.append(command[-1])
            self.assertEqual(kwargs["cwd"], preflight.ROOT)
            self.assertEqual(kwargs["timeout"], 120)
            self.assertTrue(kwargs["capture_output"])
            self.assertTrue(kwargs["text"])
            self.assertNotIn("shell", kwargs)
            code = 0 if command[-1].endswith("pass.py") else 403
            return subprocess.CompletedProcess(command, code, SECRET, SECRET)

        output = io.StringIO()
        with (mock.patch.object(preflight, "GATES", gates),
              mock.patch.object(sys, "argv", ["preflight", "--json"]),
              mock.patch.object(preflight.shutil, "which", return_value="/usr/bin/python3"),
              mock.patch.object(pathlib.Path, "is_file", autospec=True, side_effect=file_exists),
              mock.patch.object(preflight.subprocess, "run", side_effect=run),
              contextlib.redirect_stdout(output)):
            self.assertEqual(preflight.main(), 1)

        self.assertEqual(calls, ["tests/pass.py", "tests/fail.py"])
        raw = output.getvalue()
        self.assertNotIn(SECRET, raw)
        receipt = json.loads(raw)
        self.assertEqual(receipt["kind"], "SYNTHETIC_OFFLINE_ONLY")
        self.assertEqual(receipt["live"], "UNKNOWN")
        for key in ("host", "debian", "chromium"):
            self.assertEqual(receipt[key], "NOT_VERIFIED")
        results = receipt["gates"]
        self.assertEqual([r["gate"] for r in results],
                         ["history-pass", "http-denial-fail", "missing-contract"])
        self.assertEqual([r["status"] for r in results],
                         ["PASS", "FAIL", "NOT_EXECUTED"])
        self.assertEqual(results[0]["exit_code"], 0)
        self.assertEqual(results[1]["exit_code"], 403)
        self.assertEqual(results[2]["reason"], "missing files or executable")
        self.assertEqual(results[2]["missing"], ["tests/missing.py"])


if __name__ == "__main__":
    unittest.main()
