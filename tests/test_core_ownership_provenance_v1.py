"""Core #233 evidence authority binding: no provider boolean grants authority."""
import unittest

from app.core.ownership_provenance_v1 import ownership_evidence_http_decision


class EvidenceBindingTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.claims = {
            "oidc_proof_sha256": "a" * 64,
            "glpi_readmy_proof_sha256": "b" * 64,
        }

    def decide(self, oidc, glpi):
        return ownership_evidence_http_decision(
            self.claims, "invalid", b"k" * 32, {}, oidc, glpi,
            lambda *_: self.calls.append("ledger") or True, now=100,
        )

    def test_same_provider_cannot_supply_both_authorities(self):
        provider = lambda *_: {"verified": True, "proof_sha256": "a" * 64}
        self.assertEqual(self.decide(provider, provider)[0], 503)
        self.assertEqual(self.calls, [])

    def test_oidc_digest_mismatch_blocks_glpi_and_ledger(self):
        def oidc(*_):
            self.calls.append("oidc")
            return {"verified": True, "proof_sha256": "c" * 64}
        def glpi(*_):
            self.calls.append("glpi")
            return {"verified": True, "proof_sha256": "b" * 64}
        self.assertEqual(self.decide(oidc, glpi)[0], 503)
        self.assertEqual(self.calls, ["oidc"])

    def test_glpi_digest_mismatch_blocks_ledger(self):
        oidc = lambda *_: {"verified": True, "proof_sha256": "a" * 64}
        glpi = lambda *_: {"verified": True, "proof_sha256": "c" * 64}
        self.assertEqual(self.decide(oidc, glpi)[0], 503)
        self.assertEqual(self.calls, [])

    def test_truthy_or_malformed_evidence_never_consumes(self):
        valid_glpi = lambda *_: {"verified": True, "proof_sha256": "b" * 64}
        for record in (True, 1, {"verified": 1, "proof_sha256": "a" * 64},
                       {"verified": True, "proof_sha256": "A" * 64},
                       {"verified": True, "proof_sha256": "a" * 64, "extra": 1},
                       {"verified": True, "proof_sha256": None}):
            with self.subTest(record=record):
                self.assertEqual(self.decide(lambda *_: record, valid_glpi)[0], 503)
        self.assertEqual(self.calls, [])

    def test_matching_digests_do_not_bypass_signature(self):
        oidc = lambda *_: {"verified": True, "proof_sha256": "a" * 64}
        glpi = lambda *_: {"verified": True, "proof_sha256": "b" * 64}
        self.assertEqual(self.decide(oidc, glpi), (503, {"status": "UNKNOWN"}))
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
