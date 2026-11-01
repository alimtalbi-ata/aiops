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


    def authz_settings(self):
        return {**os.environ,
            "AIOPS_PORTAL_CORE_AUTHZ_ORIGIN": "https://core.example.test:8443",
            "AIOPS_PORTAL_CORE_AUTHZ_SERVICE_TOKEN": "authz-" + "a" * 40,
            "AIOPS_PORTAL_CORE_AUTHZ_SCOPE": "actor:resource:authorize",
        }

    def test_authz_wire_preflight_is_server_only_and_dispatch_disabled(self):
        from portal import core_authz_transport as wire
        actor, binding = self.actor(), self.binding()
        settings = self.authz_settings()
        with patch("urllib.request.urlopen", side_effect=AssertionError("network")) as net:
            plan = wire.prepare_core_authz_wire(actor, binding, env=settings)
        self.assertIsNotNone(plan)
        self.assertFalse(plan.dispatch_allowed)
        self.assertEqual(plan.method, "POST")
        self.assertEqual(plan.origin, "https://core.example.test:8443")
        self.assertEqual(plan.path, "/api/tenants/ACME/runs/" + RUN
                         + "/actor-resource-authorization")
        self.assertEqual(plan.headers["Authorization"],
                         "Bearer " + settings["AIOPS_PORTAL_CORE_AUTHZ_SERVICE_TOKEN"])
        self.assertNotIn(settings["AIOPS_PORTAL_CORE_AUTHZ_SERVICE_TOKEN"], repr(plan))
        self.assertNotIn("operator-123", plan.body.decode())
        self.assertNotIn("X-Actor", str(plan.headers))
        self.assertNotIn("X-Tenant", str(plan.headers))
        self.assertNotIn("delegation", plan.body.decode())
        self.assertEqual(__import__("json").loads(plan.body)["permission"], "run:read")
        net.assert_not_called()

    def test_authz_wire_rejects_foreign_expired_and_forged_bindings(self):
        from portal import core_authz_transport as wire
        settings = self.authz_settings()
        for actor, binding in (
            (self.actor("ACME"), self.binding("OTHER")),
            (self.actor(expiry=-1), self.binding()),
            (self.actor(), core_acl_consumer.ServerXref(
                "ACME", "RUN-../evil", "INC-ACME-123", "glpi-acme", "123", "42")),
            (self.actor(), core_acl_consumer.ServerXref(
                "ACME", RUN, "INC-ACME-123", "glpi-acme", "123", "foreign")),
        ):
            with self.subTest(actor=actor, binding=binding):
                self.assertIsNone(wire.prepare_core_authz_wire(
                    actor, binding, env=settings))

    def test_authz_wire_rejects_unpinned_origin_and_shared_service_token(self):
        from portal import core_authz_transport as wire
        settings = self.authz_settings()
        for changes in (
            {"AIOPS_PORTAL_CORE_AUTHZ_ORIGIN": "http://core.example.test"},
            {"AIOPS_PORTAL_CORE_AUTHZ_ORIGIN": "https://core.example.test@evil.test"},
            {"AIOPS_PORTAL_CORE_AUTHZ_ORIGIN": "https://core.example.test/path"},
            {"AIOPS_PORTAL_CORE_AUTHZ_SCOPE": "itsm:xref:read"},
            {"AIOPS_PORTAL_CORE_AUTHZ_SERVICE_TOKEN":
                settings["AIOPS_PORTAL_CORE_XREF_SERVICE_TOKEN"]},
            {"AIOPS_PORTAL_CORE_AUTHZ_SERVICE_TOKEN":
                settings["AIOPS_PORTAL_READ_TOKEN"]},
        ):
            with self.subTest(changes=changes):
                self.assertIsNone(wire.prepare_core_authz_wire(
                    self.actor(), self.binding(), env={**settings, **changes}))

    def test_signed_synthetic_allow_is_authenticated_but_never_authorized(self):
        from portal import core_authz_transport as wire
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
        import base64
        now = int(time.time())
        actor, binding, _, payload = self.future_envelope(now)
        settings = self.authz_settings()
        plan = wire.prepare_core_authz_wire(actor, binding, env=settings, now=now)
        self.assertIsNotNone(plan)
        payload["request_nonce"] = plan.nonce
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        numbers = private.public_key().public_numbers()
        def b64(value):
            return base64.urlsafe_b64encode(
                value.to_bytes((value.bit_length() + 7) // 8, "big")
            ).rstrip(b"=").decode("ascii")
        settings["AIOPS_PORTAL_CORE_AUTHZ_RESPONSE_JWKS_JSON"] = __import__("json").dumps({
            "keys": [{"kid": "core-test-key", "kty": "RSA", "alg": "RS256",
                      "use": "sig", "n": b64(numbers.n), "e": b64(numbers.e)}]
        })
        def sign(body, origin=None):
            signed = wire._canonical_signed_bytes(origin or plan.origin, body)
            return {"alg": "RS256", "kid": "core-test-key",
                    "signature": base64.urlsafe_b64encode(private.sign(
                        signed, padding.PKCS1v15(), hashes.SHA256())
                    ).rstrip(b"=").decode("ascii")}
        signature = sign(payload)
        check = lambda p, s, target=plan: wire.verify_pinned_core_response_signature(
            p, s, actor=actor, binding=binding, plan=target,
            env=settings, now=now)
        self.assertTrue(check(payload, signature))
        self.assertFalse(wire.core_authz_read_permitted(payload, signature))
        self.assertFalse(core_acl_consumer.positive_core_contract_matches(
            payload, actor, binding, now=now))
        # A forged ALLOW without a valid signature is not even authenticated.
        self.assertFalse(check({**payload, "tenant_id": "OTHER"}, signature))
        self.assertFalse(check({**payload, "run_id": OTHER}, signature))
        self.assertFalse(check({**payload, "ticket_id": "999"}, signature))
        self.assertFalse(check(payload, {**signature, "alg": "none"}))
        self.assertFalse(check(payload, {**signature, "signature": "x" * 40}))
        self.assertFalse(check(payload, sign(payload, "https://evil.test")))
        self.assertFalse(check(payload, {**signature, "kid": "attacker"}))
        # A new challenge cannot accept a previous signed response.
        next_plan = wire.prepare_core_authz_wire(actor, binding, env=settings, now=now)
        self.assertNotEqual(plan.nonce, next_plan.nonce)
        self.assertFalse(check(payload, signature, next_plan))
        # A forged pin or a missing pin is not response authenticity.
        self.assertFalse(wire.verify_pinned_core_response_signature(
            payload, signature, actor=actor, binding=binding, plan=plan,
            env={**settings, "AIOPS_PORTAL_CORE_AUTHZ_RESPONSE_JWKS_JSON":
                 '{"keys":[]}'}, now=now))
        self.assertFalse(wire.verify_pinned_core_response_signature(
            payload, signature, actor=actor, binding=binding, plan=plan,
            env={**settings, "AIOPS_PORTAL_CORE_AUTHZ_ORIGIN":
                 "https://other.example.test"}, now=now))

    def test_authz_transport_is_not_wired_to_browser_or_api(self):
        from portal import core_authz_transport as wire
        self.session()
        settings = self.authz_settings()
        with patch.dict(os.environ, settings), patch.object(
                wire, "prepare_core_authz_wire",
                side_effect=AssertionError("premature Core authz request")) as prepare, \
             patch.object(acme_run_detail, "_read_core_run",
                          side_effect=AssertionError("Core business read")) as core, \
             patch.object(main, "get_json",
                          side_effect=AssertionError("Core/GLPI fetch")) as upstream:
            for rid in (RUN, OTHER, "RUN-ABSENT", "RUN-forged!"):
                for prefix in ("/api/portal/runs/", "/runs/"):
                    response = self.client.get(prefix + rid, headers={
                        "Authorization": "Bearer forged-allow",
                        "X-Actor-ID": "admin", "X-Tenant-ID": "OTHER",
                        "X-GLPI-Profile": "manager"})
                    self.assert_fence(response, 503)
                    self.assertNotIn("INC-ACME", response.text)
                    self.assertNotIn("glpi-acme", response.text)
            prepare.assert_not_called()
            core.assert_not_called()
            upstream.assert_not_called()
        with oidc_session._lock:
            oidc_session._sessions.pop(oidc_session._digest(HANDLE), None)
        for prefix in ("/api/portal/runs/", "/runs/"):
            self.assert_fence(self.client.get(prefix + RUN), 401)


    def test_current_core_route_and_negative_wire_are_exactly_reconciled(self):
        """Exercise the actual Core router with only disposable mocks; no HTTP upstream."""
        import json
        from fastapi import FastAPI
        # Core xref registers the actor router; import xref first to avoid
        # the existing Core module-level circular import during isolated tests.
        from core import itsm_xref as core_xref
        from core import actor_resource_authz as core_actor
        from portal import core_authz_transport as wire

        actor, binding = self.actor(), self.binding()
        plan = wire.prepare_core_authz_wire(
            actor, binding, env=self.authz_settings())
        self.assertIsNotNone(plan)
        self.assertFalse(plan.dispatch_allowed)
        self.assertNotIn("X-Actor-Delegation", plan.headers)
        self.assertNotIn("actor_subject", plan.body.decode())
        self.assertNotIn("actor_issuer", plan.body.decode())
        self.assertNotIn("actor_audience", plan.body.decode())
        self.assertEqual(plan.path,
                         "/api/tenants/ACME/runs/" + RUN +
                         "/actor-resource-authorization")
        self.assertEqual(core_actor.SCHEMA,
                         "aiops.core-actor-resource-authorization.v1")

        app = FastAPI()
        app.include_router(core_xref.router)
        with TestClient(app) as client, \
             patch.object(core_xref, "_auth", return_value=(
                 {"permissions": ["actor:resource:authorize"],
                  "tenant_ids": ["ACME"]}, 200)), \
             patch.object(core_actor, "_actor_introspection",
                          return_value=None) as introspect, \
             patch.object(core_xref, "db",
                          side_effect=AssertionError("no Core DB")) as database:
            response = client.post(plan.path, json=json.loads(plan.body),
                                   headers=plan.headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {
                "schema": core_actor.SCHEMA, "decision": "UNKNOWN"})
            self.assertTrue(wire.core_v1_current_unknown_reply_matches(
                response.status_code, response.json(), response.headers))
            self.assertFalse(wire.core_authz_read_permitted(response.json()))
            self.assertFalse(core_acl_consumer.positive_core_contract_matches(
                response.json(), actor, binding))
            self.assertEqual(introspect.call_count, 1)
            self.assertIsNone(introspect.call_args.args[0])
            expected = introspect.call_args.args[1]
            self.assertEqual(expected, {
                "tenant_id": binding.tenant_id, "run_id": binding.run_id,
                "incident_id": binding.incident_id,
                "glpi_instance_id": binding.glpi_instance_id,
                "ticket_id": binding.ticket_id,
                "glpi_entity_id": binding.glpi_entity_id,
                "permission": "run:read", "nonce": plan.nonce})
            database.assert_not_called()

    def test_current_core_401_403_and_invalid_resource_no_upstream(self):
        """No delegated IdP token, foreign tenant or forged body may grant a read."""
        import json
        from fastapi import FastAPI
        # Core xref registers the actor router; import xref first to avoid
        # the existing Core module-level circular import during isolated tests.
        from core import itsm_xref as core_xref
        from core import actor_resource_authz as core_actor
        from portal import core_authz_transport as wire

        plan = wire.prepare_core_authz_wire(
            self.actor(), self.binding(), env=self.authz_settings())
        app = FastAPI()
        app.include_router(core_xref.router)
        with TestClient(app) as client, \
             patch.object(core_actor, "_actor_introspection") as introspect, \
             patch.object(core_xref, "db",
                          side_effect=AssertionError("no Core DB")) as database:
            for auth, path, status in (
                ((None, 401), plan.path, 401),
                (({"permissions": [], "tenant_ids": ["ACME"]}, 200),
                 plan.path, 403),
                (({"permissions": ["actor:resource:authorize"],
                   "tenant_ids": ["ACME"]}, 200),
                 plan.path.replace("/ACME/", "/OTHER/"), 403),
            ):
                with self.subTest(status=status, path=path), \
                     patch.object(core_xref, "_auth", return_value=auth):
                    response = client.post(path, json=json.loads(plan.body),
                                           headers=plan.headers)
                    self.assertEqual(response.status_code, status)
                    self.assertTrue(wire.core_v1_current_unknown_reply_matches(
                        status, response.json(), response.headers))
                    self.assertFalse(wire.core_authz_read_permitted(response.json()))
            with patch.object(core_xref, "_auth", return_value=(
                {"permissions": ["actor:resource:authorize"],
                 "tenant_ids": ["ACME"]}, 200)):
                for changes in (
                    {"nonce": "replayed-invalid"}, {"ticket_id": "999;drop"},
                    {"incident_id": "INC-../foreign"},
                    {"glpi_entity_id": "OTHER"},
                    {"permission": "ticket:write"},
                ):
                    with self.subTest(changes=changes):
                        body = {**json.loads(plan.body), **changes}
                        response = client.post(plan.path, json=body,
                                               headers=plan.headers)
                        self.assertEqual(response.status_code, 200)
                        self.assertTrue(wire.core_v1_current_unknown_reply_matches(
                            200, response.json(), response.headers))
            introspect.assert_not_called()
            database.assert_not_called()

    def test_current_core_reply_rejects_forged_allow_replay_and_leaks(self):
        from portal import core_authz_transport as wire
        good_headers = {"Cache-Control": "no-store", "Pragma": "no-cache",
                        "X-Content-Type-Options": "nosniff",
                        "Referrer-Policy": "no-referrer"}
        unknown = {"schema": "aiops.core-actor-resource-authorization.v1",
                   "decision": "UNKNOWN"}
        self.assertTrue(wire.core_v1_current_unknown_reply_matches(
            200, unknown, good_headers))
        for code, body, headers in (
            (200, {**unknown, "decision": "ALLOW"}, good_headers),
            (200, {**unknown, "tenant_id": "ACME"}, good_headers),
            (200, {**unknown, "actor_subject": "admin"}, good_headers),
            (200, {**unknown, "request_nonce": "replayed"}, good_headers),
            (200, {**unknown, "glpi_readback": {"verified": True}}, good_headers),
            (200, {**unknown, "decision": "CONNECTED"}, good_headers),
            (503, {**unknown, "decision": "ALLOW"}, good_headers),
            (200, unknown, {**good_headers, "Cache-Control": "public"}),
            (200, unknown, {**good_headers, "Referrer-Policy": "unsafe-url"}),
            (401, unknown, good_headers),
            (200, unknown, {}),
        ):
            with self.subTest(code=code, body=body):
                self.assertFalse(wire.core_v1_current_unknown_reply_matches(
                    code, body, headers))
        self.session()
        with patch.object(acme_run_detail, "_read_core_run",
                          side_effect=AssertionError("Core read forbidden")) as core, \
             patch.object(main, "get_json",
                          side_effect=AssertionError("upstream forbidden")) as upstream:
            for rid in (RUN, OTHER, "RUN-NOT-FOUND", "RUN-forged!"):
                for prefix in ("/api/portal/runs/", "/runs/"):
                    response = self.client.get(prefix + rid, headers={
                        "X-Tenant-ID": "OTHER", "X-Actor-ID": "admin",
                        "Authorization": "Bearer forged-allow"})
                    self.assert_fence(response, 503)
                    self.assertNotIn("INC-ACME", response.text)
            core.assert_not_called()
            upstream.assert_not_called()
        with oidc_session._lock:
            oidc_session._sessions.pop(oidc_session._digest(HANDLE), None)
        self.assert_fence(self.client.get("/api/portal/runs/" + RUN), 401)
        self.session(ttl=-1)
        self.assert_fence(self.client.get("/runs/" + RUN), 401)


    def test_offline_core_v1_signed_shape_and_real_denial_parity(self):
        """Disposable RSA signs proposed ALLOW; neither it nor 200 UNKNOWN grants."""
        import base64
        import json
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
        from portal import core_authz_transport as wire

        now = int(time.time())
        actor, binding, _, payload = self.future_envelope(now)
        settings = self.authz_settings()
        plan = wire.prepare_core_authz_wire(actor, binding, env=settings, now=now)
        self.assertIsNotNone(plan)
        self.assertFalse(plan.dispatch_allowed)
        payload["request_nonce"] = plan.nonce
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        numbers = private.public_key().public_numbers()

        def b64(number):
            return base64.urlsafe_b64encode(number.to_bytes(
                (number.bit_length() + 7) // 8, "big")).rstrip(b"=").decode()

        settings["AIOPS_PORTAL_CORE_AUTHZ_RESPONSE_JWKS_JSON"] = json.dumps({
            "keys": [{"kid": "core-fixture", "kty": "RSA", "alg": "RS256",
                      "use": "sig", "n": b64(numbers.n), "e": b64(numbers.e)}]
        })
        def sign(body):
            signed = wire._canonical_signed_bytes(plan.origin, body)
            return {"alg": "RS256", "kid": "core-fixture",
                    "signature": base64.urlsafe_b64encode(private.sign(
                        signed, padding.PKCS1v15(), hashes.SHA256()
                    )).rstrip(b"=").decode()}

        headers = {"Cache-Control": "no-store", "Pragma": "no-cache",
                   "X-Content-Type-Options": "nosniff",
                   "Referrer-Policy": "no-referrer"}
        def assess(code, body, sig=None, *, target=plan, who=actor, resource=binding,
                   response_headers=headers):
            return wire.assess_core_authz_reply_offline(
                code, body, response_headers, sig, actor=who, binding=resource,
                plan=target, env=settings, now=now)

        schema = "aiops.core-actor-resource-authorization.v1"
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("no upstream")) as network:
            for code, decision in ((200, "UNKNOWN"), (401, "UNKNOWN"),
                                   (403, "UNAUTHORIZED"), (503, "UNKNOWN")):
                with self.subTest(core_status=code):
                    h = {**headers, **({"WWW-Authenticate": "Bearer"}
                                      if code == 401 else {})}
                    result = assess(code, {"schema": schema, "decision": decision},
                                    response_headers=h)
                    self.assertEqual(result.kind, "CURRENT_CORE_NEGATIVE")
                    self.assertEqual((result.portal_status, result.state,
                                      result.read_permitted), (503, "UNKNOWN", False))
            signature = sign(payload)
            valid = assess(200, payload, signature)
            self.assertEqual(valid.kind, "SIGNED_SHAPE_UNQUALIFIED")
            self.assertEqual((valid.portal_status, valid.state,
                              valid.read_permitted), (503, "UNKNOWN", False))
            self.assertFalse(wire.core_authz_read_permitted(payload, signature))
            # An unsigned or altered ALLOW, even on HTTP 200, is invalid.
            for changes in (
                {"tenant_id": "OTHER"}, {"actor_subject": "admin"},
                {"actor_issuer": "https://forged.example.test"},
                {"actor_audience": "core-other"},
                {"run_id": OTHER}, {"incident_id": "INC-FOREIGN"},
                {"ticket_id": "999"}, {"glpi_entity_id": "99"},
                {"revoked": True}, {"expires_at": now - 1},
                {"request_nonce": "r" * 43},
                {"delegation": {**payload["delegation"], "revoked": True}},
                {"glpi_readback": {**payload["glpi_readback"],
                                   "actor_permission_confirmed": False}},
            ):
                with self.subTest(forgery=changes):
                    forged = {**payload, **changes}
                    self.assertEqual(assess(200, forged, sign(forged)).kind,
                                     "INVALID")
            self.assertEqual(assess(200, payload).kind, "INVALID")
            self.assertEqual(assess(503, payload, signature).kind, "INVALID")
            self.assertEqual(assess(200, payload, {**signature,
                                                  "signature": "x" * 40}).kind,
                             "INVALID")
            # A replayed response cannot satisfy a *new* nonce challenge.
            fresh = wire.prepare_core_authz_wire(
                actor, binding, env=settings, now=now)
            self.assertNotEqual(plan.nonce, fresh.nonce)
            self.assertEqual(assess(200, payload, signature, target=fresh).kind,
                             "INVALID")
            for altered_headers in (
                {**headers, "Cache-Control": "public"},
                {**headers, "Set-Cookie": "sid=forged"},
                {**headers, "Access-Control-Allow-Origin": "*"},
                {**headers, "Location": "https://evil.test"},
            ):
                self.assertEqual(assess(200, payload, signature,
                                        response_headers=altered_headers).kind,
                                 "INVALID")
            self.assertEqual(assess(200, payload, signature,
                                    who=self.actor(expiry=-1)).kind, "INVALID")
            self.assertEqual(assess(200, payload, signature,
                                    resource=self.binding("OTHER")).kind, "INVALID")
            network.assert_not_called()

    def test_signed_fixture_cannot_bypass_revoked_oidc_browser_api_fence(self):
        """A browser replaying an opaque revoked cookie cannot fetch a Run."""
        from portal import core_authz_transport as wire
        self.session()
        with oidc_session._lock:
            oidc_session._sessions.pop(oidc_session._digest(HANDLE), None)
        with patch.object(wire, "assess_core_authz_reply_offline",
                          side_effect=AssertionError("offline-only")) as contract, \
             patch.object(acme_run_detail, "_read_core_run",
                          side_effect=AssertionError("no Core read")) as core, \
             patch.object(main, "get_json",
                          side_effect=AssertionError("no upstream")) as upstream:
            for rid in (RUN, OTHER, "RUN-NOT-FOUND", "RUN-forged!"):
                for prefix in ("/api/portal/runs/", "/runs/"):
                    response = self.client.get(prefix + rid, headers={
                        "Authorization": "Bearer forged-allow",
                        "X-Actor-ID": "admin", "X-Tenant-ID": "OTHER"})
                    self.assert_fence(response, 401)
            contract.assert_not_called()
            core.assert_not_called()
            upstream.assert_not_called()


    def test_independent_signed_core_and_native_glpi_tls_are_still_unqualified(self):
        """Two disposable TLS origins: signed ALLOW + native GLPI shape != ACL."""
        import copy
        import json
        from portal import core_authz_transport as wire
        from portal_core_signed_glpi_fixture import (
            DisposableSignedCoreNativeGlpi, synthetic_native_glpi_shape_matches,
        )

        now = int(time.time())
        actor, binding, _, envelope = self.future_envelope(now)
        settings = self.authz_settings()
        plan = wire.prepare_core_authz_wire(actor, binding, env=settings, now=now)
        self.assertIsNotNone(plan)
        self.assertIs(plan.dispatch_allowed, False)
        envelope["request_nonce"] = plan.nonce

        with DisposableSignedCoreNativeGlpi(plan.service_bearer) as peers:
            settings["AIOPS_PORTAL_CORE_AUTHZ_RESPONSE_JWKS_JSON"] = json.dumps(
                peers.jwks)
            peers.payload = envelope
            status, signed, headers = peers.send_core(plan)
            self.assertEqual(status, 200)
            self.assertEqual(peers.core_observations[0]["body"],
                             json.loads(plan.body))
            self.assertEqual(len(peers.glpi_observations), 0)
            assessment = wire.assess_core_authz_reply_offline(
                status, signed["payload"], headers, signed["signature"],
                actor=actor, binding=binding, plan=plan, env=settings, now=now)
            self.assertEqual(assessment.kind, "SIGNED_SHAPE_UNQUALIFIED")
            self.assertEqual((assessment.portal_status, assessment.state,
                              assessment.read_permitted), (503, "UNKNOWN", False))
            self.assertFalse(wire.core_authz_read_permitted(
                signed["payload"], signed["signature"]))
            self.assertFalse(core_acl_consumer.positive_core_contract_matches(
                signed["payload"], actor, binding, now=now))

            # The independent GLPI test peer reads a *human* session's native
            # User/Profile/Entity/Ticket shapes, never a service-level xref.
            native = peers.read_native_glpi()
            self.assertTrue(synthetic_native_glpi_shape_matches(
                native, binding, glpi_user_id=77))
            self.assertEqual(len(peers.glpi_observations), 5)
            self.assertTrue(all(row["method"] == "GET"
                                for row in peers.glpi_observations))
            self.assertTrue(all(row["method"] == "POST"
                                for row in peers.core_observations))

            # Every variant is RE-SIGNED by the independent Core peer. A
            # syntactically authentic but foreign/revoked claim stays INVALID.
            variants = (
                {"actor_subject": "forged-operator"},
                {"actor_issuer": "https://foreign-idp.example.test"},
                {"actor_audience": "wrong-audience"},
                {"tenant_id": "FOREIGN"},
                {"run_id": "RUN-FOREIGN-999"},
                {"incident_id": "INC-FOREIGN-999"},
                {"ticket_id": "999"},
                {"glpi_entity_id": "99"},
                {"request_nonce": "r" * 43},
                {"revoked": True},
                {"expires_at": now - 1},
                {"glpi_readback": {
                    **envelope["glpi_readback"],
                    "actor_permission_confirmed": False}},
            )
            for changes in variants:
                with self.subTest(changes=changes):
                    peers.payload = {**envelope, **changes}
                    code, forged, h = peers.send_core(plan)
                    result = wire.assess_core_authz_reply_offline(
                        code, forged["payload"], h, forged["signature"],
                        actor=actor, binding=binding, plan=plan,
                        env=settings, now=now)
                    self.assertEqual(result.kind, "INVALID")
                    self.assertFalse(result.read_permitted)
                    self.assertEqual(result.portal_status, 503)
            # A signed answer replayed for a fresh nonce is not a grant.
            next_plan = wire.prepare_core_authz_wire(
                actor, binding, env=settings, now=now)
            self.assertNotEqual(next_plan.nonce, plan.nonce)
            self.assertEqual(wire.assess_core_authz_reply_offline(
                status, signed["payload"], headers, signed["signature"],
                actor=actor, binding=binding, plan=next_plan,
                env=settings, now=now).kind, "INVALID")
            # No business GET is made to Core, even by the explicit test peer.
            self.assertTrue(all(row["method"] == "POST"
                                for row in peers.core_observations))

    def test_native_glpi_profile_entity_user_denials_and_portal_no_leak(self):
        """Synthetic GLPI native rights cannot be inferred from viewer/OIDC."""
        import copy
        from portal import core_authz_transport as wire
        from portal_core_signed_glpi_fixture import (
            DisposableSignedCoreNativeGlpi, synthetic_native_glpi_shape_matches,
        )
        actor, binding = self.actor(), self.binding()
        settings = self.authz_settings()
        plan = wire.prepare_core_authz_wire(actor, binding, env=settings)
        self.assertIsNotNone(plan)
        with DisposableSignedCoreNativeGlpi(plan.service_bearer) as peers:
            rows = peers.read_native_glpi()
            for section, key, value in (
                ("getFullSession", "session", {
                    **rows["getFullSession"]["session"], "glpiID": 78}),
                ("getFullSession", "session", {
                    **rows["getFullSession"]["session"],
                    "glpiactiveentities": [99]}),
                ("User", "is_active", 0),
                ("Profile", "ticket", 0),
                ("Profile", "ticket", 2),  # READMY != native READ
                ("Profile", "ticket", True),
                ("Profile", "id", 5),
                ("Entity", "id", 99),
                ("Ticket", "id", 999),
                ("Ticket", "entities_id", 99),
            ):
                with self.subTest(section=section, key=key, value=value):
                    changed = copy.deepcopy(rows)
                    changed[section][key] = value
                    self.assertFalse(synthetic_native_glpi_shape_matches(
                        changed, binding, glpi_user_id=77))
            # Native GLPI records have no tenant claim: their shape alone
            # cannot prove tenant ownership, even when all IDs match.
            self.assertTrue(synthetic_native_glpi_shape_matches(
                rows, self.binding("OTHER"), glpi_user_id=77))
            self.assertFalse(core_acl_consumer.exact_binding_valid(
                actor, self.binding("OTHER")))

            # Portal remains unable to dispatch even with a reachable,
            # independently signed synthetic Core and GLPI human-session peer.
            self.session()
            before_core = len(peers.core_observations)
            before_glpi = len(peers.glpi_observations)
            with patch.dict(os.environ, settings), patch.object(
                    wire, "prepare_core_authz_wire",
                    side_effect=AssertionError("no Core authz dispatch")) as preflight, \
                 patch.object(acme_run_detail, "_read_core_run",
                              side_effect=AssertionError("no Core business GET")) as core, \
                 patch.object(main, "get_json",
                              side_effect=AssertionError("no upstream GLPI GET")) as upstream:
                projections = []
                for rid in (RUN, OTHER, "RUN-NOT-FOUND", "RUN-forged!"):
                    for prefix in ("/api/portal/runs/", "/runs/"):
                        response = self.client.get(prefix + rid, headers={
                            "Authorization": "Bearer forged-browser-token",
                            "X-Actor-ID": "forged", "X-Tenant-ID": "FOREIGN",
                            "X-GLPI-Profile": "manager"})
                        self.assert_fence(response, 503)
                        self.assertNotIn(plan.service_bearer, response.text)
                        self.assertNotIn(binding.glpi_instance_id, response.text)
                        self.assertNotIn(binding.incident_id, response.text)
                        if prefix.startswith("/api/"):
                            projections.append(response.json())
                self.assertTrue(all(item == projections[0]
                                    for item in projections))
                preflight.assert_not_called()
                core.assert_not_called()
                upstream.assert_not_called()
            self.assertEqual(len(peers.core_observations), before_core)
            self.assertEqual(len(peers.glpi_observations), before_glpi)
            with oidc_session._lock:
                oidc_session._sessions.pop(oidc_session._digest(HANDLE), None)
            for prefix in ("/api/portal/runs/", "/runs/"):
                self.assert_fence(self.client.get(prefix + RUN), 401)
            self.assertFalse(wire.core_authz_read_permitted())


if __name__ == "__main__":
    unittest.main()
