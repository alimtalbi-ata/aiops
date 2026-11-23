"""Synthetic Event -> Twin/Evidence -> GAMMA DENY smoke contract.

Only stdlib and synthetic fixtures. No production identity, ACL or API binding.
Run from v3-spike/contracts with: python -m unittest -v test_vertical_slice_deny.py
"""
import hashlib
import sqlite3
import unittest

from test_backend_attestation_boundary import KEY, sign_claims
from test_backend_atomic_consume import verify_bind_and_consume


def synthetic_deny(db, claims, expected, nonce, keys=None, mac=None):
    """Fail closed; a DENY result never becomes an approval or a mutation."""
    if claims.get("approval_id") != "DENY" or expected.get("approval_id") != "DENY":
        return {"decision": "DENY", "evidence": None, "accepted": False}
    authenticated = verify_bind_and_consume(
        db, claims, sign_claims(claims) if mac is None else mac,
        "backend-issuer", {"backend-issuer": KEY} if keys is None else keys,
        expected, nonce)
    if not authenticated:
        return {"decision": "DENY", "evidence": None, "accepted": False}
    return {"decision": "DENY", "evidence": {
        "tenant_id": claims["tenant_id"],
        "resource_id": claims["resource_id"],
        "event_id": claims["event_id"],
        "digest": claims["evidence_digest"],
    }, "accepted": True}


class VerticalSliceDenyTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:", isolation_level=None)
        self.db.execute("CREATE TABLE consumed_nonce(tenant TEXT NOT NULL, nonce TEXT NOT NULL, PRIMARY KEY(tenant,nonce))")
        self.claims = {
            "tenant_id": "synthetic-acme", "principal_id": "synthetic-operator",
            "event_id": "synthetic-event-1", "resource_id": "opaque:host:1",
            "twin_revision": "rev-1",
            "evidence_digest": hashlib.sha256(b"synthetic-event-1").hexdigest(),
            "policy_version": "synthetic-policy-1", "approval_id": "DENY",
        }

    def tearDown(self):
        self.db.close()

    def count(self):
        return self.db.execute("SELECT COUNT(*) FROM consumed_nonce").fetchone()[0]

    def run_gate(self, claims=None, expected=None, nonce="synthetic-nonce-1", **kwargs):
        return synthetic_deny(self.db, self.claims if claims is None else claims,
                              self.claims if expected is None else expected,
                              nonce, **kwargs)

    def test_valid_synthetic_deny_evidence_and_single_nonce(self):
        result = self.run_gate()
        self.assertEqual(result["decision"], "DENY")
        self.assertTrue(result["accepted"])
        self.assertEqual(result["evidence"]["digest"], self.claims["evidence_digest"])
        self.assertEqual(self.count(), 1)
        self.assertFalse(self.run_gate()["accepted"])
        self.assertEqual(self.count(), 1)

    def test_foreign_tenant_signed_but_unbound_no_write(self):
        other = dict(self.claims, tenant_id="foreign-tenant")
        self.assertFalse(self.run_gate(claims=other)["accepted"])
        self.assertEqual(self.count(), 0)

    def test_foreign_resource_and_digest_no_write(self):
        for field, value in (("resource_id", "opaque:other"),
                             ("evidence_digest", "0" * 64)):
            with self.subTest(field=field):
                self.assertFalse(self.run_gate(claims=dict(self.claims, **{field: value}))["accepted"])
                self.assertEqual(self.count(), 0)

    def test_revoked_issuer_no_write_then_recover(self):
        self.assertFalse(self.run_gate(keys={})["accepted"])
        self.assertEqual(self.count(), 0)
        self.assertTrue(self.run_gate()["accepted"])

    def test_invalid_mac_no_write_then_recover(self):
        self.assertFalse(self.run_gate(mac="0" * 64)["accepted"])
        self.assertEqual(self.count(), 0)
        self.assertTrue(self.run_gate()["accepted"])

    def test_unapproved_context_no_write(self):
        changed = dict(self.claims, approval_id="ALLOW")
        self.assertFalse(self.run_gate(claims=changed, expected=changed)["accepted"])
        self.assertEqual(self.count(), 0)

    def test_sqlite_failure_no_write_then_recover(self):
        self.db.execute("CREATE TRIGGER deny_insert BEFORE INSERT ON consumed_nonce BEGIN SELECT RAISE(ABORT,'synthetic fault'); END")
        self.assertFalse(self.run_gate()["accepted"])
        self.assertEqual(self.count(), 0)
        self.db.execute("DROP TRIGGER deny_insert")
        self.assertTrue(self.run_gate()["accepted"])


if __name__ == "__main__":
    unittest.main()
