"""Offline regression: every preflight gate is evaluated even after a failure.

Synthetic subprocess mocks only; never a Debian/Chromium qualification.
"""
import contextlib
import importlib.util
import io
import json
import pathlib
import subprocess
import tempfile
import unittest
from unittest import mock

SCRIPT = pathlib.Path(__file__).with_name("portal_candidate_preflight.py")
SPEC = importlib.util.spec_from_file_location("portal_candidate_preflight_all_gates", SCRIPT)
PREFLIGHT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREFLIGHT)


class AllGatesContract(unittest.TestCase):
    def test_first_gate_failure_does_not_skip_remaining_gates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            gates = [
                ("initial-failure", ["python3", "first.py"]),
                ("later-success", ["node", "--test", "second.mjs"]),
                ("last-timeout", ["python3", "third.py"]),
            ]
            for name in ("first.py", "second.mjs", "third.py"):
                (root / name).touch()
            calls = []

            def runner(command, **kwargs):
                calls.append(list(command))
                if command[1] == "first.py":
                    return subprocess.CompletedProcess(command, 1, "SECRET_STDOUT", "SECRET_STDERR")
                if command[1] == "third.py":
                    raise subprocess.TimeoutExpired(command, 120, output="SECRET_TIMEOUT")
                return subprocess.CompletedProcess(command, 0, "SECRET_OK", "")

            output = io.StringIO()
            with mock.patch.object(PREFLIGHT, "ROOT", root), \
                 mock.patch.object(PREFLIGHT, "GATES", gates), \
                 mock.patch.object(PREFLIGHT.shutil, "which", return_value="/synthetic/executable"), \
                 mock.patch.object(PREFLIGHT.subprocess, "run", side_effect=runner), \
                 mock.patch("sys.argv", ["preflight", "--json"]), contextlib.redirect_stdout(output):
                exit_code = PREFLIGHT.main()

            receipt = json.loads(output.getvalue())
            self.assertEqual(exit_code, 1)
            self.assertEqual([x["gate"] for x in receipt["gates"]], [x[0] for x in gates])
            self.assertEqual([x["status"] for x in receipt["gates"]], ["FAIL", "PASS", "FAIL"])
            self.assertEqual(len(calls), 3)
            for key, expected in (("kind", "SYNTHETIC_OFFLINE_ONLY"),
                                  ("host", "NOT_VERIFIED"),
                                  ("debian", "NOT_VERIFIED"),
                                  ("chromium", "NOT_VERIFIED"),
                                  ("live", "UNKNOWN")):
                self.assertEqual(receipt[key], expected)
            self.assertNotIn("SECRET_", output.getvalue())

    def test_duplicate_gate_names_are_not_silently_deduplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "check.py").touch()
            gates = [("same-name", ["python3", "check.py"])] * 2
            with mock.patch.object(PREFLIGHT, "ROOT", root), \
                 mock.patch.object(PREFLIGHT, "GATES", gates), \
                 mock.patch.object(PREFLIGHT.shutil, "which", return_value="/synthetic/python"), \
                 mock.patch.object(PREFLIGHT.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)), \
                 mock.patch("sys.argv", ["preflight", "--json"]), contextlib.redirect_stdout(io.StringIO()) as output:
                exit_code = PREFLIGHT.main()
            self.assertEqual(exit_code, 0)
            self.assertEqual(len(json.loads(output.getvalue())["gates"]), 2)


if __name__ == "__main__":
    unittest.main()
