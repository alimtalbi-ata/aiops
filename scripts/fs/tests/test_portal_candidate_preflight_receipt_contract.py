#!/usr/bin/env python3
"""Receipt contract: synthetic preflight must never claim host qualification."""
import contextlib
import importlib.util
import io
import json
import pathlib
import subprocess
import unittest
from unittest import mock

MODULE_PATH = pathlib.Path(__file__).with_name("portal_candidate_preflight.py")
spec = importlib.util.spec_from_file_location("portal_candidate_preflight_receipt", MODULE_PATH)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class ReceiptContractTests(unittest.TestCase):
    def run_receipt(self, effect):
        output = io.StringIO()
        with mock.patch.object(preflight, "GATES", [("synthetic-gate", ["python3", "-c", "pass"])]), \
             mock.patch.object(preflight.shutil, "which", return_value="/usr/bin/python3"), \
             mock.patch.object(preflight.subprocess, "run", side_effect=effect), \
             mock.patch.object(preflight.sys, "argv", ["preflight", "--json"]), \
             contextlib.redirect_stdout(output):
            code = preflight.main()
        return code, json.loads(output.getvalue()), output.getvalue()

    def assert_unqualified(self, receipt):
        self.assertEqual(receipt["kind"], "SYNTHETIC_OFFLINE_ONLY")
        for key in ("host", "debian", "chromium"):
            self.assertEqual(receipt[key], "NOT_VERIFIED")
        self.assertEqual(receipt["live"], "UNKNOWN")
        self.assertNotIn("READY", json.dumps(receipt))

    def test_pass_does_not_qualify_host(self):
        code, receipt, raw = self.run_receipt(
            lambda *a, **k: subprocess.CompletedProcess(a[0], 0, "SECRET_CANARY", "TOKEN_CANARY"))
        self.assertEqual(code, 0)
        self.assertEqual(receipt["gates"][0]["status"], "PASS")
        self.assert_unqualified(receipt)
        self.assertNotIn("CANARY", raw)

    def test_failed_command_is_redacted_and_blocking(self):
        code, receipt, raw = self.run_receipt(
            lambda *a, **k: subprocess.CompletedProcess(a[0], 23, "SECRET_CANARY", "TOKEN_CANARY"))
        self.assertEqual(code, 1)
        self.assertEqual(receipt["gates"][0]["status"], "FAIL")
        self.assertEqual(receipt["gates"][0]["exit_code"], 23)
        self.assert_unqualified(receipt)
        self.assertNotIn("CANARY", raw)

    def test_timeout_is_redacted_and_blocking(self):
        def timeout(*a, **k):
            raise subprocess.TimeoutExpired(a[0], 120, output=b"SECRET_CANARY", stderr=b"TOKEN_CANARY")
        code, receipt, raw = self.run_receipt(timeout)
        self.assertEqual(code, 1)
        self.assertEqual(receipt["gates"][0]["status"], "FAIL")
        self.assert_unqualified(receipt)
        self.assertNotIn("CANARY", raw)


if __name__ == "__main__":
    unittest.main()
