"""Synthetic binding gate: authenticated backend claims must match trusted request context.
This contract does not establish issuer provenance or production authorization.
"""
import hashlib
import sqlite3
import unittest
from test_backend_attestation_boundary import KEY, sign_claims, attest_backend

FIELDS = ("tenant_id", "principal_id", "event_id", "resource_id",
          "twin_revision", "evidence_digest", "policy_version", "approval_id")

def verify_bound_context(claims, mac, key_id, trusted_keys, expected):
    """Fail closed: expected comes from authenticated backend, never user envelope."""
    if not isinstance(expected, dict) or set(expected) != set(FIELDS):
        return None
    if any(not isinstance(v, str) or not v for v in expected.values()):
        return None
    authenticated = attest_backend(claims, mac, key_id, trusted_keys)
    if authenticated is None:
        return None
    if any(authenticated[k] != expected[k] for k in FIELDS):
        return None
    return authenticated

class BackendBindingAdversarialTests(unittest.TestCase):
    def setUp(self):
        self.claims = dict(tenant_id="tenant-A", principal_id="p1", event_id="e1",
                           resource_id="opaque:001", twin_revision="r1",
                           evidence_digest=hashlib.sha256(b"fixture").hexdigest(),
                           policy_version="policy1", approval_id="a1")
        self.keys = {"backend-issuer": KEY}
        self.mac = sign_claims(self.claims)
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE nonce(tenant TEXT, nonce TEXT, PRIMARY KEY(tenant,nonce))")
    def tearDown(self):
        self.db.close()
    def check(self, claims=None, mac=None, expected=None, keys=None):
        return verify_bound_context(self.claims if claims is None else claims,
                                    self.mac if mac is None else mac, "backend-issuer",
                                    self.keys if keys is None else keys,
                                    self.claims if expected is None else expected)
    def assert_denied_without_mutation(self, result):
        self.assertIsNone(result)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM nonce").fetchone()[0], 0)
        self.assertFalse(self.db.in_transaction)
    def test_valid_detached_context(self):
        got = self.check()
        self.assertEqual(got, self.claims)
        self.assertIsNot(got, self.claims)
    def test_signed_other_tenant_denied(self):
        foreign = dict(self.claims, tenant_id="tenant-B")
        self.assert_denied_without_mutation(self.check(claims=foreign, mac=sign_claims(foreign)))
    def test_signed_other_resource_denied(self):
        foreign = dict(self.claims, resource_id="opaque:other")
        self.assert_denied_without_mutation(self.check(claims=foreign, mac=sign_claims(foreign)))
    def test_signed_other_digest_denied(self):
        foreign = dict(self.claims, evidence_digest="0" * 64)
        self.assert_denied_without_mutation(self.check(claims=foreign, mac=sign_claims(foreign)))
    def test_signed_other_principal_denied(self):
        foreign = dict(self.claims, principal_id="other")
        self.assert_denied_without_mutation(self.check(claims=foreign, mac=sign_claims(foreign)))
    def test_signed_other_policy_or_approval_denied(self):
        for field in ("policy_version", "approval_id", "twin_revision", "event_id"):
            with self.subTest(field=field):
                foreign = dict(self.claims, **{field: "other"})
                self.assert_denied_without_mutation(self.check(claims=foreign, mac=sign_claims(foreign)))
    def test_missing_expected_field_denied(self):
        expected = dict(self.claims)
        expected.pop("resource_id")
        self.assert_denied_without_mutation(self.check(expected=expected))
    def test_untrusted_key_or_invalid_mac_denied_then_recovery(self):
        self.assert_denied_without_mutation(self.check(keys={}))
        self.assert_denied_without_mutation(self.check(mac="0" * 64))
        self.assertEqual(self.check(), self.claims)

if __name__ == "__main__":
    unittest.main()
