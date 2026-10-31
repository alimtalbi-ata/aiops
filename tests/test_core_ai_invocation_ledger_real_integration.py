"""Real PostgreSQL/Core integration for provider-reported Analyst/Critic telemetry."""
import hashlib
import json
import os
import unittest
import uuid

import psycopg
import requests
from psycopg.types.json import Jsonb

BASE = os.environ.get("CORE_URL", "http://127.0.0.1:1810")
TOKEN = os.environ["AIOPS_INTERNAL_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]


class CoreAIInvocationLedgerIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        suffix = uuid.uuid4().hex[:10]
        cls.incident_id = "INC-CI-AI-" + suffix
        cls.run_id = "RUN-CI-AI-" + suffix
        cls.evidence_id = "E-CI-AI-" + suffix
        cls.headers = {"Authorization": "Bearer " + TOKEN}
        with psycopg.connect(DATABASE_URL) as c:
            c.execute(
                "insert into aiops.incidents(incident_id,external_id,title,severity,state,opened_at,source,synthetic,payload) "
                "values(%s,%s,%s,'P1','OPEN',now(),'ci-ai-ledger',true,%s)",
                (cls.incident_id, cls.incident_id, "Synthetic ACME SAN ledger test", Jsonb({"synthetic": True})),
            )
            c.execute(
                "insert into aiops.runs(run_id,incident_id,mode,scenario_id,status,idempotency_key) "
                "values(%s,%s,'DEMO','CI-AI-LEDGER','CREATED',%s)",
                (cls.run_id, cls.incident_id, "ci-ai-ledger-" + suffix),
            )
            evidence_payload = {"metric": "fc_errors", "value": 184}
            payload_hash = hashlib.sha256(json.dumps(evidence_payload, sort_keys=True).encode()).hexdigest()
            c.execute(
                "insert into aiops.evidence(evidence_id,source,external_id,observed_at,claim,confidence,provenance,payload_hash,payload) "
                "values(%s,'ci-fixture',%s,now(),%s,0.95,%s,%s,%s)",
                (cls.evidence_id, cls.evidence_id, "Synthetic FC error metric", Jsonb({"synthetic": True}), payload_hash, Jsonb(evidence_payload)),
            )

    def test_analysis_and_critique_usage_are_persisted_and_returned(self):
        analyst_usage = {
            "invocation_id": "ci-analyst-invocation-001",
            "latency_ms": 421.7,
            "request_count": 1,
            "retry_count": 0,
            "prompt_tokens": 123,
            "completion_tokens": 32,
            "total_tokens": 155,
            "cached_tokens": 8,
            "reasoning_tokens": 0,
            "usage_source": "provider_reported",
            "status": "success",
            "cost_usd": None,
            "pricing_source": None,
            "api_key": "must-never-be-persisted",
        }
        analyst = {
            "contract_version": "2.0",
            "severity": "P1",
            "confidence": 0.91,
            "confidence_basis": "provider response grounded in supplied evidence",
        }
        r = requests.post(
            f"{BASE}/api/runs/{self.run_id}/analysis-record",
            headers=self.headers,
            json={
                "analysis": analyst,
                "evidence_ids": [self.evidence_id],
                "idempotency_key": "CI-ANALYST-" + self.run_id,
                "provider": "openai-compatible",
                "model": "ci-deterministic-provider",
                "prompt_version": "analyst-v2.2",
                "model_invocation": analyst_usage,
            },
            timeout=5,
        )
        self.assertEqual(r.status_code, 200, r.text)
        analysis_id = r.json()["analysis_id"]

        critic_usage = {
            "invocation_id": "ci-critic-invocation-001",
            "latency_ms": 287.4,
            "request_count": 1,
            "retry_count": 0,
            "prompt_tokens": 99,
            "completion_tokens": 24,
            "total_tokens": 123,
            "cached_tokens": 0,
            "reasoning_tokens": 0,
            "usage_source": "provider_reported",
            "status": "success",
            "cost_usd": None,
            "pricing_source": None,
        }
        critique = {
            "contract_version": "2.0",
            "validated": True,
            "issues": [],
            "diagnostic_confidence": 0.89,
            "final_recommendation": "OBSERVE",
        }
        r = requests.post(
            f"{BASE}/api/runs/{self.run_id}/critique-record",
            headers=self.headers,
            json={
                "critique": critique,
                "analysis_id": analysis_id,
                "evidence_ids": [self.evidence_id],
                "idempotency_key": "CI-CRITIC-" + self.run_id,
                "provider": "openai-compatible",
                "model": "ci-deterministic-provider",
                "model_invocation": critic_usage,
            },
            timeout=5,
        )
        self.assertEqual(r.status_code, 200, r.text)

        r = requests.get(f"{BASE}/api/runs/{self.run_id}/ai-ledger", headers=self.headers, timeout=5)
        self.assertEqual(r.status_code, 200, r.text)
        ledger = r.json()
        self.assertEqual(len(ledger["analyses"]), 1)
        self.assertEqual(len(ledger["critiques"]), 1)
        a = ledger["analyses"][0]["model_invocation"]
        self.assertEqual(a["total_tokens"], 155)
        self.assertEqual(a["usage_source"], "provider_reported")
        self.assertEqual(a["latency_ms"], 421.7)
        self.assertIsNone(a["cost_usd"])
        self.assertNotIn("api_key", a)
        c = ledger["critiques"][0]["model_invocation"]
        self.assertEqual(c["total_tokens"], 123)
        self.assertEqual(c["usage_source"], "provider_reported")
        self.assertIsNone(c["cost_usd"])


if __name__ == "__main__":
    unittest.main()
