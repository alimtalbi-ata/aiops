"""Fail-closed contract for a completely empty offline preflight manifest."""
import contextlib
import importlib.util
import io
import json
import pathlib
import sys
import unittest
from unittest import mock

MODULE_PATH = pathlib.Path(__file__).with_name("portal_candidate_preflight.py")
SPEC = importlib.util.spec_from_file_location("portal_candidate_preflight_empty_gates", MODULE_PATH)
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)


class EmptyManifestContract(unittest.TestCase):
    def test_empty_manifest_never_returns_success_or_host_qualification(self):
        output = io.StringIO()
        with mock.patch.object(preflight, "GATES", []), \
             mock.patch.object(sys, "argv", ["portal_candidate_preflight.py", "--json"]), \
             mock.patch.object(preflight.subprocess, "run", side_effect=AssertionError("must not spawn")), \
             contextlib.redirect_stdout(output):
            code = preflight.main()

        receipt = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(receipt["kind"], "SYNTHETIC_OFFLINE_ONLY")
        for field in ("host", "debian", "chromium"):
            self.assertEqual(receipt[field], "NOT_VERIFIED")
        self.assertEqual(receipt["live"], "UNKNOWN")
        self.assertEqual(receipt["gates"], [
            {"gate": "manifest", "status": "FAIL", "reason": "no gates configured"}
        ])
        self.assertNotIn("PASS", output.getvalue())


if __name__ == "__main__":
    unittest.main()
