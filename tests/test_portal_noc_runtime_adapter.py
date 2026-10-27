"""Offline tests for the signed, read-only NOC upstream bridge."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import pathlib
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

APP_ROOT = pathlib.Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from portal import noc_runtime  # noqa: E402


HMAC_KEY = "synthetic-hmac-key-for-offline-tests-32-bytes-minimum"
TOKEN = "synthetic-upstream-token-not-a-real-secret"
PORTAL_TOKEN = "synthetic-portal-read-token"
ORIGIN = "https://noc.example.test"
URL = ORIGIN + "/api/read-model"
NOW = datetime.now(timezone.utc).replace(microsecond=0)


def fixture_payload():
    return {
        "schema": noc_runtime.SCHEMA,
        "provenance": "RUNTIME_READMODEL",
        "run_id": "RUN-ACME-001",
        "incident_id": "INC-ACME-SAN-001",
        "correlation_id": "CORR-001",
        "ticket_id": "SIM-GLPI-001",
        "event_timestamp_utc": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "observed_at": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "evidence_sha256": "a" * 64,
        "steps": [{"name": "detect", "state": "WARN", "private_note": "not projected"}],
        "runtime_authenticated": True,
        "live_remediation_authorized": False,
    }


def signed_response(payload=None, raw=None):
    body = raw if raw is not None else json.dumps(
        payload if payload is not None else fixture_payload(),
        separators=(",", ":"),
    ).encode("utf-8")
    return body, {
        "X-AIOps-Read-Model-SHA256": hashlib.sha256(body).hexdigest(),
        "X-AIOps-Read-Model-Signature": hmac.new(
            HMAC_KEY.encode(), body, hashlib.sha256
        ).hexdigest(),
    }


class NocSignedPayloadTests(unittest.TestCase):
    def project(self, payload=None, raw=None, headers=None, now=NOW):
        body, valid_headers = signed_response(payload, raw)
        valid_headers.update(headers or {})
        return noc_runtime._project_signed_payload(
            body,
            digest_header=valid_headers.get("X-AIOps-Read-Model-SHA256"),
            signature_header=valid_headers.get("X-AIOps-Read-Model-Signature"),
            hmac_key=HMAC_KEY.encode(),
            source_origin=ORIGIN,
            now=now,
        )

    def test_signed_payload_projects_only_allowlisted_fields_and_never_attests_runtime(self):
        view = self.project()
        self.assertEqual(view["source_authentication"], "HMAC_SHA256_VERIFIED")
        self.assertIs(view["source_payload_authenticated"], True)
        self.assertIs(view["runtime_attested"], False)
        self.assertIs(view["runtime_authenticated"], False)
        self.assertIs(view["live_remediation_authorized"], False)
        self.assertEqual(view["ticket_id"], "SIM-GLPI-001")
        self.assertEqual(view["ticket_provenance"], "UPSTREAM_SIGNED_CLAIM")
        self.assertEqual(view["evidence_status"], "DIGEST_REPORTED_NOT_BYTES_VERIFIED")
        self.assertEqual(view["handoff_status"], "ABSENT")
        self.assertNotIn("private_note", view["steps"][0])
        self.assertNotIn("runtime_authenticated", view)

    def test_digest_and_signature_must_both_match(self):
        for headers in (
            {"X-AIOps-Read-Model-SHA256": "0" * 64},
            {"X-AIOps-Read-Model-Signature": "0" * 64},
            {"X-AIOps-Read-Model-Signature": "A" * 64},
            {"X-AIOps-Read-Model-Signature": None},
        ):
            with self.subTest(headers=headers), self.assertRaises(ValueError):
                self.project(headers=headers)

    def test_duplicate_json_keys_and_non_object_roots_are_rejected(self):
        for raw in (
            b'{"schema":"x","schema":"y"}',
            b"[]",
            b'{"x":NaN}',
            b"\xff",
        ):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.project(raw=raw)

    def test_stale_future_and_ambiguous_timestamps_are_rejected(self):
        invalid_values = (
            (NOW.replace(year=NOW.year - 1).strftime("%Y-%m-%dT%H:%M:%SZ"), NOW),
            ((NOW.replace(year=NOW.year + 1)).strftime("%Y-%m-%dT%H:%M:%SZ"), NOW),
            (" " + NOW.strftime("%Y-%m-%dT%H:%M:%SZ"), NOW),
            (NOW.strftime("%Y-%m-%d %H:%M:%SZ"), NOW),
            (NOW.strftime("%Y-%m-%dT%H:%M:%S+00:00"), NOW),
        )
        for observed, clock in invalid_values:
            payload = fixture_payload()
            payload["observed_at"] = observed
            raw = json.dumps(payload, separators=(",", ":")).encode()
            with self.subTest(observed=observed), self.assertRaises(ValueError):
                self.project(raw=raw, now=clock)

    def test_source_cannot_promote_live_remediation_evidence_or_production(self):
        for field in ("live_remediation_authorized", "evidence_runtime_attested",
                      "production_qualified"):
            payload = fixture_payload()
            payload[field] = True
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.project(payload=payload)

    def test_malformed_states_and_unverified_handoff_claims_fail_closed(self):
        for mutate in (
            lambda p: p.update({"steps": [{"name": "x", "state": []}]}),
            lambda p: p.update({"steps": [{"name": "x", "state": {"state": "OK"}}]}),
            lambda p: p.update({"handoff_02_03": {"runtime_authenticated": True}}),
            lambda p: p.update({"handoff_identity_sha256": "a" * 64}),
        ):
            payload = fixture_payload()
            mutate(payload)
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.project(payload=payload)

    def test_missing_ticket_and_evidence_are_explicitly_absent(self):
        payload = fixture_payload()
        payload.pop("ticket_id")
        payload.pop("evidence_sha256")
        payload.pop("event_timestamp_utc")
        view = self.project(payload=payload)
        self.assertIsNone(view["ticket_id"])
        self.assertEqual(view["ticket_provenance"], "ABSENT")
        self.assertIsNone(view["evidence_sha256"])
        self.assertEqual(view["evidence_status"], "ABSENT")
        self.assertIsNone(view["event_timestamp_utc"])
        self.assertEqual(view["event_timestamp_provenance"], "ABSENT")


class FakeResponse:
    def __init__(self, body, headers, url):
        self._body = body
        self.headers = headers
        self._url = url
        self.status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def getcode(self):
        return self.status

    def geturl(self):
        return self._url

    def read(self, limit=-1):
        return self._body[:limit]


class FakeOpener:
    def __init__(self, response):
        self.response = response
        self.request = None
        self.timeout = None

    def open(self, request, timeout):
        self.request = request
        self.timeout = timeout
        return self.response


class NocRuntimeRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = FastAPI()
        cls.app.include_router(noc_runtime.router)
        cls.client = TestClient(cls.app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def test_upstream_request_is_allowlisted_get_and_verifies_exact_signed_bytes(self):
        body, signed_headers = signed_response()
        headers = {
            **signed_headers,
            "Content-Type": "application/json; charset=utf-8",
            "Content-Length": str(len(body)),
        }
        response = FakeResponse(body, headers, URL)
        opener = FakeOpener(response)
        env = {
            "AIOPS_NOC_READ_MODEL_URL": URL,
            "AIOPS_NOC_READ_MODEL_TOKEN": TOKEN,
            "AIOPS_NOC_READ_MODEL_HMAC_KEY": HMAC_KEY,
            "AIOPS_NOC_ALLOWED_ORIGINS": ORIGIN,
        }
        with patch.dict(os.environ, env), patch.object(
            noc_runtime.urllib.request, "build_opener", return_value=opener
        ) as builder:
            view = noc_runtime.read_signed_noc_snapshot()
        builder.assert_called_once()
        proxy_handler, redirect_handler = builder.call_args.args
        self.assertIsInstance(proxy_handler, noc_runtime.urllib.request.ProxyHandler)
        self.assertEqual(proxy_handler.proxies, {})
        self.assertIsInstance(redirect_handler, noc_runtime._NoRedirect)
        self.assertEqual(opener.request.get_method(), "GET")
        self.assertEqual(opener.request.get_header("Authorization"), "Bearer " + TOKEN)
        self.assertEqual(opener.timeout, noc_runtime.TIMEOUT_SECONDS)
        self.assertEqual(view["source_origin"], ORIGIN)
        self.assertEqual(view["source_authentication"], "HMAC_SHA256_VERIFIED")
        self.assertIs(view["runtime_attested"], False)

    def test_declared_response_length_must_match_signed_body(self):
        body, signed_headers = signed_response()
        headers = {
            **signed_headers,
            "Content-Type": "application/json",
            "Content-Length": str(len(body) + 1),
        }
        opener = FakeOpener(FakeResponse(body, headers, URL))
        env = {
            "AIOPS_NOC_READ_MODEL_URL": URL,
            "AIOPS_NOC_READ_MODEL_TOKEN": TOKEN,
            "AIOPS_NOC_READ_MODEL_HMAC_KEY": HMAC_KEY,
            "AIOPS_NOC_ALLOWED_ORIGINS": ORIGIN,
        }
        with patch.dict(os.environ, env), patch.object(
            noc_runtime.urllib.request, "build_opener", return_value=opener
        ):
            with self.assertRaisesRegex(ValueError, "body length mismatch"):
                noc_runtime.read_signed_noc_snapshot()

    def test_malformed_upstream_token_is_rejected_before_network_access(self):
        env = {
            "AIOPS_NOC_READ_MODEL_URL": URL,
            "AIOPS_NOC_READ_MODEL_TOKEN": "token with spaces and newline",
            "AIOPS_NOC_READ_MODEL_HMAC_KEY": HMAC_KEY,
            "AIOPS_NOC_ALLOWED_ORIGINS": ORIGIN,
        }
        with patch.dict(os.environ, env), patch.object(
            noc_runtime.urllib.request, "build_opener",
            side_effect=AssertionError("invalid token must not open network"),
        ):
            with self.assertRaisesRegex(ValueError, "credentials"):
                noc_runtime.read_signed_noc_snapshot()

    def test_disallowed_origin_is_rejected_before_network_access(self):
        env = {
            "AIOPS_NOC_READ_MODEL_URL": "https://other.example.test/api/read-model",
            "AIOPS_NOC_READ_MODEL_TOKEN": TOKEN,
            "AIOPS_NOC_READ_MODEL_HMAC_KEY": HMAC_KEY,
            "AIOPS_NOC_ALLOWED_ORIGINS": ORIGIN,
        }
        with patch.dict(os.environ, env), patch.object(
            noc_runtime.urllib.request, "build_opener",
            side_effect=AssertionError("disallowed origin must not open network"),
        ):
            with self.assertRaisesRegex(ValueError, "not allowlisted"):
                noc_runtime.read_signed_noc_snapshot()

    def test_redirect_handler_never_follows_upstream_redirects(self):
        handler = noc_runtime._NoRedirect()
        self.assertIsNone(
            handler.redirect_request(None, None, 302, "Found", {}, URL + "/elsewhere")
        )

    def test_route_requires_portal_read_auth_before_any_upstream_call(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": PORTAL_TOKEN}), patch.object(
            noc_runtime, "read_signed_noc_snapshot",
            side_effect=AssertionError("must not contact upstream"),
        ):
            response = self.client.get("/api/noc/runtime-state")
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json()["detail"], "invalid_portal_read_token")
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertEqual(response.headers["pragma"], "no-cache")

    def test_route_auth_configuration_failure_is_not_cached_and_never_contacts_upstream(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": ""}), patch.object(
            noc_runtime, "read_signed_noc_snapshot",
            side_effect=AssertionError("must not contact upstream"),
        ):
            response = self.client.get(
                "/api/noc/runtime-state",
                headers={"Authorization": "Bearer " + PORTAL_TOKEN},
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "portal_read_auth_not_configured")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["pragma"], "no-cache")

    def test_route_reports_unconfigured_source_without_network_access(self):
        env = {
            "AIOPS_PORTAL_READ_TOKEN": PORTAL_TOKEN,
            "AIOPS_NOC_READ_MODEL_URL": "",
            "AIOPS_NOC_READ_MODEL_TOKEN": "",
            "AIOPS_NOC_READ_MODEL_HMAC_KEY": "",
            "AIOPS_NOC_ALLOWED_ORIGINS": "",
        }
        with patch.dict(os.environ, env), patch.object(
            noc_runtime.urllib.request, "build_opener",
            side_effect=AssertionError("must not open network"),
        ):
            response = self.client.get(
                "/api/noc/runtime-state",
                headers={"Authorization": "Bearer " + PORTAL_TOKEN},
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "noc_source_not_configured")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["pragma"], "no-cache")

    def test_route_returns_only_verified_projection_and_no_store(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": PORTAL_TOKEN}), patch.object(
            noc_runtime, "read_signed_noc_snapshot", return_value=self._safe_view(),
        ):
            response = self.client.get(
                "/api/noc/runtime-state",
                headers={"Authorization": "Bearer " + PORTAL_TOKEN},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertIs(response.json()["runtime_attested"], False)
        self.assertIs(response.json()["live_remediation_authorized"], False)

    def test_route_redacts_upstream_exceptions(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": PORTAL_TOKEN}), patch.object(
            noc_runtime, "read_signed_noc_snapshot",
            side_effect=RuntimeError("PRIVATE-TOKEN-AND-UPSTREAM-BODY"),
        ):
            response = self.client.get(
                "/api/noc/runtime-state",
                headers={"Authorization": "Bearer " + PORTAL_TOKEN},
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "noc_source_unavailable_or_unverified")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["pragma"], "no-cache")
        self.assertNotIn("PRIVATE-TOKEN", response.text)

    @staticmethod
    def _safe_view():
        body, headers = signed_response()
        return noc_runtime._project_signed_payload(
            body,
            digest_header=headers["X-AIOps-Read-Model-SHA256"],
            signature_header=headers["X-AIOps-Read-Model-Signature"],
            hmac_key=HMAC_KEY.encode(),
            source_origin=ORIGIN,
            now=NOW,
        )


if __name__ == "__main__":
    unittest.main()
