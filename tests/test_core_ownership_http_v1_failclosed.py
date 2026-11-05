"""Negative contract tests for Core #233 HTTP fail-closed boundary."""
import unittest
from app.core.ownership_http_v1 import ownership_http_decision


class OwnershipHttpFailClosedTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.ledger = lambda *args: self.calls.append("ledger") or True

    def decide(self, oidc, glpi):
        return ownership_http_decision(
            {}, "not-a-signature", b"k" * 32, {},
            oidc, glpi, self.ledger, now=100,
        )

    def test_missing_authority_never_consumes(self):
        for oidc, glpi in ((None, None), (True, True),
                           (lambda *_: True, None)):
            self.assertEqual(self.decide(oidc, glpi),
                             (503, {"status": "UNKNOWN"}))
        self.assertEqual(self.calls, [])

    def test_ambiguous_authority_never_consumes(self):
        for result in (1, "true", {}, None, False):
            with self.subTest(result=result):
                self.assertEqual(
                    self.decide(lambda *_: result, lambda *_: True)[0], 503)
        self.assertEqual(self.calls, [])

    def test_glpi_denial_never_consumes(self):
        self.assertEqual(self.decide(lambda *_: True, lambda *_: False)[0], 503)
        self.assertEqual(self.calls, [])

    def test_provider_exception_never_consumes(self):
        def fail(*_):
            raise ConnectionError("unavailable")
        self.assertEqual(self.decide(fail, lambda *_: True)[0], 503)
        self.assertEqual(self.decide(lambda *_: True, fail)[0], 503)
        self.assertEqual(self.calls, [])

    def test_forged_signature_never_consumes(self):
        self.assertEqual(self.decide(lambda *_: True, lambda *_: True)[0], 503)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
