"""Source-backed Demo Studio V2 status rendering; no runtime calls or LIVE claim."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
os.environ.setdefault("AIOPS_INTERNAL_TOKEN", "ci-demo-studio-only-not-production")

from portal import main
from portal.demo_v2 import _source, render_demo_v2


class DemoStudioSourceStates(unittest.TestCase):
    @staticmethod
    def http_error(status):
        response = requests.Response()
        response.status_code = status
        response.url = "http://internal.invalid/secret-token-in-url"
        return requests.HTTPError("sensitive-token-must-not-leak", response=response)

    def test_401_from_actual_transport_is_explicit_without_leaking_details(self):
        with patch.object(main, "get_json", side_effect=self.http_error(401)):
            state = main._get("/api/runs/RUN-DEMO/ai-ledger")
        self.assertEqual(state, {"status": "UNKNOWN", "error_type": "HTTPError", "http_status": 401})
        self.assertIn("HTTP 401", _source(state))
        rendered = render_demo_v2({"run": {"run_id": "RUN-DEMO", "mode": "DEMO"},
                                   "events": []}, state, {"items": []})
        self.assertIn("HTTP 401", rendered)
        self.assertNotIn("sensitive-token", rendered)
        self.assertNotIn("internal.invalid", rendered)
        self.assertNotIn("DISPONIBLE — données reçues", _source(state))

    def test_403_distinct_from_401(self):
        with patch.object(main, "get_json", side_effect=self.http_error(403)):
            state = main._get("/api/runs/RUN-DEMO/gates")
        self.assertEqual(state["http_status"], 403)
        self.assertIn("HTTP 403", _source(state))
        self.assertNotIn("HTTP 401", _source(state))

    def test_500_and_transport_failure_remain_unknown_not_auth_denied(self):
        with patch.object(main, "get_json", side_effect=self.http_error(500)):
            self.assertIn("INCONNU", _source(main._get("/api/runs/RUN-DEMO/ai-ledger")))
        with patch.object(main, "get_json", side_effect=requests.Timeout("secret")):
            state = main._get("/api/runs/RUN-DEMO/ai-ledger")
        self.assertEqual(state, {"status": "UNKNOWN", "error_type": "Timeout"})
        self.assertIn("INCONNU", _source(state))

    def test_unverified_json_cannot_claim_transport_401(self):
        self.assertIn("INCONNU", _source({"status": "UNKNOWN", "http_status": 401}))
        self.assertIn("INCONNU", _source({"status": "UNKNOWN", "error_type": "Timeout", "http_status": 401}))
        self.assertIn("INCONNU", _source({"status": "UNKNOWN", "error_type": "HTTPError", "http_status": "401"}))
        self.assertIn("INCONNU", _source({"error_type": "HTTPError"}))
        self.assertIn("INCONNU", _source({}))
        self.assertIn("INCONNU", _source(None))

    def test_valid_source_does_not_claim_runtime_attestation(self):
        self.assertIn("non attestées", _source({"items": []}))
        self.assertIn("non attestées", _source({"decision": "SIMULATE"}))
        self.assertNotIn("HTTP 401", _source({"items": []}))


if __name__ == "__main__":
    unittest.main()
