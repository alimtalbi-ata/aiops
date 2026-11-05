"""Core #233: signed inverted time windows must deny before replay ledger use.

Synthetic unit regression only; not independent human GLPI/OIDC evidence.
"""
import unittest
from core.ownership_v1 import OwnershipDenied, sign, verify_and_consume
from test_core_ownership_v1 import KEY, T, fixture


class OwnershipWindowRegression(unittest.TestCase):
    def test_signed_inverted_window_never_consumes(self):
        claims, expected = fixture()
        claims["iat"] = T + 20
        claims["exp"] = T + 10
        calls = []
        def consume(*args):
            calls.append(args)
            return True
        with self.assertRaises(OwnershipDenied):
            verify_and_consume(claims, sign(claims, KEY), KEY, expected,
                               True, True, consume, now=T)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
