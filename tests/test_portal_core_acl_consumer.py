"""P0 actor+tenant Run ACL consumer: disposable server sessions, zero Core/GLPI I/O."""
import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "internal-" + "i" * 48}):
    from portal import main, oidc_session, acme_run_detail, core_acl_consumer
from portal.oidc_identity import PortalActorContext

RUN = "RUN-ACME-123"
OTHER = "RUN-FOREIGN-999"
HANDLE = "A" * 43
NOW = int(time.time())


class PortalCoreACLConsumerTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "AIOPS_PORTAL_READ_TOKEN": "viewer-" + "v" * 40,
            "AIOPS_PORTAL_CORE_XREF_ORIGIN": "https://core.example.test:8443",
            "AIOPS_PORTAL_CORE_XREF_SERVICE_TOKEN": "xref-" + "s" * 40,
            "AIOPS_PORTAL_CORE_XREF_SCOPE": "itsm:xref:read",
        })
        self.env.start()
        self.client = TestClient(main.app, base_url="https://portal.example.test")
        with oidc_session._lock:
            oidc_session._sessions.clear()
            oidc_session._pending.clear()

    def tearDown(self):
        self.client.close()
        self.env.stop()
        with oidc_session._lock:
            oidc_session._sessions.clear()
            oidc_session._pending.clear()

    def actor(self, tenant="ACME", expiry=600):
        return PortalActorContext(
            "operator-123", tenant, ("N2",),
            "https://idp.example.test/realms/acme", "aiops2-portal",
            expires_at=int(time.time()) + expiry)

    def session(self, tenant="ACME", ttl=600, actor_expiry=600):
        with oidc_session._lock:
            oidc_session._sessions[oidc_session._digest(HANDLE)] = oidc_session._Session(
                self.actor(tenant, actor_expiry), int(time.time()) + ttl)
        self.client.cookies.set(oidc_session._SESSION_COOKIE, HANDLE,
                                domain="portal.example.test", path="/")

    def assert_fence(self, response, status=503):
        self.assertEqual(response.status_code, status)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertIn("frame-ancestors 'none'",
                      response.headers["content-security-policy"])
        self.assertNotIn("CONNECTED", response.text)
        self.assertNotIn("operator-123", response.text)

    def test_valid_identity_still_unknown_for_present_foreign_absent_forged(self):
        self.session()
        responses = []
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=AssertionError("Core forbidden")) as core, \
             patch.object(main, "get_json",
                          side_effect=AssertionError("upstream forbidden")) as upstream:
            for run in (RUN, OTHER, "RUN-NOT-FOUND", "RUN-bad!"):
                for prefix in ("/api/portal/runs/", "/runs/"):
                    with self.subTest(run=run, prefix=prefix):
                        response = self.client.get(prefix + run, headers={
                            "Authorization": "Bearer forged",
                            "X-Actor-ID": "admin", "X-Tenant-ID": "OTHER",
                            "X-GLPI-Profile": "manager"})
                        self.assert_fence(response)
                        if prefix.startswith("/api/"):
                            self.assertEqual(response.json()["reason"],
                                             "TENANT_ACL_NOT_QUALIFIED")
                            responses.append(response.json())
            core.assert_not_called()
            upstream.assert_not_called()
        self.assertTrue(all(item == responses[0] for item in responses))

    def test_foreign_session_identity_never_promotes_acl(self):
        self.session(tenant="OTHER")
        response = self.client.get("/api/portal/runs/" + RUN)
        self.assert_fence(response)
        self.assertEqual(response.json()["tenant_acl_qualified"], False)

    def test_missing_expired_and_revoked_session_refused(self):
        self.assert_fence(self.client.get("/api/portal/runs/" + RUN), 401)
        self.session(ttl=-1)
        self.assert_fence(self.client.get("/api/portal/runs/" + RUN), 401)
        self.session(actor_expiry=-1)
        self.assert_fence(self.client.get("/api/portal/runs/" + RUN), 401)
        self.session()
        self.assert_fence(self.client.get("/api/portal/runs/" + RUN), 503)
        with oidc_session._lock:
            oidc_session._sessions.pop(oidc_session._digest(HANDLE), None)
        # Replaying the original opaque cookie cannot restore a revoked session.
        self.assert_fence(self.client.get("/api/portal/runs/" + RUN), 401)

    def test_legacy_viewer_bearer_never_grants_run(self):
        response = self.client.get("/api/portal/runs/" + RUN, headers={
            "Authorization": "Bearer " + os.environ["AIOPS_PORTAL_READ_TOKEN"]})
        self.assert_fence(response)

    def test_core_origin_scope_and_separate_token_pinned(self):
        good = dict(os.environ)
        target = core_acl_consumer.configured_core_target(good)
        self.assertIsNotNone(target)
        self.assertNotIn("xref-", repr(target))
        for changes in (
            {"AIOPS_PORTAL_CORE_XREF_ORIGIN": "http://core.example.test:8443"},
            {"AIOPS_PORTAL_CORE_XREF_ORIGIN": "https://evil.example.test/xref"},
            {"AIOPS_PORTAL_CORE_XREF_ORIGIN": "https://user:pw@core.example.test"},
            {"AIOPS_PORTAL_CORE_XREF_ORIGIN": "https://core.example.test@evil.test"},
            {"AIOPS_PORTAL_CORE_XREF_ORIGIN": "https://core.example.test:9999"},
            {"AIOPS_PORTAL_CORE_XREF_ORIGIN": "https://core.example.test?redirect=1"},
            {"AIOPS_PORTAL_CORE_XREF_SCOPE": "admin"},
            {"AIOPS_PORTAL_CORE_XREF_SERVICE_TOKEN": good["AIOPS_PORTAL_READ_TOKEN"]},
            {"AIOPS_PORTAL_CORE_XREF_SERVICE_TOKEN": "short"},
        ):
            with self.subTest(changes=changes):
                self.assertIsNone(core_acl_consumer.configured_core_target(
                    {**good, **changes}))

    def binding(self, tenant="ACME"):
        return core_acl_consumer.ServerXref(
            tenant, RUN, "INC-ACME-123", "glpi-acme", "123", "42")

    def test_cross_tenant_and_forged_resource_binding(self):
        actor = self.actor()
        self.assertTrue(core_acl_consumer.exact_binding_valid(actor, self.binding()))
        for binding in (
            self.binding("OTHER"),
            core_acl_consumer.ServerXref("ACME", "RUN-../escape", "INC-ACME-123",
                                         "glpi-acme", "123", "42"),
            core_acl_consumer.ServerXref("ACME", RUN, "INC-ACME-123",
                                         "glpi-acme", "../ticket", "42"),
            core_acl_consumer.ServerXref("ACME", RUN, "INC-ACME-123",
                                         "glpi-acme", "123", "foreign"),
        ):
            with self.subTest(binding=binding):
                self.assertFalse(core_acl_consumer.exact_binding_valid(actor, binding))

    def test_current_core_xref_verified_is_not_actor_acl(self):
        actor, binding = self.actor(), self.binding()
        current_core = {"schema": "aiops.core-itsm-xref-read.v1",
                        "status": "VERIFIED", "tenant_acl_qualified": True,
                        "tenant_id": "ACME", "run_id": RUN,
                        "incident_id": "INC-ACME-123",
                        "ticket_id": "123"}
        self.assertFalse(core_acl_consumer.positive_core_contract_matches(
            current_core, actor, binding))

    def future_envelope(self, now):
        actor, binding = self.actor(), self.binding()
        nonce = "n" * 43
        return actor, binding, nonce, {
            "schema": "aiops.core-actor-resource-authorization.v1",
            "decision": "ALLOW", "permission": "run:read",
            "tenant_acl_qualified": True, "acl_version": "v1",
            "decision_id": "d" * 24, "actor_subject": actor.subject,
            "actor_issuer": actor.issuer, "actor_audience": actor.audience,
            "tenant_id": binding.tenant_id, "run_id": binding.run_id,
            "incident_id": binding.incident_id,
            "glpi_instance_id": binding.glpi_instance_id,
            "ticket_id": binding.ticket_id,
            "glpi_entity_id": binding.glpi_entity_id,
            "request_nonce": nonce, "issued_at": now - 5,
            "expires_at": now + 30, "revocation_checked_at": now - 2,
            "revoked": False,
            "delegation": {
                "kind": "CORE_VERIFIED_OIDC_DELEGATION",
                "subject": actor.subject, "issuer": actor.issuer,
                "audience": actor.audience, "tenant_id": actor.tenant_id,
                "expires_at": now + 60, "revoked": False,
            },
            "glpi_readback": {
                "kind": "INDEPENDENT_AUTHENTICATED_GLPI_READBACK",
                "instance_id": binding.glpi_instance_id,
                "ticket_id": binding.ticket_id,
                "entity_id": binding.glpi_entity_id,
                "permission": "ticket:read", "verified_at": now - 4,
                "expires_at": now + 60, "ownership_confirmed": True,
                "actor_permission_confirmed": True,
                "run_ticket_binding_confirmed": True,
            },
        }

    def test_v1_shape_is_never_positive_authorization(self):
        now = int(time.time())
        actor, binding, nonce, envelope = self.future_envelope(now)
        self.assertTrue(core_acl_consumer.core_v1_envelope_matches(
            envelope, actor, binding, request_nonce=nonce, now=now))
        # Even a perfect synthetic JSON cannot establish transport trust,
        # real subject delegation or independent GLPI authority.
        self.assertFalse(core_acl_consumer.positive_core_contract_matches(
            envelope, actor, binding, now=now))
        self.assertFalse(core_acl_consumer.core_v1_envelope_matches(
            envelope, actor, binding, request_nonce="r" * 43, now=now))

    def test_v1_adversarial_claims_and_stale_proofs_rejected(self):
        now = int(time.time())
        actor, binding, nonce, envelope = self.future_envelope(now)
        variants = [
            {"actor_subject": "forged"}, {"tenant_id": "OTHER"},
            {"run_id": OTHER}, {"incident_id": "INC-FOREIGN"},
            {"ticket_id": "999"}, {"glpi_entity_id": "99"},
            {"actor_issuer": "https://evil.test"},
            {"actor_audience": "other-client"},
            {"permission": "admin"}, {"schema": "aiops.core-itsm-xref-read.v1"},
            {"decision": "DENY"}, {"revoked": True},
            {"tenant_acl_qualified": False}, {"expires_at": now - 1},
            {"expires_at": now + 301}, {"issued_at": now - 61},
            {"issued_at": now + 1}, {"revocation_checked_at": now - 31},
            {"revocation_checked_at": now + 1}, {"acl_version": "v0"},
            {"decision_id": ""}, {"request_nonce": "r" * 43},
            {"extra_authority": "CONNECTED"},
            {"delegation": {**envelope["delegation"], "revoked": True}},
            {"delegation": {**envelope["delegation"], "subject": "forged"}},
            {"delegation": {**envelope["delegation"], "expires_at": now - 1}},
            {"glpi_readback": {**envelope["glpi_readback"],
                               "ownership_confirmed": False}},
            {"glpi_readback": {**envelope["glpi_readback"],
                               "actor_permission_confirmed": False}},
            {"glpi_readback": {**envelope["glpi_readback"],
                               "run_ticket_binding_confirmed": False}},
            {"glpi_readback": {**envelope["glpi_readback"], "entity_id": "99"}},
            {"glpi_readback": {**envelope["glpi_readback"],
                               "verified_at": now - 61}},
            {"glpi_readback": {**envelope["glpi_readback"],
                               "expires_at": now - 1}},
        ]
        for changes in variants:
            with self.subTest(changes=changes):
                self.assertFalse(core_acl_consumer.core_v1_envelope_matches(
                    {**envelope, **changes}, actor, binding,
                    request_nonce=nonce, now=now))
        # JSON booleans must not be accepted as integer timestamps.
        for key in ("issued_at", "expires_at", "revocation_checked_at"):
            with self.subTest(timestamp=key):
                self.assertFalse(core_acl_consumer.core_v1_envelope_matches(
                    {**envelope, key: True}, actor, binding,
                    request_nonce=nonce, now=now))

    def test_distinct_core_authz_service_token_preflight_only(self):
        settings = {**os.environ,
            "AIOPS_PORTAL_CORE_AUTHZ_ORIGIN": "https://core.example.test:8443",
            "AIOPS_PORTAL_CORE_AUTHZ_SERVICE_TOKEN": "authz-" + "a" * 40,
            "AIOPS_PORTAL_CORE_AUTHZ_SCOPE": "actor:resource:authorize",
        }
        target = core_acl_consumer.configured_core_authz_target(settings)
        self.assertIsNotNone(target)
        self.assertNotIn("authz-", repr(target))
        for changes in (
            {"AIOPS_PORTAL_CORE_AUTHZ_SCOPE": "itsm:xref:read"},
            {"AIOPS_PORTAL_CORE_AUTHZ_SERVICE_TOKEN":
             settings["AIOPS_PORTAL_CORE_XREF_SERVICE_TOKEN"]},
            {"AIOPS_PORTAL_CORE_AUTHZ_SERVICE_TOKEN":
             settings["AIOPS_PORTAL_READ_TOKEN"]},
            {"AIOPS_PORTAL_CORE_AUTHZ_ORIGIN": "http://core.example.test"},
            {"AIOPS_PORTAL_CORE_AUTHZ_ORIGIN":
             "https://core.example.test@evil.test"},
        ):
            with self.subTest(changes=changes):
                self.assertIsNone(core_acl_consumer.configured_core_authz_target(
                    {**settings, **changes}))

    def test_session_replay_expiry_revocation_api_html_no_upstream(self):
        self.session()
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=AssertionError("no Core read")) as core, \
             patch("urllib.request.urlopen",
                   side_effect=AssertionError("no network")) as upstream:
            for route in ("/api/portal/runs/", "/runs/"):
                self.assert_fence(self.client.get(route + RUN), 503)
            with oidc_session._lock:
                oidc_session._sessions.pop(oidc_session._digest(HANDLE), None)
            for route in ("/api/portal/runs/", "/runs/"):
                self.assert_fence(self.client.get(route + RUN), 401)
            self.session(ttl=-1)
            for route in ("/api/portal/runs/", "/runs/"):
                self.assert_fence(self.client.get(route + RUN), 401)
            self.session(actor_expiry=-1)
            for route in ("/api/portal/runs/", "/runs/"):
                self.assert_fence(self.client.get(route + RUN), 401)
            core.assert_not_called()
            upstream.assert_not_called()

    def test_even_future_envelope_does_not_enable_network(self):
        self.session()
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("network forbidden")) as upstream:
            response = self.client.get("/api/portal/runs/" + RUN)
        self.assert_fence(response)
        upstream.assert_not_called()


if __name__ == "__main__":
    unittest.main()
