"""Negative, synthetic-only receipt-name safety checks; no host qualification."""
import contextlib
import importlib.util
import io
import json
import pathlib
import sys
import unittest
from unittest import mock

MODULE = pathlib.Path(__file__).with_name("portal_candidate_preflight.py")
spec = importlib.util.spec_from_file_location("portal_candidate_preflight_name_test", MODULE)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class GateNameSafetyTests(unittest.TestCase):
    def check(self, gates, expected_reason, expected_calls):
        output = io.StringIO()
        with (mock.patch.object(preflight, "GATES", gates),
              mock.patch.object(preflight.shutil, "which", return_value="/usr/bin/python3"),
              mock.patch.object(preflight.subprocess, "run", return_value=mock.Mock(returncode=0)) as runner,
              mock.patch.object(sys, "argv", ["preflight", "--json"]),
              contextlib.redirect_stdout(output)):
            code = preflight.main()
        receipt = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(runner.call_count, expected_calls)
        self.assertIn(expected_reason, [g.get("reason") for g in receipt["gates"]])
        self.assertEqual(receipt["host"], "NOT_VERIFIED")
        self.assertEqual(receipt["debian"], "NOT_VERIFIED")
        self.assertEqual(receipt["chromium"], "NOT_VERIFIED")
        self.assertEqual(receipt["live"], "UNKNOWN")
        self.assertEqual(receipt["kind"], "SYNTHETIC_OFFLINE_ONLY")

    def test_bidi_override_rejected_without_execution(self):
        self.check([("history\\u202ePASS", ["python3", "-V"])], "unsafe gate name", 0)

    def test_zero_width_joiner_rejected_without_execution(self):
        self.check([("history\\u200dPASS", ["python3", "-V"])], "unsafe gate name", 0)

    def test_control_character_rejected_without_execution(self):
        self.check([("history\\nPASS", ["python3", "-V"])], "unsafe gate name", 0)

    def test_whitespace_alias_duplicate(self):
        self.check([("history", ["python3", "-V"]), (" history ", ["python3", "-V"])],
                   "duplicate gate name", 1)


if __name__ == "__main__":
    unittest.main()
