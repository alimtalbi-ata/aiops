"""Core #233: authority ordering and revocation fail-closed regression tests.

All cases are negative; no synthetic authorization is produced.
"""
import unittest

from app.core.ownership_http_v1 import ownership_http_decision


class OwnershipAuthorityOrderingTests(unittest.TestCase):
    def setUp(self):
        self.events = []

    def run_decision(self, oidc, glpi, ledger=None):
        if ledger is None:
            ledger = lambda *_: self.events.append("ledger") or True
        return ownership_http_decision(
            {}, "invalid-signature", b"k" * 32, {},
            oidc, glpi, ledger, now=100,
        )

    def test_oidc_revocation_short_circuits_glpi_and_ledger(self):
        def oidc(*_):
            self.events.append("oidc")
            return False

        def glpi(*_):
            self.events.append("glpi")
            return True

        self.assertEqual(self.run_decision(oidc, glpi),
                         (503, {"status": "UNKNOWN"}))
        self.assertEqual(self.events, ["oidc"])

    def test_glpi_revocation_never_consumes(self):
        def oidc(*_):
            self.events.append("oidc")
            return True

        def glpi(*_):
            self.events.append("glpi")
            return False

        self.assertEqual(self.run_decision(oidc, glpi),
                         (503, {"status": "UNKNOWN"}))
        self.assertEqual(self.events, ["oidc", "glpi"])

    def test_missing_ledger_is_unknown_even_with_callable_authorities(self):
        self.assertEqual(self.run_decision(lambda *_: True,
                                           lambda *_: True,
                                           ledger=False),
                         (503, {"status": "UNKNOWN"}))
        self.assertEqual(self.events, [])

    def test_provider_failure_never_invokes_later_authority(self):
        def unavailable(*_):
            self.events.append("oidc")
            raise TimeoutError("issuer unavailable")

        def glpi(*_):
            self.events.append("glpi")
            return True

        self.assertEqual(self.run_decision(unavailable, glpi),
                         (503, {"status": "UNKNOWN"}))
        self.assertEqual(self.events, ["oidc"])


if __name__ == "__main__":
    unittest.main()
