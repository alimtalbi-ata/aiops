"""Synthetic negative tests: decode/subprocess runner failures remain redacted and blocking."""
import contextlib
import importlib.util
import io
import json
import pathlib
import sys
import unittest
from unittest import mock

TARGET = pathlib.Path(__file__).with_name("portal_candidate_preflight.py")
spec = importlib.util.spec_from_file_location("portal_candidate_preflight_decode", TARGET)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class RunnerDecodeFailureTests(unittest.TestCase):
    def test_runner_errors_fail_closed_without_leaking_exception(self):
        for failure in (
            UnicodeDecodeError("utf-8", b"\\xff", 0, 1, "SYNTHETIC_SECRET"),
            UnicodeError("SYNTHETIC_SECRET"),
            __import__("subprocess").SubprocessError("SYNTHETIC_SECRET"),
        ):
            with self.subTest(failure=type(failure).__name__):
                output = io.StringIO()
                with (
                    mock.patch.object(preflight, "GATES", [("decode-gate", ["python3", "-V"])]),
                    mock.patch.object(preflight.shutil, "which", return_value="/synthetic/python3"),
                    mock.patch.object(preflight.subprocess, "run", side_effect=failure) as runner,
                    mock.patch.object(sys, "argv", ["preflight", "--json"]),
                    contextlib.redirect_stdout(output),
                ):
                    rc = preflight.main()
                receipt = json.loads(output.getvalue())
                self.assertEqual(rc, 1)
                self.assertEqual(receipt["kind"], "SYNTHETIC_OFFLINE_ONLY")
                self.assertEqual(receipt["host"], "NOT_VERIFIED")
                self.assertEqual(receipt["debian"], "NOT_VERIFIED")
                self.assertEqual(receipt["chromium"], "NOT_VERIFIED")
                self.assertEqual(receipt["live"], "UNKNOWN")
                self.assertEqual(receipt["gates"], [
                    {"gate": "decode-gate", "status": "FAIL", "reason": "runner unavailable"}
                ])
                self.assertNotIn("SYNTHETIC_SECRET", output.getvalue())
                runner.assert_called_once()


if __name__ == "__main__":
    unittest.main()
