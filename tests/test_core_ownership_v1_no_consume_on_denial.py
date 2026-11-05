"""#233 source regression: denied requests must never consume the replay ledger.

Synthetic inputs only. These tests are NOT independent OIDC/GLPI human evidence.
"""
import unittest

from core.ownership_v1 import OwnershipDenied, sign, verify_and_consume
from test_core_ownership_v1 import KEY, T, fixture


class NoConsumeOnDenialTests(unittest.TestCase):
    def test_bad_signature_or_binding_does_not_touch_ledger(self):
        claims, expected = fixture()
        calls = []

        def consume(*args):
            calls.append(args)
            return True

        cases = [
            (claims, "0" * 64, expected, True, True),
            (claims, sign(claims, KEY), dict(expected, actor_id="other"), True, True),
            (claims, sign(claims, KEY), dict(expected, glpi_ticket_id="other"), True, True),
            (claims, sign(claims, KEY), expected, False, True),
            (claims, sign(claims, KEY), expected, True, False),
        ]
        for c, signature, bindings, oidc, glpi in cases:
            with self.subTest(bindings=bindings, oidc=oidc, glpi=glpi):
                with self.assertRaises(OwnershipDenied):
                    verify_and_consume(c, signature, KEY, bindings, oidc, glpi,
                                       consume, now=T)
        self.assertEqual(calls, [])

    def test_ledger_truthy_result_cannot_authorize(self):
        claims, expected = fixture()
        for result in (1, "inserted", {"inserted": True}, None):
            with self.subTest(result=result):
                with self.assertRaises(OwnershipDenied):
                    verify_and_consume(claims, sign(claims, KEY), KEY, expected,
                                       True, True, lambda *_: result, now=T)


if __name__ == "__main__":
    unittest.main()
