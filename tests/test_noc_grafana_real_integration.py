"""Real Grafana container integration test. Never replace Grafana with a stub."""
import os
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from portal.noc_grafana_health import read_grafana_health

class RealGrafanaIntegration(unittest.TestCase):
    @unittest.skipUnless(os.getenv("AIOPS_REAL_GRAFANA_CI") == "true",
                         "NOT_TESTED: real Grafana service not enabled")
    def test_real_grafana_http_readiness(self):
        result = read_grafana_health()
        self.assertEqual(result["state"], "GRAFANA_HTTP_READY_UNATTESTED")
        self.assertEqual(result["source"], "REAL_GRAFANA_HTTP_HEALTH")
        self.assertTrue(result["grafana_http_checked"])
        self.assertEqual(result["grafana_observation"], "NOT_TESTED")
        self.assertFalse(result["production_qualified"])
