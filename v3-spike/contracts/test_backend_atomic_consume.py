"""Synthetic atomic nonce gate for already authenticated Twin/Evidence bindings.
Not production authorization: trusted expected fields and keys must originate externally.
"""
import hashlib
import sqlite3
import unittest
from test_backend_attestation_boundary import KEY, sign_claims
from test_backend_binding_adversarial import verify_bound_context

def verify_bind_and_consume(db, claims, mac, key_id, trusted_keys, expected, nonce):
    """No nonce write until authentication and all eight backend bindings pass."""
    if not isinstance(nonce, str) or not nonce or len(nonce) > 128 or not nonce.isascii():
        return False
    if any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for c in nonce):
        return False
    bound = verify_bound_context(claims, mac, key_id, trusted_keys, expected)
    if bound is None:
        return False
    if db.in_transaction:
        return False
    try:
        db.execute("BEGIN IMMEDIATE")
        db.execute("INSERT INTO consumed_nonce(tenant,nonce) VALUES (?,?)", (bound["tenant_id"], nonce))
        db.commit()
        return True
    except sqlite3.Error:
        db.rollback()
        return False

class BackendAtomicConsumeTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:", isolation_level=None)
        self.db.execute("CREATE TABLE consumed_nonce(tenant TEXT NOT NULL, nonce TEXT NOT NULL, PRIMARY KEY(tenant,nonce))")
        self.claims = dict(tenant_id="tenant-A", principal_id="p1", event_id="e1",
                           resource_id="opaque:001", twin_revision="r1",
                           evidence_digest=hashlib.sha256(b"synthetic").hexdigest(),
                           policy_version="policy1", approval_id="a1")
        self.keys = {"backend-issuer": KEY}
    def tearDown(self):
        self.db.close()
    def run_gate(self, claims=None, expected=None, nonce="nonce-1", mac=None, keys=None):
        claims = self.claims if claims is None else claims
        return verify_bind_and_consume(self.db, claims, sign_claims(claims) if mac is None else mac,
                                       "backend-issuer", self.keys if keys is None else keys,
                                       self.claims if expected is None else expected, nonce)
    def rows(self):
        return self.db.execute("SELECT tenant,nonce FROM consumed_nonce ORDER BY tenant,nonce").fetchall()
    def test_valid_consumes_once_and_replay_denied(self):
        self.assertTrue(self.run_gate())
        self.assertFalse(self.run_gate())
        self.assertEqual(self.rows(), [("tenant-A", "nonce-1")])
        self.assertFalse(self.db.in_transaction)
    def test_signed_foreign_tenant_cannot_consume_nonce(self):
        self.assertFalse(self.run_gate(claims=dict(self.claims, tenant_id="tenant-B")))
        self.assertEqual(self.rows(), [])
    def test_signed_foreign_resource_cannot_consume_nonce(self):
        self.assertFalse(self.run_gate(claims=dict(self.claims, resource_id="opaque:other")))
        self.assertEqual(self.rows(), [])
    def test_signed_foreign_digest_cannot_consume_nonce(self):
        self.assertFalse(self.run_gate(claims=dict(self.claims, evidence_digest="0"*64)))
        self.assertEqual(self.rows(), [])
    def test_revoked_key_cannot_consume_nonce(self):
        self.assertFalse(self.run_gate(keys={}))
        self.assertEqual(self.rows(), [])
    def test_invalid_nonce_does_not_mutate_and_valid_recovers(self):
        for nonce in ("", "bad\nnonce", "bad/nonce", "x"*129, "\u200b"):
            self.assertFalse(self.run_gate(nonce=nonce))
        self.assertEqual(self.rows(), [])
        self.assertTrue(self.run_gate())
    def test_sqlite_abort_rolls_back_then_recovers(self):
        self.db.execute("CREATE TRIGGER abort_nonce BEFORE INSERT ON consumed_nonce BEGIN SELECT RAISE(ABORT,'synthetic fault'); END")
        self.assertFalse(self.run_gate())
        self.assertEqual(self.rows(), [])
        self.assertFalse(self.db.in_transaction)
        self.db.execute("DROP TRIGGER abort_nonce")
        self.assertTrue(self.run_gate())
    def test_existing_transaction_is_not_mutated(self):
        self.db.execute("BEGIN")
        self.assertFalse(self.run_gate())
        self.assertEqual(self.rows(), [])
        self.assertTrue(self.db.in_transaction)
        self.db.rollback()
        self.assertTrue(self.run_gate())

if __name__ == "__main__":
    unittest.main()
