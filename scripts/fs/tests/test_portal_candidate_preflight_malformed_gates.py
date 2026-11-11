"""Fail-closed synthetic checks for invalid preflight gate manifests."""
import contextlib
import io
import json
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import portal_candidate_preflight as preflight


class ManifestFailClosedTests(unittest.TestCase):
    def receipt(self, gates):
        output = io.StringIO()
        with mock.patch.object(preflight, "GATES", gates), \
             mock.patch.object(sys, "argv", ["preflight", "--json"]), \
             mock.patch.object(preflight.shutil, "which", return_value="/synthetic/python3"), \
             mock.patch.object(preflight.subprocess, "run", return_value=mock.Mock(returncode=0)) as runner, \
             contextlib.redirect_stdout(output):
            code = preflight.main()
        return code, json.loads(output.getvalue()), runner.call_count

    def test_empty_manifest_blocks_without_running(self):
        code, receipt, calls = self.receipt([])
        self.assertEqual((code, calls), (1, 0))
        self.assertEqual(receipt["gates"][0]["status"], "FAIL")

    def test_malformed_entries_block_without_running(self):
        for gates in [[("bad", [])], [("", ["python3"])], [("bad", ["python3", None])], [None], [("bad", "python3")]]:
            with self.subTest(gates=gates):
                code, receipt, calls = self.receipt(gates)
                self.assertEqual((code, calls), (1, 0))
                self.assertEqual(receipt["gates"][0]["reason"], "invalid gate definition")
                self.assertEqual(receipt["host"], "NOT_VERIFIED")
                self.assertEqual(receipt["debian"], "NOT_VERIFIED")
                self.assertEqual(receipt["chromium"], "NOT_VERIFIED")
                self.assertEqual(receipt["live"], "UNKNOWN")

    def test_duplicate_name_blocks_and_does_not_execute_duplicate(self):
        code, receipt, calls = self.receipt([("gate", ["python3", "-V"]), ("gate", ["python3", "-V"])])
        self.assertEqual((code, calls), (1, 1))
        self.assertEqual([x["status"] for x in receipt["gates"]], ["PASS", "FAIL"])
        self.assertEqual(receipt["gates"][1]["reason"], "duplicate gate name")
        self.assertEqual(receipt["kind"], "SYNTHETIC_OFFLINE_ONLY")


if __name__ == "__main__":
    unittest.main()
