"""Offline negative contract: missing dependencies never execute or qualify a host."""
import contextlib
import importlib.util
import io
import json
import pathlib
import sys
import unittest
from unittest import mock

MODULE_PATH = pathlib.Path(__file__).with_name("portal_candidate_preflight.py")
spec = importlib.util.spec_from_file_location("portal_candidate_preflight_missing_dependency", MODULE_PATH)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class MissingDependencyContract(unittest.TestCase):
    def check_case(self, gate, which_result, file_exists, expected_missing):
        output = io.StringIO()
        with (mock.patch.object(preflight, "GATES", [gate]),
              mock.patch.object(sys, "argv", ["preflight", "--json"]),
              mock.patch.object(preflight.shutil, "which", return_value=which_result),
              mock.patch.object(pathlib.Path, "is_file", return_value=file_exists),
              mock.patch.object(preflight.subprocess, "run") as runner,
              contextlib.redirect_stdout(output)):
            self.assertEqual(preflight.main(), 1)
        runner.assert_not_called()
        receipt = json.loads(output.getvalue())
        self.assertEqual(receipt["kind"], "SYNTHETIC_OFFLINE_ONLY")
        for field in ("host", "debian", "chromium"):
            self.assertEqual(receipt[field], "NOT_VERIFIED")
        self.assertEqual(receipt["live"], "UNKNOWN")
        self.assertEqual(len(receipt["gates"]), 1)
        result = receipt["gates"][0]
        self.assertEqual(result["status"], "NOT_EXECUTED")
        self.assertEqual(result["reason"], "missing files or executable")
        self.assertEqual(result["missing"], expected_missing)
        self.assertNotIn("PASS", output.getvalue())

    def test_missing_python_fixture(self):
        self.check_case(("fixture", ["python3", "tests/missing_fixture.py"]),
                        "/usr/bin/python3", False, ["tests/missing_fixture.py"])

    def test_missing_executable(self):
        self.check_case(("fixture", ["missing-interpreter", "tests/fixture.py"]),
                        None, True, [])

    def test_both_dependencies_missing(self):
        self.check_case(("fixture", ["missing-interpreter", "tests/fixture.py"]),
                        None, False, ["tests/fixture.py"])


if __name__ == "__main__":
    unittest.main()
