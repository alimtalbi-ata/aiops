"""Core #233: isolated signed-contract roundtrip, NOT human OIDC/GLPI authority.

These stub verifiers exercise wiring only. Never treat this fixture as an
authorization source, a LIVE credential, or a human E2E proof.
"""
import unittest

from app.core.ownership_v1 import FIELDS, VERSION, sign
from app.core.ownership_provenance_v1 import ownership_evidence_http_decision


class SignedRoundtripContractTests(unittest.TestCase):
    def setUp(self):
        self.key = b"isolated-contract-test-key-32-bytes!!"
        self.expected = {
            "issuer": "core-test", "subject": "user-1", "tenant_id": "tenant-1",
            "actor_id": "actor-1", "incident_id": "INC-1", "run_id": "RUN-1",
            "glpi_ticket_id": "GLPI-1", "glpi_entity_id": "entity-1",
        }
        self.claims = dict(self.expected, version=VERSION, scope="run:read",
                           jti="jti-1", iat=100, exp=200,
                           oidc_proof_sha256="a" * 64,
                           glpi_readmy_proof_sha256="b" * 64)
        self.assertEqual(set(self.claims), set(FIELDS))
        self.consumed = set()
        self.calls = []

    def oidc(self, *_):
        self.calls.append("oidc")
        return {"verified": True, "proof_sha256": "a" * 64}

    def glpi(self, *_):
        self.calls.append("glpi")
        return {"verified": True, "proof_sha256": "b" * 64}

    def consume(self, issuer, jti, expiry):
        self.calls.append("ledger")
        key = (issuer, jti)
        if key in self.consumed:
            return False
        self.consumed.add(key)
        return True

    def decide(self, claims=None, signature=None, expected=None):
        claims = self.claims if claims is None else claims
        signature = sign(claims, self.key) if signature is None else signature
        return ownership_evidence_http_decision(
            claims, signature, self.key,
            self.expected if expected is None else expected,
            self.oidc, self.glpi, self.consume, now=150,
        )

    def test_signed_roundtrip_then_replay_denied(self):
        self.assertEqual(self.decide(),
                         (200, {"status": "VERIFIED", "run_id": "RUN-1",
                                "incident_id": "INC-1"}))
        self.assertEqual(self.decide(), (503, {"status": "UNKNOWN"}))
        self.assertEqual(self.calls, ["oidc", "glpi", "ledger"] * 2)
        self.assertEqual(self.consumed, {("core-test", "jti-1")})

    def test_tampered_actor_binding_never_consumes(self):
        tampered = dict(self.claims, actor_id="other-actor")
        signature = sign(self.claims, self.key)
        self.assertEqual(self.decide(tampered, signature),
                         (503, {"status": "UNKNOWN"}))
        self.assertNotIn("ledger", self.calls)

    def test_valid_signature_wrong_tenant_never_consumes(self):
        expected = dict(self.expected, tenant_id="other-tenant")
        self.assertEqual(self.decide(expected=expected),
                         (503, {"status": "UNKNOWN"}))
        self.assertNotIn("ledger", self.calls)


if __name__ == "__main__":
    unittest.main()
