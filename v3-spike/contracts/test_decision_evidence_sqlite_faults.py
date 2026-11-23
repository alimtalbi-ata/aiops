"""SQLite failure-injection gates for synthetic DecisionEvidence; no production authorization."""
import hashlib
import sqlite3
import unittest

from decision_evidence_synthetic import sign_fixture, verify_and_consume

KEY = b"synthetic-only-test-key-not-for-production-123456"
DIGEST = hashlib.sha256(b"synthetic proof").hexdigest()

class DecisionEvidenceSQLiteFaults(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:", isolation_level=None)
        self.db.execute("CREATE TABLE consumed_nonces (issuer_key_id TEXT NOT NULL, tenant_id TEXT NOT NULL, nonce TEXT NOT NULL, PRIMARY KEY(issuer_key_id, tenant_id, nonce))")
        self.env = dict(schema_version="v1-synthetic", tenant_id="tenant-A", principal_id="principal-1", event_id="event-1", resource_id="opaque-1", twin_revision="rev-1", evidence_digest=DIGEST, policy_version="policy-1", decision="SIMULATE_ONLY", approval_id="approval-1", issued_at=1000, expires_at=1100, nonce="nonce-1", issuer_key_id="fixture-key")
        self.backend = {k: self.env[k] for k in ("tenant_id", "principal_id", "event_id", "resource_id", "twin_revision", "evidence_digest", "policy_version", "approval_id")}
    def tearDown(self):
        self.db.close()
    def verify(self, keys=None, mac=None):
        return verify_and_consume(self.db, envelope=self.env, backend=self.backend,
            mac=sign_fixture(self.env, KEY) if mac is None else mac,
            trusted_keys={"fixture-key": KEY} if keys is None else keys, now=1001)
    def assert_clean_deny(self):
        before = self.db.total_changes
        result = self.verify()
        self.assertEqual(result["decision"], "DENY", result)
        self.assertEqual(self.db.total_changes, before)
        self.assertFalse(self.db.in_transaction)
        self.assertEqual(self.db.execute("SELECT count(*) FROM consumed_nonces").fetchone()[0], 0)
    def test_abort_trigger_rolls_back_nonce(self):
        self.db.execute("CREATE TRIGGER abort_nonce BEFORE INSERT ON consumed_nonces BEGIN SELECT RAISE(ABORT, 'synthetic fault'); END")
        self.assert_clean_deny()
        self.db.execute("DROP TRIGGER abort_nonce")
        self.assertEqual(self.verify()["decision"], "SIMULATE_ONLY")
    def test_unique_conflict_preserves_original_nonce(self):
        self.assertEqual(self.verify()["decision"], "SIMULATE_ONLY")
        before = self.db.total_changes
        result = self.verify()
        self.assertEqual(result["decision"], "DENY")
        self.assertEqual(self.db.total_changes, before)
        self.assertEqual(self.db.execute("SELECT count(*) FROM consumed_nonces").fetchone()[0], 1)
        self.assertFalse(self.db.in_transaction)
    def test_check_constraint_rejects_and_rolls_back(self):
        self.db.execute("DROP TABLE consumed_nonces")
        self.db.execute("CREATE TABLE consumed_nonces (issuer_key_id TEXT, tenant_id TEXT, nonce TEXT CHECK(nonce != 'nonce-1'), PRIMARY KEY(issuer_key_id, tenant_id, nonce))")
        self.assert_clean_deny()
    def test_invalid_key_type_never_writes(self):
        before = self.db.total_changes
        result = self.verify(keys={"fixture-key": "not-bytes"})
        self.assertEqual(result, {"decision": "DENY", "reason": "key"})
        self.assertEqual(self.db.total_changes, before)
        self.assertFalse(self.db.in_transaction)
    def test_boolean_clock_rejected_before_transaction(self):
        before = self.db.total_changes
        result = verify_and_consume(self.db, envelope=self.env, backend=self.backend,
            mac=sign_fixture(self.env, KEY), trusted_keys={"fixture-key": KEY}, now=True)
        self.assertEqual(result, {"decision": "DENY", "reason": "clock"})
        self.assertEqual(self.db.total_changes, before)
        self.assertFalse(self.db.in_transaction)

    def test_after_insert_abort_rolls_back_nonce(self):
        self.db.execute("CREATE TRIGGER abort_after AFTER INSERT ON consumed_nonces BEGIN SELECT RAISE(ABORT, 'synthetic after-insert fault'); END")
        self.assert_clean_deny()
        self.db.execute("DROP TRIGGER abort_after")
        self.assertEqual(self.verify()["decision"], "SIMULATE_ONLY")
        self.assertEqual(self.db.execute("SELECT count(*) FROM consumed_nonces").fetchone()[0], 1)
    def test_missing_nonce_table_fails_closed_then_recovers(self):
        self.db.execute("DROP TABLE consumed_nonces")
        before = self.db.total_changes
        result = self.verify()
        self.assertEqual(result["decision"], "DENY")
        self.assertEqual(self.db.total_changes, before)
        self.assertFalse(self.db.in_transaction)
        self.db.execute("CREATE TABLE consumed_nonces (issuer_key_id TEXT NOT NULL, tenant_id TEXT NOT NULL, nonce TEXT NOT NULL, PRIMARY KEY(issuer_key_id,tenant_id,nonce))")
        self.assertEqual(self.verify()["decision"], "SIMULATE_ONLY")
    def test_null_nonce_constraint_fails_closed_then_recovers(self):
        self.db.execute("DROP TABLE consumed_nonces")
        self.db.execute("CREATE TABLE consumed_nonces (issuer_key_id TEXT NOT NULL, tenant_id TEXT NOT NULL, nonce TEXT NOT NULL CHECK(nonce != 'nonce-1'), PRIMARY KEY(issuer_key_id,tenant_id,nonce))")
        self.assert_clean_deny()
        self.db.execute("DROP TABLE consumed_nonces")
        self.db.execute("CREATE TABLE consumed_nonces (issuer_key_id TEXT NOT NULL, tenant_id TEXT NOT NULL, nonce TEXT NOT NULL, PRIMARY KEY(issuer_key_id,tenant_id,nonce))")
        self.assertEqual(self.verify()["decision"], "SIMULATE_ONLY")


    def test_query_only_connection_denies_then_recovers(self):
        self.db.execute("PRAGMA query_only=ON")
        try:
            self.assert_clean_deny()
        finally:
            self.db.execute("PRAGMA query_only=OFF")
        self.assertEqual(self.verify()["decision"], "SIMULATE_ONLY")
        self.assertEqual(self.db.execute("SELECT count(*) FROM consumed_nonces").fetchone()[0], 1)

    def test_sqlite_authorizer_denies_insert_then_recovers(self):
        def authorizer(action, arg1, arg2, database, trigger):
            if action == sqlite3.SQLITE_INSERT and arg1 == "consumed_nonces":
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        self.db.set_authorizer(authorizer)
        try:
            self.assert_clean_deny()
        finally:
            self.db.set_authorizer(None)
        self.assertEqual(self.verify()["decision"], "SIMULATE_ONLY")
        self.assertEqual(self.db.execute("SELECT count(*) FROM consumed_nonces").fetchone()[0], 1)

    def test_deferred_foreign_key_commit_failure_rolls_back(self):
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("CREATE TABLE synthetic_parent (id INTEGER PRIMARY KEY)")
        self.db.execute("DROP TABLE consumed_nonces")
        self.db.execute("CREATE TABLE consumed_nonces (issuer_key_id TEXT NOT NULL, tenant_id TEXT NOT NULL, nonce TEXT NOT NULL, parent_id INTEGER NOT NULL DEFAULT 999 REFERENCES synthetic_parent(id) DEFERRABLE INITIALLY DEFERRED, PRIMARY KEY(issuer_key_id,tenant_id,nonce))")
        # SQLite total_changes counts attempted writes even after rollback.
        # Assert durable state instead of total_changes for deferred commit failure.
        result = self.verify()
        self.assertEqual(result["decision"], "DENY")
        self.assertFalse(self.db.in_transaction)
        self.assertEqual(self.db.execute("SELECT count(*) FROM consumed_nonces").fetchone()[0], 0)
        self.db.execute("INSERT INTO synthetic_parent(id) VALUES (999)")
        self.assertEqual(self.verify()["decision"], "SIMULATE_ONLY")
        self.assertEqual(self.db.execute("SELECT count(*) FROM consumed_nonces").fetchone()[0], 1)

if __name__ == "__main__":
    unittest.main()
