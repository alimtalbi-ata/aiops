"""Regression: platform gate must fail closed when Debian runtime evidence is incomplete.

Offline test only; does not execute Docker or access production.
"""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "platform_readiness_gate_under_test",
    ROOT / "scripts" / "ops" / "platform_readiness_gate.py",
)
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


class PlatformGateRuntimeFailClosedTests(unittest.TestCase):
    def test_missing_runtime_containers_cannot_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = Path(directory) / "platform.json"
            with (
                patch.object(gate, "docker_state", return_value=[]),
                patch.object(gate, "core_probe", side_effect=AssertionError("must not probe")),
                patch.object(sys, "argv", ["platform_readiness_gate.py", "--output", str(receipt)]),
            ):
                self.assertEqual(gate.main(), 2)
            result = json.loads(receipt.read_text())
            self.assertEqual(result["verdict"], "HOLD")
            self.assertEqual(result["e2e_verdict"], "NOT_VERIFIED")
            self.assertEqual(result["deployment_verdict"], "NOT_VERIFIED")
            self.assertTrue(result.get("error"))

    def test_probe_failure_cannot_be_reported_as_e2e_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = Path(directory) / "platform.json"
            with (
                patch.object(gate, "docker_state", side_effect=RuntimeError("Docker unavailable")),
                patch.object(sys, "argv", ["platform_readiness_gate.py", "--output", str(receipt)]),
            ):
                self.assertEqual(gate.main(), 2)
            result = json.loads(receipt.read_text())
            self.assertEqual(result["verdict"], "HOLD")
            self.assertEqual(result["qualification_scope"], "read_only_platform_smoke")
            self.assertEqual(result["e2e_verdict"], "NOT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
