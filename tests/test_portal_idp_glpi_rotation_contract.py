"""Disposable IdP→GLPI human identity and Core signer rotation contract.

Synthetic RSA/JWKS and GLPI TLS peer are NOT independently attested authority.
All positive Portal dispatch/read fences remain closed.
"""
import base64
import copy
import json
import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from portal import core_authz_transport as wire
from portal import core_acl_consumer, oidc_session
from portal.oidc_identity import IdentityRejected, verify_server_oidc_assertion
from portal_core_signed_glpi_fixture import (
    DisposableSignedCoreNativeGlpi, synthetic_native_glpi_shape_matches,
)

ISSUER = "https://idp.example.test/realms/acme"
AUDIENCE = "aiops2-portal"
HEADERS = {"Cache-Control": "no-store", "Pragma": "no-cache",
           "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"}


def b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def jwk(private, kid):
    numbers = private.public_key().public_numbers()
    return {"kid": kid, "kty": "RSA", "alg": "RS256", "use": "sig",
            "n": b64(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")),
            "e": b64(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big"))}


class PortalIdpGlpiRotationContract(unittest.TestCase):
    def setUp(self):
        self.now = int(time.time())
        self.idp_private = rsa.generate_private_key(public_exponent=65537,
                                                    key_size=2048)
        self.idp_env = {
            "AIOPS_PORTAL_OIDC_ISSUER": ISSUER,
            "AIOPS_PORTAL_OIDC_AUDIENCE": AUDIENCE,
            "AIOPS_PORTAL_OIDC_JWKS_JSON": json.dumps({
                "keys": [jwk(self.idp_private, "idp-pinned-v1")]}),
            "AIOPS_PORTAL_OIDC_TENANT_GROUP_MAP_JSON":
                json.dumps({"tenant-acme": "ACME", "tenant-foreign": "FOREIGN"}),
            "AIOPS_PORTAL_OIDC_ROLE_GROUP_MAP_JSON":
                json.dumps({"role-n2": "N2"}),
        }
        self.claims = {
            "iss": ISSUER, "aud": AUDIENCE, "sub": "operator-123",
            "iat": self.now - 5, "nbf": self.now - 5,
            "exp": self.now + 300, "nonce": "oidc-challenge-123",
            "jti": "synthetic-idp-jti-001",
            "groups": ["tenant-acme", "role-n2"],
        }
        self.settings = {
            "AIOPS_PORTAL_READ_TOKEN": "viewer-" + "v" * 40,
            "AIOPS_PORTAL_CORE_XREF_ORIGIN": "https://core.example.test:8443",
            "AIOPS_PORTAL_CORE_XREF_SERVICE_TOKEN": "xref-" + "s" * 40,
            "AIOPS_PORTAL_CORE_XREF_SCOPE": "itsm:xref:read",
            "AIOPS_PORTAL_CORE_AUTHZ_ORIGIN": "https://core.example.test:8443",
            "AIOPS_PORTAL_CORE_AUTHZ_SERVICE_TOKEN": "authz-" + "a" * 40,
            "AIOPS_PORTAL_CORE_AUTHZ_SCOPE": "actor:resource:authorize",
        }
        self.binding = core_acl_consumer.ServerXref(
            "ACME", "RUN-ACME-123", "INC-ACME-123",
            "glpi-acme", "123", "42")
        # Test-only explicit IdP-subject-to-GLPI-user mapping. Not a Portal
        # production mapping, nor proof of native human permissions.
        self.synthetic_mapping = {(ISSUER, "operator-123", "ACME"): 77}

    def token(self, claims=None, *, private=None, kid="idp-pinned-v1"):
        header = b64(json.dumps({"alg": "RS256", "typ": "JWT", "kid": kid},
                                separators=(",", ":")).encode())
        body = b64(json.dumps(self.claims if claims is None else claims,
                              separators=(",", ":")).encode())
        signed = (header + "." + body).encode("ascii")
        key = private or self.idp_private
        return header + "." + body + "." + b64(
            key.sign(signed, padding.PKCS1v15(), hashes.SHA256()))

    def actor(self, claims=None):
        return verify_server_oidc_assertion(
            self.token(claims), env=self.idp_env, now=self.now,
            expected_nonce="oidc-challenge-123")

    def envelope(self, actor, nonce):
        n = self.now
        return {
            "schema": "aiops.core-actor-resource-authorization.v1",
            "decision": "ALLOW", "permission": "run:read",
            "tenant_acl_qualified": True, "acl_version": "v1",
            "decision_id": "d" * 24,
            "actor_subject": actor.subject, "actor_issuer": actor.issuer,
            "actor_audience": actor.audience, "tenant_id": "ACME",
            "run_id": self.binding.run_id, "incident_id": self.binding.incident_id,
            "glpi_instance_id": self.binding.glpi_instance_id,
            "ticket_id": self.binding.ticket_id,
            "glpi_entity_id": self.binding.glpi_entity_id,
            "request_nonce": nonce, "issued_at": n - 5,
            "expires_at": n + 30, "revocation_checked_at": n - 2,
            "revoked": False,
            "delegation": {
                "kind": "CORE_VERIFIED_OIDC_DELEGATION",
                "subject": actor.subject, "issuer": actor.issuer,
                "audience": actor.audience, "tenant_id": actor.tenant_id,
                "expires_at": n + 60, "revoked": False},
            "glpi_readback": {
                "kind": "INDEPENDENT_AUTHENTICATED_GLPI_READBACK",
                "instance_id": self.binding.glpi_instance_id,
                "ticket_id": self.binding.ticket_id,
                "entity_id": self.binding.glpi_entity_id,
                "permission": "ticket:read", "verified_at": n - 4,
                "expires_at": n + 60, "ownership_confirmed": True,
                "actor_permission_confirmed": True,
                "run_ticket_binding_confirmed": True},
        }

    def assess(self, response, actor, plan, settings):
        status, body, headers = response
        return wire.assess_core_authz_reply_offline(
            status, body["payload"], headers, body["signature"],
            actor=actor, binding=self.binding, plan=plan,
            env=settings, now=self.now)

    def test_idp_verified_subject_maps_only_to_explicit_glpi_user(self):
        actor = self.actor()
        self.assertEqual((actor.subject, actor.tenant_id, actor.roles),
                         ("operator-123", "ACME", ("N2",)))
        self.assertFalse(actor.tenant_acl_qualified)
        self.assertEqual(self.synthetic_mapping.get(
            (actor.issuer, actor.subject, actor.tenant_id)), 77)
        with DisposableSignedCoreNativeGlpi("authz-" + "a" * 40) as peers:
            native = peers.read_native_glpi()
            self.assertTrue(synthetic_native_glpi_shape_matches(
                native, self.binding, glpi_user_id=77))
            self.assertFalse(synthetic_native_glpi_shape_matches(
                native, self.binding, glpi_user_id=78))
            self.assertEqual(len(peers.glpi_observations), 5)
            self.assertFalse(wire.core_authz_read_permitted())
            # Matching GLPI native shapes have no tenant claim, so a
            # separately attested source-owned tenant link is still missing.
            self.assertTrue(synthetic_native_glpi_shape_matches(
                native, core_acl_consumer.ServerXref(
                    "FOREIGN", self.binding.run_id, self.binding.incident_id,
                    "glpi-acme", "123", "42"), glpi_user_id=77))

    def test_foreign_revoked_and_forged_idp_assertions_fail_closed(self):
        for change in (
            {"iss": "https://foreign-idp.example.test"},
            {"aud": "foreign-client"}, {"exp": self.now - 1},
            {"nonce": "replayed-nonce"},
            {"groups": ["tenant-acme", "tenant-foreign", "role-n2"]},
            {"groups": ["tenant-foreign", "role-n2"]},
        ):
            with self.subTest(change=change):
                claims = {**self.claims, **change}
                if change.get("groups") == ["tenant-foreign", "role-n2"]:
                    foreign = self.actor(claims)
                    self.assertEqual(foreign.tenant_id, "FOREIGN")
                    self.assertNotIn((foreign.issuer, foreign.subject,
                                      foreign.tenant_id), self.synthetic_mapping)
                    self.assertIsNone(wire.prepare_core_authz_wire(
                        foreign, self.binding, env=self.settings, now=self.now))
                else:
                    with self.assertRaises(IdentityRejected):
                        self.actor(claims)
        attacker = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        with self.assertRaises(IdentityRejected):
            verify_server_oidc_assertion(
                self.token(private=attacker), env=self.idp_env, now=self.now,
                expected_nonce="oidc-challenge-123")

    def test_independent_core_signer_rotation_requires_new_pinned_key(self):
        actor = self.actor()
        plan = wire.prepare_core_authz_wire(
            actor, self.binding, env=self.settings, now=self.now)
        self.assertIsNotNone(plan)
        self.assertIs(plan.dispatch_allowed, False)
        with DisposableSignedCoreNativeGlpi(plan.service_bearer) as peers:
            peers.payload = self.envelope(actor, plan.nonce)
            settings = {**self.settings,
                        "AIOPS_PORTAL_CORE_AUTHZ_RESPONSE_JWKS_JSON":
                            json.dumps(peers.jwks)}
            first = peers.send_core(plan)
            self.assertEqual(self.assess(first, actor, plan, settings).kind,
                             "SIGNED_SHAPE_UNQUALIFIED")
            peers.rotate_signer(retain_previous=True)
            settings["AIOPS_PORTAL_CORE_AUTHZ_RESPONSE_JWKS_JSON"] = json.dumps(
                peers.jwks)
            second = peers.send_core(plan)
            self.assertEqual(self.assess(second, actor, plan, settings).kind,
                             "SIGNED_SHAPE_UNQUALIFIED")
            self.assertEqual(self.assess(first, actor, plan, settings).kind,
                             "SIGNED_SHAPE_UNQUALIFIED")
            # Retiring the previous kid invalidates BOTH previous responses.
            peers.rotate_signer(kid="disposable-core-signer-v3")
            settings["AIOPS_PORTAL_CORE_AUTHZ_RESPONSE_JWKS_JSON"] = json.dumps(
                peers.jwks)
            third = peers.send_core(plan)
            self.assertEqual(self.assess(third, actor, plan, settings).kind,
                             "SIGNED_SHAPE_UNQUALIFIED")
            for stale in (first, second):
                self.assertEqual(self.assess(stale, actor, plan, settings).kind,
                                 "INVALID")
            # A duplicate kid is not a valid signer pin set.
            ambiguous = {**settings,
                "AIOPS_PORTAL_CORE_AUTHZ_RESPONSE_JWKS_JSON": json.dumps({
                    "keys": peers.jwks["keys"] * 2})}
            self.assertEqual(self.assess(third, actor, plan, ambiguous).kind,
                             "INVALID")
            self.assertTrue(all(row["method"] == "POST"
                                for row in peers.core_observations))
            self.assertEqual(peers.glpi_observations, [])
            self.assertFalse(wire.core_authz_read_permitted())

    def test_nonce_jti_replay_and_resigned_foreign_claims_never_grant(self):
        actor = self.actor()
        plan = wire.prepare_core_authz_wire(
            actor, self.binding, env=self.settings, now=self.now)
        with DisposableSignedCoreNativeGlpi(plan.service_bearer) as peers:
            settings = {**self.settings,
                        "AIOPS_PORTAL_CORE_AUTHZ_RESPONSE_JWKS_JSON":
                            json.dumps(peers.jwks)}
            peers.payload = self.envelope(actor, plan.nonce)
            response = peers.send_core(plan)
            # Offline signature verification alone is NOT a durable JTI/nonce
            # ledger: the same signed response matches twice, never grants.
            for _ in range(2):
                result = self.assess(response, actor, plan, settings)
                self.assertEqual((result.kind, result.portal_status,
                                  result.read_permitted),
                                 ("SIGNED_SHAPE_UNQUALIFIED", 503, False))
            # Illustrative disposable ledger only; no production activation.
            consumed = set()
            jti = self.claims["jti"]
            self.assertNotIn((jti, plan.nonce), consumed)
            consumed.add((jti, plan.nonce))
            self.assertIn((jti, plan.nonce), consumed)
            next_plan = wire.prepare_core_authz_wire(
                actor, self.binding, env=settings, now=self.now)
            self.assertNotEqual(next_plan.nonce, plan.nonce)
            self.assertEqual(self.assess(response, actor, next_plan, settings).kind,
                             "INVALID")
            for changes in (
                {"actor_subject": "foreign"},
                {"tenant_id": "FOREIGN"}, {"run_id": "RUN-FOREIGN-999"},
                {"ticket_id": "999"}, {"glpi_entity_id": "99"},
                {"revoked": True},
                {"delegation": {**peers.payload["delegation"], "revoked": True}},
            ):
                with self.subTest(changes=changes):
                    peers.payload = {**self.envelope(actor, plan.nonce), **changes}
                    forged = peers.send_core(plan)
                    result = self.assess(forged, actor, plan, settings)
                    self.assertEqual((result.kind, result.portal_status,
                                      result.read_permitted), ("INVALID", 503, False))
            self.assertEqual(peers.glpi_observations, [])
            self.assertTrue(all(row["method"] == "POST"
                                for row in peers.core_observations))


    def test_revoked_oidc_session_rechecked_after_core_unknown_no_upstream(self):
        from starlette.requests import Request
        actor = self.actor()
        plan = wire.prepare_core_authz_wire(
            actor, self.binding, env=self.settings, now=self.now)
        handle = "A" * 43
        scope = {
            "type": "http", "method": "GET",
            "path": "/api/portal/runs/RUN-ACME-123",
            "headers": [(b"cookie", (oidc_session._SESSION_COOKIE + "="
                                      + handle).encode("ascii"))],
            "query_string": b"", "scheme": "https",
            "server": ("portal.example.test", 443),
        }
        request = Request(scope)
        unknown = {"schema": "aiops.core-actor-resource-authorization.v1",
                   "decision": "UNKNOWN"}
        with oidc_session._lock:
            oidc_session._sessions[oidc_session._digest(handle)] = (
                oidc_session._Session(actor, self.now + 200))
        try:
            with patch("urllib.request.urlopen",
                       side_effect=AssertionError("no upstream")) as upstream:
                first = wire.assess_core_negative_for_session(
                    request, binding=self.binding, plan=plan, status_code=200,
                    payload=unknown, headers=HEADERS, env=self.settings,
                    now=self.now)
                self.assertEqual((first.kind, first.portal_status,
                                  first.read_permitted),
                                 ("CURRENT_CORE_NEGATIVE", 503, False))
                # Signed/unsigned ALLOW is never consumed by this session gate.
                forged = wire.assess_core_negative_for_session(
                    request, binding=self.binding, plan=plan, status_code=200,
                    payload={"schema": unknown["schema"], "decision": "ALLOW"},
                    headers=HEADERS, env=self.settings, now=self.now)
                self.assertEqual((forged.kind, forged.portal_status,
                                  forged.read_permitted), ("INVALID", 503, False))
                with oidc_session._lock:
                    oidc_session._sessions.pop(oidc_session._digest(handle), None)
                revoked = wire.assess_core_negative_for_session(
                    request, binding=self.binding, plan=plan, status_code=200,
                    payload=unknown, headers=HEADERS, env=self.settings,
                    now=self.now)
                self.assertEqual((revoked.kind, revoked.portal_status,
                                  revoked.read_permitted),
                                 ("SESSION_REQUIRED", 401, False))
                upstream.assert_not_called()
        finally:
            with oidc_session._lock:
                oidc_session._sessions.pop(oidc_session._digest(handle), None)


    def _emit_negative_receipt(self, name, checks, observations):
        """CI-only JSON receipt: synthetic negative assertions, never authority."""
        import hashlib
        import subprocess
        from datetime import datetime, timezone
        destination = os.environ.get("AIOPS_E2E_ARTIFACT_DIR")
        if not destination:
            return
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[1],
            text=True).strip()
        self.assertRegex(sha, r"^[0-9a-f]{40}$")
        payload = {
            "schema": "aiops.portal.negative-authority-receipt.v1",
            "case": name, "source_head": sha,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "provenance": "CI_DISPOSABLE_SYNTHETIC_ONLY",
            "authority": "NOT_INDEPENDENTLY_ATTESTED",
            "identity_only_is_glpi_permission": False,
            "core_signed_shape_is_authorization": False,
            "nonce_jti_ledger": "TEST_ONLY_NOT_DURABLE",
            "dispatch_allowed": False, "read_permitted": False,
            "portal_default": {"http_status": 503, "state": "UNKNOWN"},
            "revoked_oidc": {"http_status": 401, "state": "UNKNOWN"},
            "checks": checks, "observations": observations,
            "result": "NEGATIVE_CONTRACT_PASS",
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True).encode("ascii")
        receipt = {"receipt": payload, "sha256": hashlib.sha256(raw).hexdigest()}
        output = Path(destination)
        output.mkdir(parents=True, exist_ok=True)
        file = output / ("portal-authority-" + name + ".json")
        file.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n",
                        encoding="utf-8")
        self.assertEqual(hashlib.sha256(json.dumps(
            receipt["receipt"], sort_keys=True, separators=(",", ":"),
            ensure_ascii=True).encode("ascii")).hexdigest(), receipt["sha256"])

    def test_p0_source_owned_idp_glpi_native_shape_receipt(self):
        """Test-only source ownership is explicit; GLPI native shape alone is not."""
        actor = self.actor()
        self.assertEqual((actor.issuer, actor.subject, actor.tenant_id),
                         (ISSUER, "operator-123", "ACME"))
        self.assertFalse(actor.tenant_acl_qualified)
        source = {
            "provenance": "SYNTHETIC_TEST_ONLY", "tenant_id": "ACME",
            "actor_issuer": ISSUER, "actor_subject": "operator-123",
            "glpi_user_id": 77, "run_id": self.binding.run_id,
            "incident_id": self.binding.incident_id,
            "glpi_instance_id": self.binding.glpi_instance_id,
            "ticket_id": self.binding.ticket_id,
            "glpi_entity_id": self.binding.glpi_entity_id,
        }
        def shape_matches(proof, native, mapping):
            # Deliberately test-only: no independent source attestation exists.
            expected = {
                "provenance": "SYNTHETIC_TEST_ONLY",
                "tenant_id": actor.tenant_id,
                "actor_issuer": actor.issuer, "actor_subject": actor.subject,
                "glpi_user_id": 77, "run_id": self.binding.run_id,
                "incident_id": self.binding.incident_id,
                "glpi_instance_id": self.binding.glpi_instance_id,
                "ticket_id": self.binding.ticket_id,
                "glpi_entity_id": self.binding.glpi_entity_id,
            }
            return (proof == expected
                    and mapping.get((actor.issuer, actor.subject,
                                     actor.tenant_id)) == 77
                    and synthetic_native_glpi_shape_matches(
                        native, self.binding, glpi_user_id=77))
        changes = [
            ("tenant_id", "FOREIGN"), ("actor_issuer", "https://foreign.test"),
            ("actor_subject", "foreign-operator"), ("glpi_user_id", 78),
            ("run_id", "RUN-FOREIGN-999"),
            ("incident_id", "INC-FOREIGN-999"),
            ("glpi_instance_id", "glpi-foreign"), ("ticket_id", "999"),
            ("glpi_entity_id", "99"),
        ]
        with DisposableSignedCoreNativeGlpi(self.settings[
                "AIOPS_PORTAL_CORE_AUTHZ_SERVICE_TOKEN"]) as peers:
            native = peers.read_native_glpi()
            self.assertTrue(shape_matches(source, native, self.synthetic_mapping))
            for field, foreign in changes:
                with self.subTest(field=field):
                    self.assertFalse(shape_matches(
                        {**source, field: foreign}, native,
                        self.synthetic_mapping))
            for field, value in (
                ("User", {"id": 77, "is_active": 0}),
                ("Profile", {"id": 4, "ticket": 2}),  # READMY != READ
                ("Entity", {"id": 99}),
                ("Ticket", {"id": 123, "entities_id": 99}),
            ):
                with self.subTest(native=field):
                    changed = copy.deepcopy(native)
                    changed[field] = value
                    self.assertFalse(shape_matches(
                        source, changed, self.synthetic_mapping))
            self.assertFalse(shape_matches(
                source, native, {(ISSUER, "operator-123", "FOREIGN"): 77}))
            # GLPI native rows have no tenant ownership proof. Even this
            # perfectly matching test-only tuple cannot promote an ACL.
            self.assertFalse(wire.core_authz_read_permitted())
            self.assertEqual(peers.core_observations, [])
            self.assertEqual(len(peers.glpi_observations), 5)
        self._emit_negative_receipt(
            "source-binding",
            ["verified_oidc_issuer_audience_subject",
             "explicit_synthetic_subject_glpi_user_mapping",
             "nine_foreign_source_binding_variants_rejected",
             "native_readmy_inactive_user_foreign_entity_ticket_rejected",
             "no_independent_glpi_tenant_ownership",
             "no_core_authorization_or_business_get"],
            {"foreign_source_variants": len(changes),
             "native_negative_variants": 4, "glpi_fixture_gets": 5})

    def test_p0_signed_unknown_rotation_nonce_jti_receipt(self):
        """Signed UNKNOWN and disposable atomic ledger never create ALLOW."""
        from concurrent.futures import ThreadPoolExecutor
        from threading import Lock
        from portal.oidc_identity import _decode, _verify_rs256
        actor = self.actor()
        plan = wire.prepare_core_authz_wire(
            actor, self.binding, env=self.settings, now=self.now)
        self.assertIsNotNone(plan)
        self.assertIs(plan.dispatch_allowed, False)
        # No synthetic ALLOW is constructed in this cycle.
        unknown = {"schema": "aiops.core-actor-resource-authorization.v1",
                   "decision": "UNKNOWN", "request_nonce": plan.nonce,
                   "tenant_id": actor.tenant_id, "run_id": self.binding.run_id}
        with DisposableSignedCoreNativeGlpi(plan.service_bearer) as peers:
            peers.payload = unknown
            first = peers.send_core(plan)
            def pinned_signature_valid(reply, jwks):
                payload, signature = reply[1]["payload"], reply[1]["signature"]
                try:
                    _verify_rs256(
                        wire._canonical_signed_bytes(plan.origin, payload),
                        _decode(signature["signature"]), signature["kid"], jwks)
                    return True
                except (IdentityRejected, IdentityUnavailable, ValueError,
                        TypeError, KeyError):
                    return False
            from portal.oidc_identity import IdentityUnavailable
            self.assertTrue(pinned_signature_valid(first, peers.jwks))
            peers.rotate_signer(kid="disposable-core-signer-v2",
                                retain_previous=True)
            second = peers.send_core(plan)
            self.assertTrue(pinned_signature_valid(first, peers.jwks))
            self.assertTrue(pinned_signature_valid(second, peers.jwks))
            peers.rotate_signer(kid="disposable-core-signer-v3")
            third = peers.send_core(plan)
            self.assertFalse(pinned_signature_valid(first, peers.jwks))
            self.assertFalse(pinned_signature_valid(second, peers.jwks))
            self.assertTrue(pinned_signature_valid(third, peers.jwks))
            settings = {**self.settings,
                        "AIOPS_PORTAL_CORE_AUTHZ_RESPONSE_JWKS_JSON":
                            json.dumps(peers.jwks)}
            for reply in (first, second, third):
                assessed = self.assess(reply, actor, plan, settings)
                self.assertEqual((assessed.kind, assessed.portal_status,
                                  assessed.read_permitted), ("INVALID", 503, False))
            # This lock/set is disposable and cannot qualify a durable
            # cross-worker Core ledger. It only checks the replay requirement.
            lock, consumed = Lock(), set()
            key = (actor.issuer, actor.subject, self.claims["jti"], plan.nonce)
            def consume_once():
                with lock:
                    if key in consumed:
                        return False
                    consumed.add(key)
                    return True
            with ThreadPoolExecutor(max_workers=8) as executor:
                outcomes = list(executor.map(lambda _: consume_once(), range(16)))
            self.assertEqual(outcomes.count(True), 1)
            self.assertEqual(outcomes.count(False), 15)
            next_plan = wire.prepare_core_authz_wire(
                actor, self.binding, env=settings, now=self.now)
            self.assertNotEqual(next_plan.nonce, plan.nonce)
            for foreign in (
                {**unknown, "tenant_id": "FOREIGN"},
                {**unknown, "run_id": "RUN-FOREIGN-999"},
                {**unknown, "request_nonce": next_plan.nonce},
                {**unknown, "revoked": True},
            ):
                peers.payload = foreign
                signed_foreign = peers.send_core(plan)
                self.assertEqual(self.assess(
                    signed_foreign, actor, plan, settings).portal_status, 503)
            self.assertEqual(peers.glpi_observations, [])
            self.assertTrue(all(row["method"] == "POST"
                                for row in peers.core_observations))
            self.assertFalse(wire.core_authz_read_permitted())
        self._emit_negative_receipt(
            "signed-unknown-replay",
            ["synthetic_core_signed_unknown_only",
             "pinned_signer_overlap_and_retirement",
             "expired_retired_key_rejected",
             "nonce_jti_concurrent_duplicate_rejected_in_disposable_set",
             "foreign_tenant_run_nonce_revoked_shapes_no_read",
             "no_glpi_business_get_no_positive_allow"],
            {"signed_unknown_requests": 7, "concurrent_attempts": 16,
             "disposable_unique_consumptions": 1,
             "durable_core_ledger_attested": False})

    def test_p0_api_revocation_presence_and_bearer_receipt(self):
        """Actual Portal ASGI API refuses without disclosing resource presence."""
        from fastapi.testclient import TestClient
        from portal import main, acme_run_detail
        handle = "R" * 43
        actor = self.actor()
        now = int(time.time())
        runs = ("RUN-ACME-123", "RUN-FOREIGN-999", "RUN-FORGED-999")
        with patch.dict(os.environ, self.settings):
            with oidc_session._lock:
                oidc_session._sessions[oidc_session._digest(handle)] = (
                    oidc_session._Session(actor, now + 200))
            try:
                with TestClient(main.app, base_url="https://portal.example.test") as client, \
                     patch.object(acme_run_detail, "_read_core_run",
                                  side_effect=AssertionError("Core GET forbidden")) as core, \
                     patch.object(main, "get_json",
                                  side_effect=AssertionError("upstream forbidden")) as upstream, \
                     patch("urllib.request.urlopen",
                           side_effect=AssertionError("network forbidden")) as network:
                    client.cookies.set(oidc_session._SESSION_COOKIE, handle)
                    replies = []
                    for run in runs:
                        response = client.get("/api/portal/runs/" + run,
                            headers={"X-Actor-ID": "admin", "X-Tenant-ID": "FOREIGN",
                                     "X-GLPI-Ticket": "999"})
                        self.assertEqual(response.status_code, 503)
                        self.assertEqual(response.headers["cache-control"], "no-store")
                        self.assertIn("frame-ancestors 'none'",
                                      response.headers["content-security-policy"])
                        self.assertEqual(response.json()["state"], "UNKNOWN")
                        replies.append(response.json())
                        for secret in (
                            self.settings["AIOPS_PORTAL_CORE_AUTHZ_SERVICE_TOKEN"],
                            self.settings["AIOPS_PORTAL_CORE_XREF_SERVICE_TOKEN"],
                            "operator-123", "glpi-acme", "INC-ACME-123"):
                            self.assertNotIn(secret, response.text)
                            self.assertNotIn(secret, str(response.headers))
                    self.assertEqual(replies[0], replies[1])
                    self.assertEqual(replies[1], replies[2])
                    viewer = client.get("/api/portal/itsm", headers={
                        "Authorization": "Bearer " +
                        self.settings["AIOPS_PORTAL_READ_TOKEN"]})
                    self.assertEqual(viewer.status_code, 503)
                    self.assertFalse(viewer.json()["glpi_write_enabled"])
                    with oidc_session._lock:
                        oidc_session._sessions.pop(
                            oidc_session._digest(handle), None)
                    revoked = []
                    for run in runs:
                        response = client.get("/api/portal/runs/" + run)
                        self.assertEqual(response.status_code, 401)
                        self.assertEqual(response.json()["state"], "UNKNOWN")
                        revoked.append(response.json())
                    self.assertEqual(revoked[0], revoked[1])
                    self.assertEqual(revoked[1], revoked[2])
                    core.assert_not_called()
                    upstream.assert_not_called()
                    network.assert_not_called()
            finally:
                with oidc_session._lock:
                    oidc_session._sessions.pop(
                        oidc_session._digest(handle), None)
        self._emit_negative_receipt(
            "api-revocation",
            ["server_oidc_session_revalidated",
             "present_foreign_forged_run_same_503_unknown",
             "revoked_session_same_401_unknown",
             "viewer_bearer_not_glpi_human_permission",
             "no_core_business_get_or_foreign_origin",
             "no_service_bearer_or_ticket_disclosure"],
            {"run_variants": len(runs), "valid_session_http": 503,
             "revoked_session_http": 401, "upstream_business_gets": 0})


if __name__ == "__main__":
    unittest.main()
