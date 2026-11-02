"""Disposable OIDC/JWKS contract tests; no network, GLPI, Core or real IdP."""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal import oidc_identity as identity

NOW = 1800000000


def b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def token(payload=None, header=None, signature=b"synthetic-signature"):
    h = {"alg": "RS256", "typ": "JWT", "kid": "fixture-key"}
    if header:
        h.update(header)
    p = {"iss": "https://idp.example.test/realms/acme",
         "aud": "aiops2-portal", "sub": "operator-123",
         "iat": NOW - 60, "nbf": NOW - 60, "exp": NOW + 600,
         "groups": ["acme-tenant", "noc-n2"]}
    if payload:
        p.update(payload)
    return (b64(json.dumps(h).encode()) + "." +
            b64(json.dumps(p).encode()) + "." + b64(signature))


def config():
    return {
        "AIOPS_PORTAL_OIDC_ISSUER": "https://idp.example.test/realms/acme",
        "AIOPS_PORTAL_OIDC_AUDIENCE": "aiops2-portal",
        "AIOPS_PORTAL_OIDC_JWKS_JSON": json.dumps({"keys": [
            {"kid": "fixture-key", "kty": "RSA", "alg": "RS256",
             "use": "sig", "n": b64(b"\xff" * 256),
             "e": b64((65537).to_bytes(3, "big"))}]}),
        "AIOPS_PORTAL_OIDC_TENANT_GROUP_MAP_JSON":
            json.dumps({"acme-tenant": "ACME", "other-tenant": "OTHER"}),
        "AIOPS_PORTAL_OIDC_ROLE_GROUP_MAP_JSON":
            json.dumps({"noc-n2": "N2", "noc-n1": "N1", "noc-manager": "manager"}),
        "AIOPS_PORTAL_CORE_XREF_SERVICE_TOKEN": "core-xref-fixture-service-token-0001",
        "AIOPS_PORTAL_READ_TOKEN": "portal-viewer-fixture-token-0001",
    }


