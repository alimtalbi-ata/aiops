"""Offline regression contract for the read-only platform readiness gate.

No Docker, network, Debian host or GLPI access: all probes are mocked.
Run: python3 -m unittest discover -s tests -p 'test_platform_readiness_contract.py' -v
"""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

GATE = Path(__file__).resolve().parents[1] / "scripts/ops/platform_readiness_gate.py"
spec = importlib.util.spec_from_file_location("platform_readiness_under_test", GATE)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def runtime():
    return [
        {"Name": "/" + name, "Config": {"Image": "synthetic:never-deployed"},
         "Image": "sha256:" + "a" * 64,
         "State": {"Status": "running", "Health": {"Status": "healthy"}},
         "NetworkSettings": {"Networks": {"synthetic": {}}}}
        for name in [v[0] for v in gate.SERVICES.values()] + list(gate.INFRA.values())
    ]


def probes():
    return {name: {"http": 200} for name in
            list(gate.SERVICES) + ["dashboard", "runs", "incidents", "twin_summary"]}


class ReadinessContract(unittest.TestCase):
    def run_gate(self, containers, observations):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "receipt.json"
            with patch.object(sys, "argv", ["gate", "--output", str(output)]), \
                 patch.object(gate, "docker_state", return_value=containers), \
                 patch.object(gate, "core_probe", return_value=observations):
                exit_code = gate.main()
            return exit_code, json.loads(output.read_text())

    def test_all_mocked_probes_pass_is_only_synthetic(self):
        code, report = self.run_gate(runtime(), probes())
        self.assertEqual(code, 0)
        self.assertEqual(report["verdict"], "PASS")
        self.assertTrue(report["read_only"])
        self.assertEqual(report["schema"], "aiops2-platform-readiness-v1")

    def test_missing_critical_probe_holds(self):
        p = probes()
        p.pop("twin_summary")
        code, report = self.run_gate(runtime(), p)
        self.assertEqual(code, 2)
        self.assertEqual(report["verdict"], "HOLD")
        self.assertIn("twin_summary:API_NOT_200", report["failures"])

    def test_stopped_postgres_holds(self):
        c = runtime()
        target = gate.INFRA["postgres"]
        next(item for item in c if item["Name"] == "/" + target)["State"]["Status"] = "exited"
        code, report = self.run_gate(c, probes())
        self.assertEqual(code, 2)
        self.assertIn("postgres:NOT_RUNNING", report["failures"])

    def test_docker_inspection_error_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "receipt.json"
            with patch.object(sys, "argv", ["gate", "--output", str(output)]), \
                 patch.object(gate, "docker_state", side_effect=RuntimeError("synthetic inspect failure")):
                code = gate.main()
            report = json.loads(output.read_text())
        self.assertEqual(code, 2)
        self.assertEqual(report["verdict"], "HOLD")
        self.assertIn("RuntimeError", report["error"])


if __name__ == "__main__":
    unittest.main()
