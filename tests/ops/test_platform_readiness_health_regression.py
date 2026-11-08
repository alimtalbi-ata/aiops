"""Offline regression: unhealthy Docker services cannot pass the platform gate."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ops" / "platform_readiness_gate.py"
spec = importlib.util.spec_from_file_location("platform_readiness_gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class ReadinessHealthRegression(unittest.TestCase):
    def run_gate(self, unhealthy=None):
        unhealthy = unhealthy or set()
        names = [v[0] for v in gate.SERVICES.values()] + list(gate.INFRA.values())
        containers = [
            {"Name": "/" + name, "Config": {"Image": "test:immutable"},
             "Image": "sha256:test", "State": {"Status": "running",
             "Health": {"Status": "unhealthy" if name in unhealthy else "healthy"}},
             "NetworkSettings": {"Networks": {"testnet": {}}}}
            for name in names
        ]
        probes = {key: {"http": 200} for key in
                  list(gate.SERVICES) + ["dashboard", "runs", "incidents", "twin_summary"]}
        with tempfile.TemporaryDirectory() as d, patch.object(gate, "docker_state", return_value=containers), \
             patch.object(gate, "core_probe", return_value=probes), \
             patch("sys.argv", ["gate", "--output", str(Path(d) / "receipt.json")]):
            rc = gate.main()
            report = json.loads((Path(d) / "receipt.json").read_text())
            return rc, report

    def test_all_healthy_passes_synthetic(self):
        rc, report = self.run_gate()
        self.assertEqual((rc, report["verdict"]), (0, "PASS"))

    def test_unhealthy_worker_holds_even_with_http_200(self):
        rc, report = self.run_gate({"aiops2-rebuild-worker"})
        self.assertEqual((rc, report["verdict"]), (2, "HOLD"))
        self.assertIn("worker:UNHEALTHY", report["failures"])

    def test_unhealthy_postgres_holds_even_if_running(self):
        rc, report = self.run_gate({"aiops2-rebuild-postgres"})
        self.assertEqual((rc, report["verdict"]), (2, "HOLD"))
        self.assertIn("postgres:UNHEALTHY", report["failures"])


if __name__ == "__main__":
    unittest.main()