class PortalOIDCIdentityTests(unittest.TestCase):
    def verified(self, payload=None, header=None, env=None):
        # The mock only isolates claims tests. A separate test below verifies
        # real RSA signature/JWKS with disposable keys.
        with patch.object(identity, "_verify_rs256", return_value=None):
            return identity.verify_server_oidc_assertion(
                token(payload, header), env=config() if env is None else env, now=NOW)

    def test_identity_is_not_positive_core_acl(self):
        actor = self.verified()
        self.assertEqual((actor.subject, actor.tenant_id, actor.roles),
                         ("operator-123", "ACME", ("N2",)))
        self.assertFalse(actor.tenant_acl_qualified)

    def test_explicit_group_mapping_rejects_cross_tenant(self):
        for groups in (["noc-n2"], ["other-tenant", "acme-tenant", "noc-n2"],
                       ["acme-tenant"], ["acme-tenant", "noc-unknown"]):
            with self.subTest(groups=groups), self.assertRaises(identity.IdentityRejected):
                self.verified({"groups": groups})

    def test_issuer_audience_and_time_constraints(self):
        cases = [
            {"iss": "https://evil.example.test"},
            {"aud": "other-client"}, {"aud": ["aiops2-portal", "other-client"]},
            {"exp": NOW}, {"nbf": NOW + 40}, {"iat": NOW + 40},
            {"iat": NOW - 4000}, {"exp": NOW + 4000},
            {"exp": True}, {"sub": ""}, {"groups": "acme-tenant"},
            {"groups": ["acme-tenant", 123, "noc-n2"]},
        ]
        for claim in cases:
            with self.subTest(claim=claim), self.assertRaises(identity.IdentityRejected):
                self.verified(claim)

    def test_algorithm_none_jku_crit_and_ambiguous_kid_rejected(self):
        for header in ({"alg": "none"}, {"alg": "HS256"},
                       {"jku": "https://evil.example.test/jwks"},
                       {"crit": ["b64"]}, {"kid": ""}):
            with self.subTest(header=header), self.assertRaises(identity.IdentityRejected):
                self.verified(header=header)

    def test_invalid_pinned_configuration_fails_closed(self):
        cases = [
            {"AIOPS_PORTAL_OIDC_ISSUER": "http://idp.example.test"},
            {"AIOPS_PORTAL_OIDC_AUDIENCE": ""},
            {"AIOPS_PORTAL_OIDC_JWKS_JSON": "{}"},
            {"AIOPS_PORTAL_OIDC_ROLE_GROUP_MAP_JSON": '{"noc-n2":"superadmin"}'},
            {"AIOPS_PORTAL_OIDC_TENANT_GROUP_MAP_JSON": '{"a":"X","a":"Y"}'},
        ]
        for override in cases:
            with self.subTest(override=override), self.assertRaises(
                    (identity.IdentityUnavailable, identity.IdentityRejected)):
                self.verified(env={**config(), **override})

    def test_unsigned_or_oversize_assertions_never_return_context(self):
        for value in ("", "not-a-jwt", "a.b.c.d", "a" * 16385,
                      "e30.e30.!", 123):
            with self.subTest(value=str(value)[:30]), self.assertRaises(
                    (identity.IdentityRejected, identity.IdentityUnavailable)):
                identity.verify_server_oidc_assertion(value, env=config(), now=NOW)

    def test_invalid_utf8_claims_and_control_character_config_rejected(self):
        bad_payload = (b64(b'{"alg":"RS256","kid":"fixture-key"}') + "." +
                       b64(bytes([255])) + "." + b64(b"synthetic"))
        with patch.object(identity, "_verify_rs256", return_value=None):
            with self.assertRaises(identity.IdentityRejected):
                identity.verify_server_oidc_assertion(bad_payload, env=config(), now=NOW)
        settings = {**config(), "AIOPS_PORTAL_CORE_XREF_SERVICE_TOKEN":
                    "a" * 33 + chr(0)}
        actor = self.verified()
        with self.assertRaises(identity.IdentityRejected):
            identity.core_xref_preflight(
                actor, tenant_id="ACME", run_id="RUN-ACME-123",
                ticket_id="TICKET-001", env=settings)

    def test_no_core_xref_fetch_even_with_verified_identity(self):
        actor = self.verified()
        with patch("urllib.request.urlopen", side_effect=AssertionError("upstream forbidden")) as upstream:
            result = identity.core_xref_preflight(
                actor, tenant_id="ACME", run_id="RUN-ACME-123",
                ticket_id="TICKET-001", env=config())
        self.assertEqual(result, {"state": "UNKNOWN",
                                 "reason": "TENANT_ACL_NOT_QUALIFIED",
                                 "connection_state": "UNKNOWN",
                                 "tenant_acl_qualified": False})
        upstream.assert_not_called()

    def test_xref_rejects_foreign_run_and_shared_service_bearer(self):
        actor = self.verified()
        cases = [
            ("OTHER", "RUN-ACME-123", "TICKET-001", config()),
            ("ACME", "RUN-../foreign", "TICKET-001", config()),
            ("ACME", "RUN-ACME-123", "../ticket", config()),
            ("ACME", "RUN-ACME-123", "TICKET-001",
             {**config(), "AIOPS_PORTAL_CORE_XREF_SERVICE_TOKEN":
              config()["AIOPS_PORTAL_READ_TOKEN"]}),
        ]
        for tenant, run, ticket, settings in cases:
            with self.subTest(tenant=tenant, run=run, ticket=ticket), self.assertRaises(
                    identity.IdentityRejected):
                identity.core_xref_preflight(
                    actor, tenant_id=tenant, run_id=run, ticket_id=ticket, env=settings)

    def test_verified_context_cannot_be_promoted_by_client_claims(self):
        actor = self.verified()
        forged = identity.PortalActorContext(
            actor.subject, actor.tenant_id, actor.roles, actor.issuer,
            actor.audience, tenant_acl_qualified=True)
        with self.assertRaises(identity.IdentityRejected):
            identity.core_xref_preflight(
                forged, tenant_id="ACME", run_id="RUN-ACME-123",
                ticket_id="TICKET-001", env=config())

    def test_invalid_jwks_key_rejected_before_crypto_import(self):
        for update in ({"kty": "oct"}, {"alg": "HS256"}, {"use": "enc"},
                       {"n": b64(b"small")}, {"e": b64(b"\x03")}):
            settings = config()
            key = json.loads(settings["AIOPS_PORTAL_OIDC_JWKS_JSON"])["keys"][0]
            key.update(update)
            settings["AIOPS_PORTAL_OIDC_JWKS_JSON"] = json.dumps({"keys": [key]})
            with self.subTest(update=update), self.assertRaises(identity.IdentityRejected):
                identity.verify_server_oidc_assertion(token(), env=settings, now=NOW)

    def test_real_rsa_signature_and_tamper_with_disposable_jwks(self):
        # No skip: shared CI installs the explicit pinned Portal test requirement.
        from cryptography.hazmat.primitives.asymmetric import rsa, padding
        from cryptography.hazmat.primitives import hashes
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pub = private.public_key().public_numbers()
        settings = config()
        settings["AIOPS_PORTAL_OIDC_JWKS_JSON"] = json.dumps({"keys": [{
            "kid": "fixture-key", "kty": "RSA", "alg": "RS256", "use": "sig",
            "n": b64(pub.n.to_bytes((pub.n.bit_length()+7)//8, "big")),
            "e": b64(pub.e.to_bytes((pub.e.bit_length()+7)//8, "big")),
        }]})
        unsigned = token().rsplit(".", 1)[0]
        signature = private.sign(unsigned.encode("ascii"), padding.PKCS1v15(), hashes.SHA256())
        signed = unsigned + "." + b64(signature)
        actor = identity.verify_server_oidc_assertion(signed, env=settings, now=NOW)
        self.assertEqual(actor.tenant_id, "ACME")
        self.assertGreater(actor.expires_at, NOW)
        # Real signature, correct nonce, wrong nonce, rotated/unknown key.
        nonce_payload = {"nonce": "server-bound-nonce"}
        unsigned_nonce = token(nonce_payload).rsplit(".", 1)[0]
        signed_nonce = unsigned_nonce + "." + b64(private.sign(
            unsigned_nonce.encode("ascii"), padding.PKCS1v15(), hashes.SHA256()))
        verified = identity.verify_server_oidc_assertion(
            signed_nonce, env=settings, now=NOW,
            expected_nonce="server-bound-nonce")
        self.assertEqual(verified.subject, "operator-123")
        with self.assertRaises(identity.IdentityRejected):
            identity.verify_server_oidc_assertion(
                signed_nonce, env=settings, now=NOW,
                expected_nonce="forged-nonce")
        with self.assertRaises(identity.IdentityRejected):
            identity.verify_server_oidc_assertion(
                signed, env=settings, now=NOW, expected_nonce="server-bound-nonce")
        rotated = json.loads(settings["AIOPS_PORTAL_OIDC_JWKS_JSON"])
        rotated["keys"][0]["kid"] = "rotated-key"
        with self.assertRaises(identity.IdentityRejected):
            identity.verify_server_oidc_assertion(
                signed_nonce,
                env={**settings, "AIOPS_PORTAL_OIDC_JWKS_JSON": json.dumps(rotated)},
                now=NOW, expected_nonce="server-bound-nonce")
        tampered = signed[:-3] + ("AAA" if signed[-3:] != "AAA" else "BBB")
        with self.assertRaises(identity.IdentityRejected):
            identity.verify_server_oidc_assertion(tampered, env=settings, now=NOW)


if __name__ == "__main__":
    unittest.main()
