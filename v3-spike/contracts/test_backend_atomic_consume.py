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
    try:
        if db.in_transaction:
            return False
        db.execute("BEGIN IMMEDIATE")
        db.execute("INSERT INTO consumed_nonce(tenant,nonce) VALUES (?,?)", (bound["tenant_id"], nonce))
        db.commit()
        return True
    except sqlite3.Error:
        try:
            if db.in_transaction:
                db.rollback()
        except sqlite3.Error:
            pass
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
    def test_closed_connection_fails_closed_without_crash(self):
        self.db.close()
        self.assertFalse(self.run_gate())

    def test_missing_nonce_table_fails_closed_then_recovers(self):
        self.db.execute("DROP TABLE consumed_nonce")
        self.assertFalse(self.run_gate())
        self.assertFalse(self.db.in_transaction)
        self.db.execute("CREATE TABLE consumed_nonce(tenant TEXT NOT NULL, nonce TEXT NOT NULL, PRIMARY KEY(tenant,nonce))")
        self.assertTrue(self.run_gate())

    def test_commit_failure_rolls_back_and_recovers(self):
        self.db.execute("CREATE TABLE parent(id INTEGER PRIMARY KEY)")
        self.db.execute("CREATE TABLE child(parent_id INTEGER REFERENCES parent(id) DEFERRABLE INITIALLY DEFERRED)")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("CREATE TRIGGER defer_fault AFTER INSERT ON consumed_nonce BEGIN INSERT INTO child(parent_id) VALUES (999); END")
        self.assertFalse(self.run_gate())
        self.assertEqual(self.rows(), [])
        self.assertFalse(self.db.in_transaction)
        self.db.execute("DROP TRIGGER defer_fault")
        self.assertTrue(self.run_gate())

    def test_same_nonce_different_tenant_isolated(self):
        self.assertTrue(self.run_gate())
        foreign = dict(self.claims, tenant_id="tenant-B")
        self.assertTrue(self.run_gate(claims=foreign, expected=foreign))
        self.assertEqual(self.rows(), [("tenant-A", "nonce-1"), ("tenant-B", "nonce-1")])

    def test_existing_transaction_is_not_mutated(self):
        self.db.execute("BEGIN")
        self.assertFalse(self.run_gate())
        self.assertEqual(self.rows(), [])
        self.assertTrue(self.db.in_transaction)
        self.db.rollback()
        self.assertTrue(self.run_gate())


    def test_two_connections_writer_lock_denies_without_partial_nonce(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory(prefix="v3-b-lock-") as temp:
            path = str(Path(temp) / "nonces.sqlite")
            with sqlite3.connect(path, timeout=0, isolation_level=None) as setup:
                setup.execute("CREATE TABLE consumed_nonce(tenant TEXT NOT NULL, nonce TEXT NOT NULL, PRIMARY KEY(tenant,nonce))")
            writer = sqlite3.connect(path, timeout=0, isolation_level=None)
            contender = sqlite3.connect(path, timeout=0, isolation_level=None)
            try:
                writer.execute("BEGIN IMMEDIATE")
                writer.execute("INSERT INTO consumed_nonce VALUES (?,?)", ("tenant-A", "held"))
                self.assertFalse(verify_bind_and_consume(
                    contender, self.claims, sign_claims(self.claims),
                    "backend-issuer", self.keys, self.claims, "retry"))
                self.assertFalse(contender.in_transaction)
                self.assertEqual(writer.execute("SELECT nonce FROM consumed_nonce").fetchall(), [("held",)])
                writer.commit()
                self.assertEqual(contender.execute("SELECT nonce FROM consumed_nonce ORDER BY nonce").fetchall(), [("held",)])
                self.assertTrue(verify_bind_and_consume(
                    contender, self.claims, sign_claims(self.claims),
                    "backend-issuer", self.keys, self.claims, "retry"))
                self.assertEqual(contender.execute("SELECT nonce FROM consumed_nonce ORDER BY nonce").fetchall(),
                                 [("held",), ("retry",)])
            finally:
                writer.close()
                contender.close()

    def test_cross_connection_replay_denied_after_commit(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory(prefix="v3-b-replay-") as temp:
            path = str(Path(temp) / "nonces.sqlite")
            first = sqlite3.connect(path, timeout=0, isolation_level=None)
            second = sqlite3.connect(path, timeout=0, isolation_level=None)
            try:
                first.execute("CREATE TABLE consumed_nonce(tenant TEXT NOT NULL, nonce TEXT NOT NULL, PRIMARY KEY(tenant,nonce))")
                args = (self.claims, sign_claims(self.claims), "backend-issuer",
                        self.keys, self.claims, "shared")
                self.assertTrue(verify_bind_and_consume(first, *args))
                self.assertFalse(verify_bind_and_consume(second, *args))
                self.assertFalse(second.in_transaction)
                self.assertEqual(second.execute("SELECT tenant,nonce FROM consumed_nonce").fetchall(),
                                 [("tenant-A", "shared")])
            finally:
                first.close()
                second.close()

    def test_sqlite_query_only_denies_without_nonce_and_recovers(self):
        self.db.execute("PRAGMA query_only=ON")
        self.assertFalse(self.run_gate(nonce="readonly"))
        self.assertFalse(self.db.in_transaction)
        self.db.execute("PRAGMA query_only=OFF")
        self.assertEqual(self.rows(), [])
        self.assertTrue(self.run_gate(nonce="readonly"))

    def test_sqlite_authorizer_denies_insert_then_recovers(self):
        def deny_insert(action, arg1, arg2, dbname, source):
            return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_INSERT and arg1 == "consumed_nonce" else sqlite3.SQLITE_OK
        self.db.set_authorizer(deny_insert)
        try:
            self.assertFalse(self.run_gate(nonce="authorizer"))
            self.assertFalse(self.db.in_transaction)
        finally:
            self.db.set_authorizer(None)
        self.assertEqual(self.rows(), [])
        self.assertTrue(self.run_gate(nonce="authorizer"))

    def test_untrusted_expected_context_cannot_redirect_nonce(self):
        foreign = dict(self.claims, tenant_id="tenant-B", resource_id="opaque:foreign")
        self.assertFalse(self.run_gate(expected=foreign, nonce="redirect"))
        self.assertEqual(self.rows(), [])
        self.assertTrue(self.run_gate(nonce="redirect"))
        self.assertEqual(self.rows(), [("tenant-A", "redirect")])

    def test_malformed_mac_and_opaque_resource_fail_without_nonce(self):
        for mac in ("0" * 64, "not-a-mac", b"bad", 17):
            with self.subTest(mac=mac):
                self.assertFalse(self.run_gate(mac=mac, nonce="opaque"))
        changed = dict(self.claims, resource_id="opaque:001' OR 1=1 --")
        self.assertFalse(self.run_gate(claims=changed, nonce="opaque"))
        self.assertEqual(self.rows(), [])
        self.assertTrue(self.run_gate(nonce="opaque"))

if __name__ == "__main__":
    unittest.main()
