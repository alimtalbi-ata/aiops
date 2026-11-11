#!/usr/bin/env python3
"""Synthetic runner-boundary contract; never qualifies Debian, Chromium or LIVE."""
import contextlib
import io
import json
import pathlib
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import portal_candidate_preflight as preflight


class RunnerIsolationTests(unittest.TestCase):
    def test_each_gate_uses_bounded_captured_repository_runner(self):
        gates = [
            ("history", ["python3", "scripts/fs/tests/test_fs1113_history_matrix_supersession.py"]),
            ("navigation", ["node", "--test", "tests/test_portal_navigation_supersession.mjs"]),
        ]
        calls = []

        def fake_run(argv, **kwargs):
            calls.append((list(argv), dict(kwargs)))
            return subprocess.CompletedProcess(argv, 0, "SYNTHETIC_SECRET", "SYNTHETIC_TOKEN")

        output = io.StringIO()
        with mock.patch.object(preflight, "GATES", gates), \
             mock.patch.object(preflight.shutil, "which", return_value="/usr/bin/test"), \
             mock.patch.object(preflight.subprocess, "run", side_effect=fake_run), \
             mock.patch.object(preflight.sys, "argv", ["preflight", "--json"]), \
             contextlib.redirect_stdout(output):
            exit_code = preflight.main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(calls), len(gates))
        for (argv, options), (_, expected) in zip(calls, gates):
            self.assertEqual(argv, expected)
            self.assertEqual(options["cwd"], preflight.ROOT)
            self.assertIs(options["capture_output"], True)
            self.assertIs(options["text"], True)
            self.assertGreater(options["timeout"], 0)
            self.assertLessEqual(options["timeout"], 120)
            self.assertNotIn("shell", options)
            self.assertNotIn("env", options)
        raw = output.getvalue()
        receipt = json.loads(raw)
        self.assertNotIn("SYNTHETIC_SECRET", raw)
        self.assertNotIn("SYNTHETIC_TOKEN", raw)
        self.assertEqual([x["status"] for x in receipt["gates"]], ["PASS", "PASS"])
        self.assertEqual(receipt["kind"], "SYNTHETIC_OFFLINE_ONLY")
        self.assertEqual(receipt["host"], "NOT_VERIFIED")
        self.assertEqual(receipt["debian"], "NOT_VERIFIED")
        self.assertEqual(receipt["chromium"], "NOT_VERIFIED")
        self.assertEqual(receipt["live"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
