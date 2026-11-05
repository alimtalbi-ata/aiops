"""Source-only contract tests; no synthetic GLPI/OIDC proof of human ALLOW."""
import unittest
from core.ownership_v1 import VERSION, OwnershipDenied, sign, verify_and_consume

KEY = b"k" * 32
T = 1800000000


def fixture():
    c = dict(version=VERSION, issuer="oidc-issuer", subject="human-sub",
             tenant_id="tenant-a", actor_id="actor-a", incident_id="incident-a",
             run_id="run-a", glpi_ticket_id="ticket-a", glpi_entity_id="entity-a",
             scope="run:read", jti="unique-jti", iat=T-30, exp=T+120,
             oidc_proof_sha256="a"*64, glpi_readmy_proof_sha256="b"*64)
    e = {k: c[k] for k in ("issuer", "subject", "tenant_id", "actor_id",
         "incident_id", "run_id", "glpi_ticket_id", "glpi_entity_id")}
    return c, e


class OwnershipContractTests(unittest.TestCase):
    def test_signed_contract_only_with_independent_authorities_and_durable_consume(self):
        c, e = fixture()
        calls = []
        result = verify_and_consume(c, sign(c, KEY), KEY, e, True, True,
                                    lambda *args: calls.append(args) or True, now=T)
        self.assertEqual(result["run_id"], "run-a")
        self.assertEqual(calls, [("oidc-issuer", "unique-jti", T+120)])

    def test_fail_closed_cases(self):
        c, e = fixture()
        cases = [
            (dict(c, tenant_id="foreign"), e, True, True, lambda *_: True, T),
            (c, dict(e, run_id="foreign"), True, True, lambda *_: True, T),
            (c, e, False, True, lambda *_: True, T),
            (c, e, True, False, lambda *_: True, T),
            (c, e, True, True, lambda *_: False, T),
            (c, e, True, True, None, T),
            (c, e, True, True, lambda *_: True, T+121),
        ]
        for claims, expected, oidc, glpi, ledger, now in cases:
            with self.subTest(claims=claims, expected=expected, now=now):
                with self.assertRaises(OwnershipDenied):
                    verify_and_consume(claims, sign(claims, KEY), KEY, expected,
                                       oidc, glpi, ledger, now=now)

    def test_strict_authority_and_binding_types(self):
        c, e = fixture()
        for oidc, glpi in [(1, True), (True, "verified"), ([], True), (True, 1)]:
            with self.subTest(oidc=oidc, glpi=glpi):
                with self.assertRaises(OwnershipDenied):
                    verify_and_consume(c, sign(c, KEY), KEY, e, oidc, glpi,
                                       lambda *_: True, now=T)
        for field in ("iat", "exp"):
            bad = dict(c, **{field: True})
            with self.subTest(field=field):
                with self.assertRaises(OwnershipDenied):
                    verify_and_consume(bad, sign(bad, KEY), KEY, e, True, True,
                                       lambda *_: True, now=T)
        for value in (True, "1800000000", 1800000000):
            with self.subTest(now=value):
                with self.assertRaises(OwnershipDenied):
                    verify_and_consume(c, sign(c, KEY), KEY, e, True, True,
                                       lambda *_: True, now=value)
        for value in (1, None, "", ["tenant-a"]):
            bad_expected = dict(e, tenant_id=value)
            with self.subTest(expected=value):
                with self.assertRaises(OwnershipDenied):
                    verify_and_consume(c, sign(c, KEY), KEY, bad_expected,
                                       True, True, lambda *_: True, now=T)

    def test_forged_signature_and_ledger_failure(self):
        c, e = fixture()
        with self.assertRaises(OwnershipDenied):
            verify_and_consume(c, sign(c, b"x"*32), KEY, e, True, True,
                               lambda *_: True, now=T)
        def unavailable(*_):
            raise ConnectionError("pg16 unavailable")
        with self.assertRaises(OwnershipDenied):
            verify_and_consume(c, sign(c, KEY), KEY, e, True, True, unavailable, now=T)


if __name__ == "__main__":
    unittest.main()
