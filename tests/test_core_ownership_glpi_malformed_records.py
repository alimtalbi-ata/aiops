"""Core #233: malformed GLPI authority records must fail closed before PG16."""
import unittest

from app.core.ownership_provenance_v1 import ownership_evidence_http_decision


class GlpiReadmyMalformedRecordsTests(unittest.TestCase):
    def test_glpi_malformed_records_never_consume_ledger(self):
        claims = {"oidc_proof_sha256": "a" * 64,
                  "glpi_readmy_proof_sha256": "b" * 64}
        bad_records = (
            True, 1, None, [], "verified",
            {"verified": 1, "proof_sha256": "b" * 64},
            {"verified": False, "proof_sha256": "b" * 64},
            {"verified": True, "proof_sha256": "B" * 64},
            {"verified": True, "proof_sha256": "b" * 63},
            {"verified": True, "proof_sha256": "c" * 64},
            {"verified": True, "proof_sha256": b"b" * 64},
            {"verified": True, "proof_sha256": "b" * 64, "extra": True},
        )
        for record in bad_records:
            with self.subTest(record=repr(record)):
                calls = []
                def oidc(*_):
                    calls.append("oidc")
                    return {"verified": True, "proof_sha256": "a" * 64}
                def glpi(*_):
                    calls.append("glpi")
                    return record
                def consume(*_):
                    calls.append("ledger")
                    return True
                result = ownership_evidence_http_decision(
                    claims, "invalid", b"k" * 32, {}, oidc, glpi, consume,
                    now=100,
                )
                self.assertEqual(result, (503, {"status": "UNKNOWN"}))
                self.assertEqual(calls, ["oidc", "glpi"])


if __name__ == "__main__":
    unittest.main()
