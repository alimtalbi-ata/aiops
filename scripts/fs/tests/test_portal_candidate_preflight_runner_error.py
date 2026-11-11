#!/usr/bin/env python3
"""Synthetic fail-closed contract: runner OS errors never leak details or PASS."""
import contextlib
import io
import json
import pathlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import portal_candidate_preflight as preflight


class RunnerErrorContract(unittest.TestCase):
    def test_oserror_is_fail_closed_and_receipt_is_minimized(self):
        secret = "CANARY_BEARER_DO_NOT_PRINT"
        out = io.StringIO()
        with patch.object(preflight, "GATES", [("synthetic-runner-error", ["node", "--test"])]), \
             patch.object(preflight.shutil, "which", return_value="/usr/bin/node"), \
             patch.object(preflight.subprocess, "run", side_effect=OSError(secret)), \
             patch.object(sys, "argv", ["preflight", "--json"]), \
             contextlib.redirect_stdout(out):
            result = preflight.main()
        receipt = json.loads(out.getvalue())
        self.assertEqual(result, 1)
        self.assertEqual(receipt["kind"], "SYNTHETIC_OFFLINE_ONLY")
        self.assertEqual(receipt["host"], "NOT_VERIFIED")
        self.assertEqual(receipt["debian"], "NOT_VERIFIED")
        self.assertEqual(receipt["chromium"], "NOT_VERIFIED")
        self.assertEqual(receipt["live"], "UNKNOWN")
        self.assertEqual(receipt["gates"], [
            {"gate": "synthetic-runner-error", "status": "FAIL", "reason": "runner unavailable"}
        ])
        self.assertNotIn(secret, out.getvalue())


if __name__ == "__main__":
    unittest.main()
