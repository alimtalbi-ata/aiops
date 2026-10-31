"""Contract/security tests: HMAC does not grant tenant access (no service integration)."""
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

ROOT = pathlib.Path(__file__).resolve().parents[1] / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from portal import noc_runtime

KEY = b"synthetic-test-hmac-key-not-production-32bytes"
TOKEN = "synthetic-portal-read-token"
NOW = datetime.now(timezone.utc).replace(microsecond=0)


def payload():
    return {
        "schema": noc_runtime.SCHEMA,
        "provenance": "RUNTIME_READMODEL",
        "run_id": "RUN-DEMO-001",
        "incident_id": "INC-DEMO-001",
        "observed_at": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "steps": [{"name": "detect", "state": "WARN"}],
        "live_remediation_authorized": False,
    }


def signed_project(data):
    raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return noc_runtime._project_signed_payload(
        raw,
        digest_header=hashlib.sha256(raw).hexdigest(),
        signature_header=hmac.new(KEY, raw, hashlib.sha256).hexdigest(),
        hmac_key=KEY,
        source_origin="https://noc.example.test",
        now=NOW,
    )


class TenantScopeFenceTests(unittest.TestCase):
    def test_unscoped_signed_read_model_still_projects(self):
        view = signed_project(payload())
        self.assertEqual(view["source_authentication"], "HMAC_SHA256_VERIFIED")
        self.assertFalse(view["runtime_attested"])
        self.assertFalse(view["live_remediation_authorized"])

    def test_root_claims_rejected_even_when_null_or_false(self):
        for name, value in (
            ("tenant_id", None),
            ("tenantId", "secret-tenant"),
            ("organization_id", "other-org"),
            ("org_id", 1),
            ("workspace-id", False),
            ("accountID", "account-2"),
            ("customer_id", ""),
            ("tenant_acl_qualified", True),
            ("ｔｅｎａｎｔ＿ｉｄ", "unicode-confusable"),
        ):
            with self.subTest(name=name):
                data = payload()
                data[name] = value
                with self.assertRaisesRegex(ValueError, "qualified ACL"):
                    signed_project(data)

    def test_nested_claims_rejected_in_steps_and_unknown_metadata(self):
        for extra in (
            {"steps": [{"name": "detect", "state": "WARN", "meta": {"tenantId": None}}]},
            {"extra": {"any": [{"workspace": "secret-workspace"}]}},
            {"extra": [{"org_name": "secret-organization"}]},
        ):
            with self.subTest(extra=extra):
                data = payload()
                data.update(extra)
                with self.assertRaisesRegex(ValueError, "qualified ACL") as caught:
                    signed_project(data)
                self.assertNotIn("secret-", str(caught.exception))

    def test_indirect_scope_aliases_rejected_before_projection(self):
        # A signed envelope is not an ACL decision, even for indirect claims.
        for key in ("ownerTenantId", "source_tenant", "projectTenantID",
                    "orgRef", "organizationRef", "workspaceRef",
                    "accountRef", "customerRef", "billingAccountID"):
            with self.subTest(key=key):
                data = payload()
                data["extra"] = {"metadata": [{key: "SECRET-OTHER-TENANT"}]}
                with self.assertRaisesRegex(ValueError, "qualified ACL") as caught:
                    signed_project(data)
                self.assertNotIn("SECRET-OTHER-TENANT", str(caught.exception))

    def test_unrelated_metadata_does_not_change_unscoped_contract(self):
        data = payload()
        data["extra"] = {"organelle": "non-scope",
                         "accounting_state": "demo",
                         "customer_impact": "synthetic"}
        view = signed_project(data)
        self.assertEqual(view["source_authentication"], "HMAC_SHA256_VERIFIED")
        self.assertFalse(view["live_remediation_authorized"])

    def test_bounded_scan_refuses_oversized_nested_metadata(self):
        data = payload()
        data["extra"] = [{} for _ in range(4200)]
        with self.assertRaisesRegex(ValueError, "scan bound"):
            signed_project(data)

    def test_signed_scoped_payload_is_redacted_by_actual_route(self):
        data = payload()
        data["steps"][0]["tenantId"] = "SECRET-TENANT-VALUE"
        app = FastAPI()
        app.include_router(noc_runtime.router)
        with TestClient(app) as client, patch.dict(os.environ, {
            "AIOPS_PORTAL_READ_TOKEN": TOKEN
        }), patch.object(noc_runtime, "read_signed_noc_snapshot",
                        side_effect=AssertionError("no source read")) as read:
            response = client.get("/api/noc/runtime-state",
                                  headers={"Authorization": "Bearer " + TOKEN})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["reason"], "TENANT_ACL_NOT_QUALIFIED")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertNotIn("SECRET-TENANT-VALUE", response.text)
        read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
