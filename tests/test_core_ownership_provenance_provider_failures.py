"""Core #233: provider failure ordering must never reach GLPI or ledger."""
import unittest

from app.core.ownership_provenance_v1 import ownership_evidence_http_decision


class ProvenanceProviderFailureTests(unittest.TestCase):
    def test_oidc_provider_exception_prevents_glpi_and_consume(self):
        calls = []
        claims = {"oidc_proof_sha256": "a" * 64,
                  "glpi_readmy_proof_sha256": "b" * 64}

        def oidc(*_):
            calls.append("oidc")
            raise TimeoutError("OIDC provider unavailable")

        def glpi(*_):
            calls.append("glpi")
            return {"verified": True, "proof_sha256": "b" * 64}

        def consume(*_):
            calls.append("ledger")
            return True

        status, payload = ownership_evidence_http_decision(
            claims, "invalid", b"k" * 32, {}, oidc, glpi, consume, now=100
        )
        self.assertEqual((status, payload), (503, {"status": "UNKNOWN"}))
        self.assertEqual(calls, ["oidc"])

    def test_glpi_provider_exception_prevents_consume(self):
        calls = []
        claims = {"oidc_proof_sha256": "a" * 64,
                  "glpi_readmy_proof_sha256": "b" * 64}

        def oidc(*_):
            calls.append("oidc")
            return {"verified": True, "proof_sha256": "a" * 64}

        def glpi(*_):
            calls.append("glpi")
            raise ConnectionError("GLPI READMY unavailable")

        def consume(*_):
            calls.append("ledger")
            return True

        status, payload = ownership_evidence_http_decision(
            claims, "invalid", b"k" * 32, {}, oidc, glpi, consume, now=100
        )
        self.assertEqual((status, payload), (503, {"status": "UNKNOWN"}))
        self.assertEqual(calls, ["oidc", "glpi"])


if __name__ == "__main__":
    unittest.main()
