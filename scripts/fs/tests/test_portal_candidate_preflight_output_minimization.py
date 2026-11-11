#!/usr/bin/env python3
"""Offline regression: subprocess diagnostics never enter published preflight receipts."""
import contextlib
import io
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import portal_candidate_preflight as preflight


class PreflightOutputMinimization(unittest.TestCase):
    def test_success_and_failure_do_not_echo_transport_secrets(self):
        secret = "Bearer-test-canary-do-not-publish"
        for returncode, expected in ((0, "PASS"), (2, "FAIL")):
            with self.subTest(returncode=returncode), tempfile.TemporaryDirectory() as root:
                output = io.StringIO()
                fake = mock.Mock(returncode=returncode,
                                 stdout="authorization: " + secret,
                                 stderr="https://internal.invalid/?token=" + secret)
                with mock.patch.object(preflight, "GATES", [("canary", ["python3"])]), \
                     mock.patch.object(preflight, "ROOT", pathlib.Path(root)), \
                     mock.patch.object(preflight.shutil, "which", return_value="/usr/bin/python3"), \
                     mock.patch.object(preflight.subprocess, "run", return_value=fake), \
                     mock.patch.object(sys, "argv", ["preflight", "--json"]), \
                     contextlib.redirect_stdout(output):
                    code = preflight.main()
                raw = output.getvalue()
                report = json.loads(raw)
                self.assertNotIn(secret, raw)
                self.assertNotIn("internal.invalid", raw)
                self.assertNotIn("stdout", raw)
                self.assertNotIn("stderr", raw)
                self.assertNotIn("output", report["gates"][0])
                self.assertEqual(report["gates"][0]["status"], expected)
                self.assertEqual(report["gates"][0]["exit_code"], returncode)
                self.assertEqual(code, 0 if returncode == 0 else 1)
                self.assertEqual(report["kind"], "SYNTHETIC_OFFLINE_ONLY")
                self.assertEqual(report["host"], "NOT_VERIFIED")
                self.assertEqual(report["debian"], "NOT_VERIFIED")
                self.assertEqual(report["chromium"], "NOT_VERIFIED")
                self.assertEqual(report["live"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
