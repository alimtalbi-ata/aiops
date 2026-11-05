"""Core #233: signed Incident/Run binding isolation (synthetic harness only).

No human OIDC/GLPI evidence, no durable ledger qualification and no LIVE effects.
"""
import unittest
from app.core.ownership_v1 import VERSION, sign
from app.core.ownership_provenance_v1 import ownership_evidence_http_decision


class IncidentRunBindingTests(unittest.TestCase):
    def setUp(self):
        self.key = b"contract-test-key-with-32-plus-bytes"
        self.expected = dict(
            issuer="core-test", subject="subject-1", tenant_id="tenant-1",
            actor_id="actor-1", incident_id="INC-1", run_id="RUN-1",
            glpi_ticket_id="GLPI-1", glpi_entity_id="entity-1",
        )
        self.claims = dict(self.expected, version=VERSION, scope="run:read",
                           jti="jti-1", iat=100, exp=200,
                           oidc_proof_sha256="a" * 64,
                           glpi_readmy_proof_sha256="b" * 64)
        self.ledger_calls = []

    def oidc(self, *_):
        return {"verified": True, "proof_sha256": "a" * 64}

    def glpi(self, *_):
        return {"verified": True, "proof_sha256": "b" * 64}

    def consume(self, *args):
        self.ledger_calls.append(args)
        return True

    def decide(self, claims, expected=None, signature=None):
        return ownership_evidence_http_decision(
            claims, sign(claims, self.key) if signature is None else signature,
            self.key, self.expected if expected is None else expected,
            self.oidc, self.glpi, self.consume, now=150,
        )

    def test_valid_signature_cannot_cross_run_boundary(self):
        for field, other in (("run_id", "RUN-2"), ("incident_id", "INC-2"),
                             ("tenant_id", "tenant-2"), ("actor_id", "actor-2"),
                             ("glpi_ticket_id", "GLPI-2"),
                             ("glpi_entity_id", "entity-2")):
            with self.subTest(field=field):
                claims = dict(self.claims, **{field: other})
                self.assertEqual(self.decide(claims),
                                 (503, {"status": "UNKNOWN"}))
        self.assertEqual(self.ledger_calls, [])

    def test_signed_claims_cannot_be_rebound_to_another_expected_run(self):
        expected = dict(self.expected, run_id="RUN-2")
        self.assertEqual(self.decide(self.claims, expected),
                         (503, {"status": "UNKNOWN"}))
        self.assertEqual(self.ledger_calls, [])

    def test_reusing_signature_for_different_incident_denied(self):
        original_signature = sign(self.claims, self.key)
        altered = dict(self.claims, incident_id="INC-2")
        self.assertEqual(self.decide(altered, signature=original_signature),
                         (503, {"status": "UNKNOWN"}))
        self.assertEqual(self.ledger_calls, [])


if __name__ == "__main__":
    unittest.main()
