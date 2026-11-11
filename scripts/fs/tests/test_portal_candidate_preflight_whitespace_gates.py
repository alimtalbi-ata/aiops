"""Whitespace-only gate names/arguments must not execute or yield PASS."""
import contextlib
import io
import json
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import portal_candidate_preflight as preflight


class WhitespaceGateTests(unittest.TestCase):
    def test_whitespace_only_names_and_arguments_fail_closed(self):
        cases = [
            [("   ", ["python3", "-V"])],
            [("history", ["   "])],
            [("history", ["python3", "  "])],
            [("history", ["python3", "\\t"])],
        ]
        for gates in cases:
            with self.subTest(gates=gates):
                output = io.StringIO()
                with mock.patch.object(preflight, "GATES", gates), \\
                     mock.patch.object(sys, "argv", ["preflight", "--json"]), \\
                     mock.patch.object(preflight.shutil, "which", return_value="/synthetic/python3"), \\
                     mock.patch.object(preflight.subprocess, "run") as runner, \\
                     contextlib.redirect_stdout(output):
                    exit_code = preflight.main()
                receipt = json.loads(output.getvalue())
                self.assertEqual(exit_code, 1)
                runner.assert_not_called()
                self.assertEqual(receipt["gates"][0]["status"], "FAIL")
                self.assertEqual(receipt["gates"][0]["reason"], "invalid gate definition")
                self.assertEqual(receipt["kind"], "SYNTHETIC_OFFLINE_ONLY")
                self.assertEqual(receipt["host"], "NOT_VERIFIED")
                self.assertEqual(receipt["debian"], "NOT_VERIFIED")
                self.assertEqual(receipt["chromium"], "NOT_VERIFIED")
                self.assertEqual(receipt["live"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
