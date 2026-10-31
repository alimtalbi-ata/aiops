"""HTTP-level Analyst/Critic integration against the deterministic TEST_PROVIDER.

This verifies the real FastAPI adapter -> OpenAI-compatible HTTP -> schema guard
path. It is not a real-model accuracy or customer benchmark.
"""
import datetime
import pathlib
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer

from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from intelligence import main as intelligence
from test_provider.main import Handler


class IntelligenceHttpIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.provider = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.provider.serve_forever, daemon=True)
        cls.thread.start()
        cls.old = (intelligence.BASE, intelligence.MODEL, intelligence.KEY, intelligence.TOKEN)
        intelligence.BASE = f"http://127.0.0.1:{cls.provider.server_port}/v1"
        intelligence.MODEL = "deterministic-test-provider"
        intelligence.KEY = ""
        intelligence.TOKEN = "ci-intelligence-internal-token-only"

    @classmethod
    def tearDownClass(cls):
        intelligence.BASE, intelligence.MODEL, intelligence.KEY, intelligence.TOKEN = cls.old
        cls.provider.shutdown()
        cls.provider.server_close()
        cls.thread.join(timeout=2)

    def test_analyst_and_critic_are_real_http_calls_with_provider_usage(self):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        evidence = [
            {
                "evidence_id": "E-CI-FC-001",
                "source": "test-provider-fixture",
                "external_id": "CI-FC-001",
                "observed_at": now,
                "claim": "Synthetic FC error counter is elevated.",
                "confidence": 0.95,
                "provenance": {"synthetic": True, "observed_at": now, "adapter": "TEST_PROVIDER"},
                "payload": {"metric": "fc_errors", "value": 184, "unit": "errors/min", "status": "CRITICAL"},
            },
            {
                "evidence_id": "E-CI-HEALTH-001",
                "source": "test-provider-fixture",
                "external_id": "CI-HEALTH-001",
                "observed_at": now,
                "claim": "Synthetic SAN fabric health is degraded.",
                "confidence": 0.95,
                "provenance": {"synthetic": True, "observed_at": now, "adapter": "TEST_PROVIDER"},
                "payload": {"node_id": "ACME-SAN-FABRIC-A", "health": 0.42, "state": "DEGRADED"},
            },
        ]
        client = TestClient(intelligence.app)
        headers = {"Authorization": "Bearer ci-intelligence-internal-token-only"}
        request = {
            "incident": {"incident_id": "INC-CI-001", "title": "ACME SAN path degradation", "severity": "UNKNOWN", "synthetic": True},
            "evidence": evidence,
            "mode": "DEMO",
            "context": {"scenario": "ACME-SAN-PAYMENTS-CI", "synthetic": True},
        }

        analyst_response = client.post("/api/intelligence/analyze", json=request, headers=headers)
        self.assertEqual(analyst_response.status_code, 200, analyst_response.text)
        analyst = analyst_response.json()
        self.assertEqual(analyst["provider"], "openai-compatible")
        self.assertEqual(analyst["model"], "deterministic-test-provider")
        self.assertEqual(analyst["analysis"]["severity"], "P1")
        self.assertFalse(analyst["execution_allowed"])
        analyst_usage = analyst["model_invocation"]
        self.assertEqual(analyst_usage["usage_source"], "provider_reported")
        self.assertEqual(analyst_usage["total_tokens"], 2)
        self.assertIsNone(analyst_usage["cost_usd"])

        critic_request = {**request, "analyst": analyst["analysis"]}
        critic_response = client.post("/api/intelligence/critic", json=critic_request, headers=headers)
        self.assertEqual(critic_response.status_code, 200, critic_response.text)
        critic = critic_response.json()
        self.assertTrue(critic["critique"]["validated"])
        self.assertFalse(critic["execution_allowed"])
        critic_usage = critic["model_invocation"]
        self.assertEqual(critic_usage["usage_source"], "provider_reported")
        self.assertEqual(critic_usage["total_tokens"], 2)
        self.assertIsNone(critic_usage["cost_usd"])


if __name__ == "__main__":
    unittest.main()
