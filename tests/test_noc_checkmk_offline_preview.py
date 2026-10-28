"""Unit/contract tests for offline PR36 Checkmk/Livestatus port; no service integration."""
from __future__ import annotations

import json
import os
import pathlib
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from portal import noc_checkmk_export as preview  # noqa: E402

TOKEN = "synthetic-operator-read-token-not-a-real-secret"
NOW = datetime(2026, 10, 28, 4, 10, tzinfo=timezone.utc)


def sample():
    return {
        "schema": preview.SCHEMA,
        "source": "CHECKMK_EXPORT",
        "read_only": True,
        "live_remediation_authorized": False,
        "captured_at": "2026-10-28T04:09:00Z",
        "hosts": [
            {"name": "brocade-fc01", "state": 2, "output": "private: secret"},
            {"name": "payments-db01", "state": 0, "output": "SYNTHETIC"},
        ],
    }


class CheckmkExportContractTests(unittest.TestCase):
    def test_pr36_state_mapping_with_no_identity_or_output_disclosure(self):
        result = preview.preview_export(sample(), now=NOW)
        self.assertEqual(result["state_counts"], {"OK": 1, "WARN": 0, "CRIT": 1, "UNKNOWN": 0})
        self.assertEqual(result["claimed_capture_age_seconds"], 60)
        self.assertEqual(result["provenance"], "OPERATOR_EXPORT_UNVERIFIED")
        self.assertEqual(result["transport"], "OFFLINE_LIVESTATUS_EXPORT")
        self.assertFalse(result["source_runtime_observed"])
        self.assertFalse(result["tenant_acl_qualified"])
        self.assertFalse(result["live_remediation_authorized"])
        serialized = json.dumps(result)
        for secret in ("brocade-fc01", "payments-db01", "private: secret"):
            self.assertNotIn(secret, serialized)

    def test_reject_unreviewed_claims_and_tenant_fields(self):
        for key, value in (("tenant_id", "other"), ("production_qualified", True),
                           ("live_remediation_authorized", True), ("source", "LIVE")):
            payload = sample()
            payload[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                preview.preview_export(payload, now=NOW)
        for key in ("tenant_id", "command", "workspace_id"):
            payload = sample()
            payload["hosts"][0][key] = "other"
            with self.subTest(key=key), self.assertRaises(ValueError):
                preview.preview_export(payload, now=NOW)

    def test_stale_future_and_bad_timestamp_fail_closed(self):
        for stamp in ("2026-10-28T04:00:00Z", "2026-10-28T04:11:00Z",
                      "2026-10-28T04:09:00+00:00", "2026-10-28 04:09:00Z"):
            payload = sample()
            payload["captured_at"] = stamp
            with self.subTest(stamp=stamp), self.assertRaises(ValueError):
                preview.preview_export(payload, now=NOW)

    def test_invalid_states_duplicates_and_bounds_fail_closed(self):
        for rows in (
            [sample()["hosts"][0]] * 2,
            [{"name": "x", "state": True, "output": "x"}],
            [{"name": "x", "state": 9, "output": "x"}],
            [{"name": "x", "state": "0", "output": "x"}],
            [{"name": "x", "state": 0, "output": "x" * 1001}],
            [{"name": "x/../y", "state": 0, "output": "x"}],
            [],
        ):
            payload = sample()
            payload["hosts"] = rows
            with self.subTest(rows=str(rows)[:50]), self.assertRaises(ValueError):
                preview.preview_export(payload, now=NOW)


class CheckmkExportEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.include_router(preview.router)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def test_auth_required_before_body_parse_and_no_cache(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN}):
            response = self.client.post("/api/noc/checkmk-export/preview", data=b"{bad",
                                        headers={"Content-Type": "application/json"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.json()["detail"], "invalid_portal_read_token")

    def test_missing_operator_config_fails_closed(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": ""}):
            response = self.client.post("/api/noc/checkmk-export/preview",
                                        headers={"Authorization": "Bearer " + TOKEN,
                                                 "Content-Type": "application/json"}, content=b"{}")
        self.assertEqual(response.status_code, 503)

    def test_duplicate_json_keys_and_nonfinite_rejected(self):
        for body in (b'{"schema":"a","schema":"b"}', b'{"x":NaN}', b"[]", b"not-json"):
            with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN}):
                response = self.client.post("/api/noc/checkmk-export/preview",
                                            content=body, headers={"Authorization": "Bearer " + TOKEN,
                                                                   "Content-Type": "application/json"})
            with self.subTest(body=body):
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.headers["cache-control"], "no-store")

    def test_body_limit_and_content_type_rejected(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN}):
            too_big = self.client.post("/api/noc/checkmk-export/preview",
                                       content=b"x" * (preview.MAX_BODY_BYTES + 1),
                                       headers={"Authorization": "Bearer " + TOKEN,
                                                "Content-Type": "application/json"})
            wrong_type = self.client.post("/api/noc/checkmk-export/preview",
                                          content=b"{}", headers={"Authorization": "Bearer " + TOKEN,
                                                                  "Content-Type": "text/plain"})
        self.assertEqual(too_big.status_code, 413)
        self.assertEqual(wrong_type.status_code, 415)

    def test_valid_api_response_never_claims_live(self):
        payload = sample()
        payload["captured_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN}):
            response = self.client.post("/api/noc/checkmk-export/preview", json=payload,
                                        headers={"Authorization": "Bearer " + TOKEN})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["state"], "UNVERIFIED_OFFLINE_EXPORT")
        self.assertFalse(response.json()["source_runtime_observed"])
        self.assertEqual(response.headers["cache-control"], "no-store")


if __name__ == "__main__":
    unittest.main()
