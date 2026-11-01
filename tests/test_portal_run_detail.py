"""Main-based Portal Run detail tests: offline mocks only, no Core/GLPI/DB I/O."""
import os
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "ci-only-core-test-token"}):
    from portal import main, acme_run_detail
from fastapi.testclient import TestClient

TOKEN = "ci-only-portal-viewer-token"
RID = "RUN-73AFC6FF9315376C"
IID = "INC-GOLDEN-P1-1edd0de6f46546e294139bf68d73d65a"


def run(**changes):
    return {"run_id": RID, "incident_id": IID, "mode": "DEMO",
            "status": "RESOLVED", **changes}


class RunDetailTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.env = patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN, "AIOPS_PORTAL_COOKIE_SECURE": "false"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.client.close()

    def get(self, path=None, authorized=True):
        return self.client.get(path or "/api/portal/runs/" + RID, headers=(
            {"Authorization": "Bearer " + TOKEN} if authorized else {}))

    def test_authenticated_unscoped_identity_never_claims_evidence_or_hitl(self):
        with patch.object(acme_run_detail, "_read_core_run", return_value=run()) as core:
            response = self.get()
        self.assertEqual(response.status_code, 503)
        core.assert_not_called()
        data = response.json()
        self.assertEqual(data["state"], "UNKNOWN")
        self.assertEqual(data["reason"], "TENANT_ACL_NOT_QUALIFIED")
        self.assertEqual(data["connection_state"], "UNKNOWN")
        self.assertEqual(data["provenance"], "UNKNOWN")
        for private_field in ("run_id", "incident_id", "mode", "run_status"):
            self.assertNotIn(private_field, data)
        self.assertNotIn(IID, response.text)
        self.assertEqual(data["source_freshness"], "UNKNOWN")
        self.assertIsNone(data["source_observed_at"])
        self.assertFalse(data["tenant_acl_qualified"])
        self.assertFalse(data["runtime_attested"])
        self.assertFalse(data["live_remediation_authorized"])
        for key in ("Incident", "Run", "Evidence", "AI Ledger", "Policy", "HITL", "Verification", "GLPI"):
            self.assertEqual(data["journey"][key]["state"], "UNKNOWN")
        self.assertEqual(data["journey"]["GLPI"]["reason"],
                         "NO_TENANT_SCOPED_TICKET_RUN_LINK")
        self.assertEqual(data["journey"]["Evidence"]["reason"],
                         "CORE_BEARER_EVIDENCE_REFS_ENDPOINT_MISSING")
        self.assertNotIn("ticket_id", response.text)
        self.assertNotIn("evidence_id", response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-frame-options"], "DENY")


    def test_valid_core_identity_is_not_disclosed_without_tenant_acl(self):
        # Internal bearer authenticates Portal->Core, not the human/tenant.
        private_incident = "INC-PRIVATE-CUSTOMER"
        with patch.object(acme_run_detail, "_read_core_run",
                          return_value=run(incident_id=private_incident, status="FAILED")):
            api = self.get()
            page = self.get("/runs/" + RID)
        self.assertEqual(api.status_code, 503)
        self.assertEqual(page.status_code, 503)
        self.assertEqual(api.json()["reason"], "TENANT_ACL_NOT_QUALIFIED")
        self.assertEqual(api.json()["connection_state"], "UNKNOWN")
        for response in (api, page):
            self.assertNotIn(private_incident, response.text)
            self.assertNotIn("FAILED", response.text)
            self.assertNotIn("Core-verified Run", response.text)
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertNotIn("run_id", api.json())
        self.assertNotIn("incident_id", api.json())
        self.assertNotIn("run_status", api.json())
        self.assertIn('data-story-provenance="SYNTHETIC"', page.text)

    def test_valid_bearer_never_fetches_core_without_server_derived_acl(self):
        # Both API and HTML must refuse before Core even for syntactically
        # valid but forged/cross-tenant Run IDs. The viewer token is not ACL.
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=AssertionError("Core must not be called")) as core:
            for rid in (RID, "RUN-FOREIGN-TENANT", "RUN-FORGED-999"):
                for route in ("/api/portal/runs/", "/runs/"):
                    with self.subTest(rid=rid, route=route):
                        response = self.get(route + rid)
                        self.assertEqual(response.status_code, 503)
                        self.assertNotIn("CONNECTED", response.text)
                        self.assertEqual(response.headers["cache-control"], "no-store")
                        self.assertEqual(response.headers["x-frame-options"], "DENY")
                        self.assertIn("frame-ancestors 'none'",
                                      response.headers["content-security-policy"])
            core.assert_not_called()

    def test_auth_missing_and_wrong_never_touch_core(self):
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=AssertionError("no Core read")) as core:
            for headers in ({}, {"Authorization": "Bearer wrong"}):
                response = self.client.get("/api/portal/runs/" + RID, headers=headers)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json()["state"], "UNAUTHORIZED")
            core.assert_not_called()

    def test_auth_unconfigured_stays_unknown_without_core_read(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": ""}), patch.object(
                acme_run_detail, "_read_core_run",
                side_effect=AssertionError("no Core read")):
            response = self.get()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["state"], "UNKNOWN")

    def test_upstream_denials_cannot_be_probed_before_tenant_acl(self):
        # Upstream 401/403 cannot be surfaced until the actor+tenant ACL is
        # qualified; the Portal must not make this network request at all.
        for code in (401, 403):
            with self.subTest(code=code), patch.object(
                    acme_run_detail, "_read_core_run",
                    side_effect=urllib.error.HTTPError("http://core", code, "secret", {}, None)) as core:
                response = self.get()
                core.assert_not_called()
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["state"], "UNKNOWN")
            self.assertEqual(response.json()["reason"], "TENANT_ACL_NOT_QUALIFIED")
            self.assertNotIn("secret", response.text)

    def test_invalid_identifier_refused_before_core(self):
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=AssertionError("no Core read")):
            response = self.get("/api/portal/runs/RUN-bad!")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["state"], "UNKNOWN")

    def test_foreign_run_and_live_are_unknown_not_replaced(self):
        for invalid in (run(run_id="RUN-FOREIGN"), run(mode="LIVE"),
                        run(incident_id="INC-FOREIGN"), run(status="")):
            with self.subTest(invalid=invalid), patch.object(
                    acme_run_detail, "_read_core_run", return_value=invalid):
                response = self.get()
            # Even syntactically valid foreign identity is tenant data.
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["state"], "UNKNOWN")
            self.assertNotIn("INC-FOREIGN", response.text)

    def test_core_status_must_match_canonical_domain_enum(self):
        # An arbitrary Core string must not be displayed as an approved,
        # connected or runtime-verified Run state.
        for invalid in ("APPROVED", "CONNECTED", "PASS", "LIVE",
                        "RESOLVED ", "<script>approved</script>", None, [], 42):
            with self.subTest(status=invalid), patch.object(
                    acme_run_detail, "_read_core_run",
                    return_value=run(status=invalid)):
                response = self.get()
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["reason"], "TENANT_ACL_NOT_QUALIFIED")
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertEqual(response.headers["x-frame-options"], "DENY")
        for status in sorted(acme_run_detail.STATUSES):
            with self.subTest(accepted=status), patch.object(
                    acme_run_detail, "_read_core_run",
                    return_value=run(status=status)):
                response = self.get()
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["reason"], "TENANT_ACL_NOT_QUALIFIED")
            self.assertNotIn("run_status", response.json())
            self.assertFalse(response.json()["runtime_attested"])

    def test_unqualified_collections_and_tenant_claims_rejected(self):
        for change in ({"events": [{"run_id": "RUN-FOREIGN"}]},
                       {"gates": "malformed"},
                       {"stages": []},
                       {"evidence_refs": [{"run_id": "RUN-FOREIGN"}]},
                       {"demo_artifacts": []},
                       {"metadata": {"ownerTenantId": "PRIVATE-TENANT"}}):
            with self.subTest(change=change), patch.object(
                    acme_run_detail, "_read_core_run", return_value=run(**change)):
                response = self.get()
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["state"], "UNKNOWN")
            self.assertNotIn("PRIVATE-TENANT", response.text)
            self.assertNotIn("RUN-FOREIGN", response.text)

    def test_unrecognized_core_fields_fail_closed_instead_of_becoming_authority(self):
        # The actual Core NOC bearer contract has only four identity keys.
        # Newly added claims must be explicitly qualified before Portal can read them.
        for claim in (
            {"approval_status": "APPROVED"},
            {"policy_decision": "ALLOW"},
            {"scenario_id": "SCN-UNVERIFIED"},
            {"run_context": {"run_id": "RUN-FOREIGN", "ticket": "GLPI-FAKE"}},
        ):
            with self.subTest(claim=claim), patch.object(
                    acme_run_detail, "_read_core_run", return_value=run(**claim)):
                response = self.get()
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["reason"], "TENANT_ACL_NOT_QUALIFIED")
            self.assertNotIn("APPROVED", response.text)
            self.assertNotIn("GLPI-FAKE", response.text)

    def test_unqualified_authority_claims_never_become_synthetic_proof(self):
        # The four-field Core NOC identity read cannot authenticate extra
        # source, tenant, ticket, impact or runtime claims.
        for claim in (
            {"synthetic": False},
            {"runtime_authenticated": True},
            {"tenant_acl_qualified": True},
            {"live_remediation_authorized": True},
            {"source_freshness": "FRESH"},
            {"ticket_id": "GLPI-UNVERIFIED"},
            {"evidence_id": "EVD-UNVERIFIED"},
            {"payments_impact": "CONFIRMED"},
        ):
            with self.subTest(claim=claim), patch.object(
                    acme_run_detail, "_read_core_run", return_value=run(**claim)):
                response = self.get()
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["state"], "UNKNOWN")
            for value in claim.values():
                if isinstance(value, str):
                    self.assertNotIn(value, response.text)

    def test_core_exception_is_redacted_unknown(self):
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=ValueError("secret-in-upstream")):
            response = self.get()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["state"], "UNKNOWN")
        self.assertNotIn("secret-in-upstream", response.text)

    def test_core_timeout_is_unknown_without_tenant_acl(self):
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=TimeoutError("sensitive host")):
            response = self.get()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["state"], "UNKNOWN")
        self.assertNotIn("sensitive host", response.text)

    def test_tenant_unqualified_run_presence_absence_and_foreign_are_indistinguishable(self):
        # Identical API and HTML for a valid internal read, foreign/malformed
        # identity, absent Run and transport timeout. No Core-derived existence
        # oracle is allowed until actor+tenant exact-Run authorization exists.
        scenarios = (
            ("present", run()),
            ("foreign", run(incident_id="INC-PRIVATE-FOREIGN")),
            ("malformed", {"run_id": RID, "incident_id": "INC-PRIVATE-FOREIGN"}),
            ("missing", urllib.error.HTTPError("http://core", 404, "not found", {}, None)),
            ("timeout", TimeoutError("private upstream")),
        )
        api_bodies, page_bodies = [], []
        for label, outcome in scenarios:
            with self.subTest(label=label):
                kwargs = ({"side_effect": outcome} if isinstance(outcome, Exception)
                          else {"return_value": outcome})
                with patch.object(acme_run_detail, "_read_core_run", **kwargs):
                    api = self.get()
                    page = self.get("/runs/" + RID)
                self.assertEqual(api.status_code, 503)
                self.assertEqual(page.status_code, 503)
                self.assertEqual(api.json()["reason"], "TENANT_ACL_NOT_QUALIFIED")
                self.assertEqual(api.json()["connection_state"], "UNKNOWN")
                self.assertEqual(api.json()["source"], "UNKNOWN")
                for response in (api, page):
                    self.assertEqual(response.headers["cache-control"], "no-store")
                    self.assertNotIn("INC-PRIVATE-FOREIGN", response.text)
                    self.assertNotIn("private upstream", response.text)
                api_bodies.append(api.json())
                page_bodies.append(page.text)
        self.assertTrue(all(body == api_bodies[0] for body in api_bodies))
        self.assertTrue(all(body == page_bodies[0] for body in page_bodies))

    def test_acme_story_marker_remains_synthetic_on_all_run_read_states(self):
        # The fixed ACME story label is not an assertion about the requested
        # Run; even a 401/403/503 page must not look like a real Payments impact.
        with patch.object(acme_run_detail, "_read_core_run", return_value=run()):
            verified = self.get("/runs/" + RID)
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=urllib.error.HTTPError(
                              "http://core", 403, "denied", {}, None)):
            denied = self.get("/runs/" + RID)
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=TimeoutError("upstream")):
            unavailable = self.get("/runs/" + RID)
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=AssertionError("anonymous Core read")) as core:
            anonymous = self.get("/runs/" + RID, authorized=False)
        core.assert_not_called()
        for page, expected in ((verified, 503), (denied, 503),
                               (unavailable, 503), (anonymous, 401)):
            with self.subTest(status=expected):
                self.assertEqual(page.status_code, expected)
                self.assertIn('data-story-provenance="SYNTHETIC"', page.text)
                self.assertIn("ACME P1 SAN→Payments", page.text)
                self.assertIn("not linked to this Run or runtime-attested", page.text)
                self.assertEqual(page.headers["cache-control"], "no-store")
        self.assertIn("provenance: UNKNOWN", anonymous.text)

    def test_html_page_is_same_portal_route_and_fail_closed_without_auth(self):
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=AssertionError("no anonymous read")):
            response = self.get("/runs/" + RID, authorized=False)
        self.assertEqual(response.status_code, 401)
        self.assertIn("Requested Run — NOT VERIFIED", response.text)
        self.assertIn("UNKNOWN", response.text)
        self.assertIn('href="/"', response.text)
        self.assertIn('href="#evidence"', response.text)
        self.assertIn('href="#ai-ledger"', response.text)
        self.assertIn('href="#verification"', response.text)
        self.assertIn('href="#glpi"', response.text)
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_authenticated_html_is_escaped_and_still_unknown_for_evidence(self):
        with patch.object(acme_run_detail, "_read_core_run", return_value=run()):
            response = self.get("/runs/" + RID)
        self.assertEqual(response.status_code, 503)
        self.assertIn("Requested Run — NOT VERIFIED", response.text)
        self.assertIn("SYNTHETIC", response.text)
        self.assertIn("CORE_BEARER_EVIDENCE_REFS_ENDPOINT_MISSING", response.text)
        self.assertIn("TENANT_ACL_NOT_QUALIFIED", response.text)
        self.assertIn("source freshness: UNKNOWN", response.text)
        self.assertNotIn("<script", response.text)

    def test_html_preserves_auth_denials_but_hides_unqualified_connection_state(self):
        with patch.object(acme_run_detail, "_read_core_run", return_value=run()):
            connected = self.get("/runs/" + RID)
        self.assertEqual(connected.status_code, 503)
        self.assertIn("connection: UNKNOWN", connected.text)
        self.assertIn("source freshness: UNKNOWN", connected.text)
        self.assertIn("CORE_BEARER_EVIDENCE_REFS_ENDPOINT_MISSING", connected.text)
        with patch.object(
                acme_run_detail, "_read_core_run",
                side_effect=urllib.error.HTTPError("http://core", 403, "denied", {}, None)):
            denied = self.get("/runs/" + RID)
        self.assertEqual(denied.status_code, 503)
        self.assertIn("connection: UNKNOWN", denied.text)
        self.assertIn("NOT VERIFIED", denied.text)
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=TimeoutError("sensitive-upstream")):
            unavailable = self.get("/runs/" + RID)
        self.assertEqual(unavailable.status_code, 503)
        self.assertIn("connection: UNKNOWN", unavailable.text)
        self.assertNotIn("sensitive-upstream", unavailable.text)

    def test_home_entry_and_js_asset_do_not_ship_secrets(self):
        home = self.client.get("/")
        self.assertIn('id="run-detail-id"', home.text)
        self.assertIn('id="run-detail-open"', home.text)
        self.assertIn('/assets/portal-run-link.js', home.text)
        js = self.client.get("/assets/portal-run-link.js")
        self.assertEqual(js.status_code, 200)
        self.assertIn("javascript", js.headers["content-type"])
        for forbidden in ("localStorage", "sessionStorage", "document.cookie", "token="):
            self.assertNotIn(forbidden, js.text)
        self.assertIn("Authorization: 'Bearer ' + token", js.text)
        self.assertIn("credentials: 'omit'", js.text)
        self.assertIn("HTTP 2xx (including legacy session success) grants no navigation", js.text)
        self.assertIn("portal-read-token", js.text)

    def test_authenticated_unqualified_session_never_issues_cookie_or_reads_core(self):
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=AssertionError("no Core read")) as core:
            # The positive same-origin shape is HTTPS at the ASGI boundary;
            # an HTTP request with a forged HTTPS Origin is separately denied.
            with TestClient(main.app, base_url="https://testserver") as tls_client:
                response = tls_client.post(
                    "/api/portal/run-session",
                    headers={"Authorization": "Bearer " + TOKEN, "Origin": "https://testserver",
                             "X-Portal-Run-ID": RID, "X-Tenant-ID": "foreign",
                             "X-Actor-ID": "forged"},
                )
            page = self.client.get("/runs/" + RID)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["state"], "UNKNOWN")
        self.assertEqual(response.json()["reason"], "TENANT_ACL_NOT_QUALIFIED")
        self.assertFalse(response.json()["tenant_acl_qualified"])
        self.assertNotIn("set-cookie", response.headers)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])
        self.assertEqual(page.status_code, 401)
        self.assertIn("Requested Run — NOT VERIFIED", page.text)
        core.assert_not_called()

    def test_session_exchange_rejects_missing_token_and_cross_origin(self):
        missing = self.client.post("/api/portal/run-session")
        self.assertEqual(missing.status_code, 401)
        self.assertNotIn("set-cookie", missing.headers)
        cross = self.client.post(
            "/api/portal/run-session",
            headers={"Authorization": "Bearer " + TOKEN, "Origin": "https://evil.example"},
        )
        self.assertEqual(cross.status_code, 403)
        self.assertNotIn("set-cookie", cross.headers)

    def test_session_exchange_failure_responses_keep_security_headers(self):
        # Failed credential exchanges must never be cached or framed either.
        cases = (
            ("missing", {}, 401),
            ("wrong", {"Authorization": "Bearer invalid", "X-Portal-Run-ID": RID}, 401),
            ("cross_origin", {"Authorization": "Bearer " + TOKEN,
                              "Origin": "https://untrusted.example", "X-Portal-Run-ID": RID}, 403),
            ("invalid_run", {"Authorization": "Bearer " + TOKEN,
                             "X-Portal-Run-ID": "RUN-../foreign"}, 422),
            ("valid_but_unqualified", {"Authorization": "Bearer " + TOKEN,
                                       "X-Portal-Run-ID": RID}, 503),
        )
        for label, headers, expected in cases:
            with self.subTest(label=label):
                response = self.client.post("/api/portal/run-session", headers=headers)
                self.assertEqual(response.status_code, expected)
                self.assertEqual(response.headers["cache-control"], "no-store")
                self.assertEqual(response.headers["x-frame-options"], "DENY")
                self.assertEqual(response.headers["x-content-type-options"], "nosniff")
                self.assertIn("frame-ancestors 'none'",
                              response.headers["content-security-policy"])
                self.assertNotIn("set-cookie", response.headers)
                self.assertNotIn(TOKEN, response.text)
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": ""}):
            unconfigured = self.client.post(
                "/api/portal/run-session",
                headers={"Authorization": "Bearer " + TOKEN, "X-Portal-Run-ID": RID},
            )
        self.assertEqual(unconfigured.status_code, 503)
        self.assertEqual(unconfigured.headers["cache-control"], "no-store")
        self.assertEqual(unconfigured.headers["x-frame-options"], "DENY")
        self.assertNotIn("set-cookie", unconfigured.headers)

    def test_expired_or_tampered_session_never_reads_core(self):
        self.client.cookies.set("aiops_portal_run_session", "expired.legacy", path="/runs")
        with patch.object(
            acme_run_detail, "_read_core_run", side_effect=AssertionError("no Core read")
        ) as core:
            response = self.client.get("/runs/" + RID)
        self.assertEqual(response.status_code, 401)
        core.assert_not_called()
        self.client.cookies.set("aiops_portal_run_session", "tampered.payload", path="/runs")
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=AssertionError("no Core read")) as core:
            response = self.client.get("/runs/" + RID)
        self.assertEqual(response.status_code, 401)
        core.assert_not_called()

    def test_json_run_api_remains_bearer_only_even_with_html_session_cookie(self):
        self.client.cookies.set("aiops_portal_run_session", "old.signed-cookie", path="/runs")
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=AssertionError("no Core read")) as core:
            response = self.client.get("/api/portal/runs/" + RID)
        self.assertEqual(response.status_code, 401)
        core.assert_not_called()

    def test_legacy_signed_cookie_is_never_actor_tenant_authority(self):
        # A cookie minted by an older Portal version remains cryptographically
        # valid, but must not authenticate the Run page without an ACL.
        # Legacy cookies are deliberately ignored, regardless of prior signature.
        self.client.cookies.set("aiops_portal_run_session", "old.signed-cookie", path="/runs")
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=AssertionError("no Core read")) as core:
            page = self.client.get("/runs/" + RID)
            exchange = self.client.post(
                "/api/portal/run-session",
                headers={"Authorization": "Bearer " + TOKEN,
                         "X-Portal-Run-ID": RID},
            )
        self.assertEqual(page.status_code, 401)
        self.assertEqual(exchange.status_code, 503)
        self.assertNotIn("set-cookie", exchange.headers)
        self.assertEqual(exchange.json()["reason"], "TENANT_ACL_NOT_QUALIFIED")
        core.assert_not_called()

    def test_session_exchange_requires_valid_run_scope_before_cookie(self):
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=AssertionError("no Core read")) as core:
            for rid in (None, "RUN-../foreign", "INC-123"):
                headers = {"Authorization": "Bearer " + TOKEN}
                if rid is not None:
                    headers["X-Portal-Run-ID"] = rid
                response = self.client.post("/api/portal/run-session", headers=headers)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["state"], "UNKNOWN")
                self.assertNotIn("set-cookie", response.headers)
            core.assert_not_called()

    def test_cookie_cannot_open_another_run(self):
        self.client.cookies.set("aiops_portal_run_session", "old.signed-cookie", path="/runs")
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=AssertionError("foreign Core read")) as core:
            foreign = self.client.get("/runs/RUN-OTHER-123")
        self.assertEqual(foreign.status_code, 401)
        self.assertIn("NOT VERIFIED", foreign.text)
        core.assert_not_called()

    def test_legacy_cookie_cannot_authenticate_after_token_rotation(self):
        self.client.cookies.set("aiops_portal_run_session", "old.signed-cookie", path="/runs")
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": "rotated-ci-only-viewer-token"}):
            with patch.object(acme_run_detail, "_read_core_run",
                              side_effect=AssertionError("no Core read")) as core:
                response = self.client.get("/runs/" + RID)
            self.assertEqual(response.status_code, 401)
            core.assert_not_called()

    def test_existing_home_cockpit_is_no_store_and_anti_framing(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["pragma"], "no-cache")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["referrer-policy"], "no-referrer")
        policy = response.headers["content-security-policy"]
        for directive in ("default-src 'none'", "connect-src 'self'",
                          "frame-ancestors 'none'", "base-uri 'none'",
                          "object-src 'none'"):
            self.assertIn(directive, policy)
        # Legacy inline event handlers stay functional; no parallel shell.
        self.assertIn("script-src 'self' 'unsafe-inline'", policy)
        self.assertIn('id="run-detail-open"', response.text)
        self.assertIn('id="portal-runs"', response.text)

    def test_unverified_run_html_stays_no_store_with_security_headers(self):
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=ValueError("unqualified Core payload")):
            response = self.get("/runs/" + RID)
        self.assertEqual(response.status_code, 503)
        self.assertIn("UNKNOWN", response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertIn("frame-ancestors 'none'",
                      response.headers["content-security-policy"])
        self.assertNotIn("unqualified Core payload", response.text)

    def test_bootstrap_shared_bearer_never_reads_unscoped_core_twin(self):
        # A valid shared token is service/viewer authentication, not tenant ACL.
        with patch.object(main, "read_portal_snapshot",
                          side_effect=AssertionError("unscoped read forbidden")) as read:
            response = self.client.get("/api/portal/bootstrap", headers={
                "Authorization": "Bearer " + TOKEN})
        read.assert_not_called()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["state"], "UNKNOWN")
        self.assertEqual(response.json()["reason"], "TENANT_ACL_NOT_QUALIFIED")
        self.assertEqual(response.json()["connection_state"], "UNKNOWN")
        self.assertEqual(response.json()["source_freshness"], "UNKNOWN")
        for key in ("runs", "dashboard", "twin", "incident_id", "run_id"):
            self.assertNotIn(key, response.json())
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")

    def test_bootstrap_auth_refusals_precede_any_unscoped_read(self):
        with patch.object(main, "read_portal_snapshot",
                          side_effect=AssertionError("unscoped read forbidden")) as read:
            for headers in ({}, {"Authorization": "Bearer wrong"}):
                response = self.client.get("/api/portal/bootstrap", headers=headers)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.headers["cache-control"], "no-store")
            with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": ""}):
                response = self.client.get("/api/portal/bootstrap", headers={
                    "Authorization": "Bearer " + TOKEN})
                self.assertEqual(response.status_code, 503)
            read.assert_not_called()

    def test_no_new_write_endpoint(self):
        self.assertEqual(self.client.post("/api/portal/runs/" + RID).status_code, 405)
        self.assertEqual(self.client.post("/runs/" + RID).status_code, 405)


if __name__ == "__main__":
    unittest.main()
