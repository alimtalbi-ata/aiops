"""Non-sequence manifest inputs must fail closed without executing subprocesses."""
import contextlib
import io
import json
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import portal_candidate_preflight as preflight


class ManifestTypeTests(unittest.TestCase):
    def test_non_sequence_manifests_fail_closed(self):
        for gates in (None, 1, True, {}, "synthetic", (x for x in [])):
            with self.subTest(manifest_type=type(gates).__name__):
                output = io.StringIO()
                with mock.patch.object(preflight, "GATES", gates), \
                     mock.patch.object(sys, "argv", ["preflight", "--json"]), \
                     mock.patch.object(preflight.subprocess, "run") as runner, \
                     contextlib.redirect_stdout(output):
                    code = preflight.main()
                receipt = json.loads(output.getvalue())
                self.assertEqual(code, 1)
                runner.assert_not_called()
                self.assertEqual(receipt["gates"], [
                    {"gate": "manifest", "status": "FAIL", "reason": "invalid manifest type"}
                ])
                self.assertEqual(receipt["kind"], "SYNTHETIC_OFFLINE_ONLY")
                self.assertEqual(receipt["host"], "NOT_VERIFIED")
                self.assertEqual(receipt["debian"], "NOT_VERIFIED")
                self.assertEqual(receipt["chromium"], "NOT_VERIFIED")
                self.assertEqual(receipt["live"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
