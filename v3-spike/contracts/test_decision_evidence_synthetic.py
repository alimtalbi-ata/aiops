"""Adversarial tests for synthetic DecisionEvidence trust boundary."""
import copy
import hashlib
import sqlite3
import tempfile
import threading
import unittest
from decision_evidence_synthetic import sign_fixture, verify_and_consume

KEY = b"synthetic-only-test-key-not-for-production-123456"
DIGEST = hashlib.sha256(b"synthetic proof").hexdigest()

class DecisionEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:", isolation_level=None)
        self.db.execute("CREATE TABLE consumed_nonces(issuer_key_id TEXT NOT NULL, tenant_id TEXT NOT NULL, nonce TEXT NOT NULL, PRIMARY KEY(issuer_key_id,tenant_id,nonce))")
        self.env = dict(schema_version="v1-synthetic", tenant_id="tenant-A", principal_id="principal-1",
                        event_id="event-1", resource_id="opaque-1", twin_revision="rev-1",
                        evidence_digest=DIGEST, policy_version="policy-1", decision="SIMULATE_ONLY",
                        approval_id="approval-1", issued_at=1000, expires_at=1100,
                        nonce="nonce-1", issuer_key_id="fixture-key")
        self.backend = {k:self.env[k] for k in ("tenant_id","principal_id","event_id","resource_id",
                        "twin_revision","evidence_digest","policy_version","approval_id")}
        self.keys = {"fixture-key":KEY}
    def tearDown(self):
        self.db.close()
    def check(self, env=None, mac=None, backend=None, db=None, now=1001, keys=None):
        e = self.env if env is None else env
        return verify_and_consume(self.db if db is None else db, envelope=e,
                                  mac=sign_fixture(e, KEY) if mac is None else mac,
                                  backend=self.backend if backend is None else backend,
                                  trusted_keys=self.keys if keys is None else keys, now=now)
    def deny_swap(self, field, value):
        e = dict(self.env, **{field:value})
        self.assertEqual(self.check(e)["decision"], "DENY")
        self.assertEqual(self.db.execute("SELECT count(*) FROM consumed_nonces").fetchone()[0], 0)
    def test_valid_single_use(self):
        self.assertEqual(self.check()["decision"], "SIMULATE_ONLY")
        self.assertEqual(self.check()["decision"], "DENY")
        self.assertFalse(self.db.in_transaction)
    def test_cross_tenant(self): self.deny_swap("tenant_id", "tenant-B")
    def test_principal_swap(self): self.deny_swap("principal_id", "attacker")
    def test_event_swap(self): self.deny_swap("event_id", "other-event")
    def test_opaque_resource_swap(self): self.deny_swap("resource_id", "opaque-2")
    def test_stale_twin(self): self.deny_swap("twin_revision", "rev-0")
    def test_digest_swap(self): self.deny_swap("evidence_digest", "0"*64)
    def test_policy_swap(self): self.deny_swap("policy_version", "policy-2")
    def test_approval_swap(self): self.deny_swap("approval_id", "approval-2")
    def test_forged_mac(self): self.assertEqual(self.check(mac="0"*64)["decision"], "DENY")
    def test_unknown_key(self): self.assertEqual(self.check(keys={})["decision"], "DENY")
    def test_expired(self): self.assertEqual(self.check(now=1100)["decision"], "DENY")
    def test_future(self): self.assertEqual(self.check(now=999)["decision"], "DENY")
    def test_overlong_validity(self):
        self.assertEqual(self.check(dict(self.env, expires_at=1400))["decision"], "DENY")
    def test_untrusted_production_allow(self):
        self.assertEqual(self.check(dict(self.env, decision="ALLOW"))["decision"], "DENY")
    def test_missing_field(self):
        e = dict(self.env); del e["nonce"]
        self.assertEqual(self.check(e, mac="0"*64)["decision"], "DENY")
    def test_extra_field(self):
        self.assertEqual(self.check(dict(self.env, extra="x"), mac="0"*64)["decision"], "DENY")
    def test_existing_transaction_nonmutation(self):
        self.db.execute("BEGIN")
        try:
            self.assertEqual(self.check()["decision"], "DENY")
            self.assertTrue(self.db.in_transaction)
        finally:
            self.db.rollback()
    def test_atomic_race_two_connections(self):
        with tempfile.TemporaryDirectory() as folder:
            path = folder + "/nonces.sqlite"
            seed = sqlite3.connect(path)
            seed.execute("CREATE TABLE consumed_nonces(issuer_key_id TEXT NOT NULL, tenant_id TEXT NOT NULL, nonce TEXT NOT NULL, PRIMARY KEY(issuer_key_id,tenant_id,nonce))")
            seed.commit(); seed.close()
            barrier = threading.Barrier(2)
            results = []
            def worker():
                db = sqlite3.connect(path, isolation_level=None, timeout=3)
                try:
                    barrier.wait(timeout=3)
                    results.append(self.check(db=db)["decision"])
                finally: db.close()
            threads = [threading.Thread(target=worker) for _ in range(2)]
            for t in threads: t.start()
            for t in threads: t.join(timeout=5)
            self.assertTrue(all(not t.is_alive() for t in threads))
            self.assertCountEqual(results, ["SIMULATE_ONLY","DENY"])
            verify = sqlite3.connect(path)
            self.assertEqual(verify.execute("SELECT count(*) FROM consumed_nonces").fetchone()[0], 1)
            verify.close()

if __name__ == "__main__":
    unittest.main()
