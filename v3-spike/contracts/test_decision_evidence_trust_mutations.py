"""Independent synthetic trust-boundary mutations; no production authorization."""
import hashlib
import sqlite3
import unittest

from decision_evidence_synthetic import sign_fixture, verify_and_consume

KEY = b"synthetic-only-test-key-not-for-production-123456"
DIGEST = hashlib.sha256(b"synthetic proof").hexdigest()
BOUND = ("tenant_id", "principal_id", "event_id", "resource_id",
         "twin_revision", "evidence_digest", "policy_version", "approval_id")


class DecisionEvidenceTrustMutations(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:", isolation_level=None)
        self.db.execute("CREATE TABLE consumed_nonces (issuer_key_id TEXT NOT NULL, tenant_id TEXT NOT NULL, nonce TEXT NOT NULL, PRIMARY KEY(issuer_key_id,tenant_id,nonce))")
        self.env = dict(schema_version="v1-synthetic", tenant_id="tenant-A",
                        principal_id="principal-1", event_id="event-1",
                        resource_id="opaque-1", twin_revision="rev-1",
                        evidence_digest=DIGEST, policy_version="policy-1",
                        decision="SIMULATE_ONLY", approval_id="approval-1",
                        issued_at=1000, expires_at=1100, nonce="nonce-1",
                        issuer_key_id="fixture-key")
        self.backend = {f: self.env[f] for f in BOUND}

    def tearDown(self):
        self.db.close()

    def verify(self, env, backend=None, mac=None):
        return verify_and_consume(
            self.db, envelope=env, backend=self.backend if backend is None else backend,
            mac=sign_fixture(env, KEY) if mac is None else mac,
            trusted_keys={"fixture-key": KEY}, now=1001)

    def assert_denied_unchanged(self, env, backend=None, mac=None):
        before = self.db.total_changes
        result = self.verify(env, backend=backend, mac=mac)
        self.assertEqual(result["decision"], "DENY", result)
        self.assertEqual(self.db.total_changes, before)
        self.assertEqual(self.db.execute("SELECT count(*) FROM consumed_nonces").fetchone()[0], 0)
        self.assertFalse(self.db.in_transaction)

    def test_signed_cross_tenant_with_lying_backend(self):
        env = dict(self.env, tenant_id="tenant-B")
        self.assert_denied_unchanged(env)

    def test_signed_resource_swap_with_lying_backend(self):
        env = dict(self.env, resource_id="opaque-other")
        self.assert_denied_unchanged(env)

    def test_signed_evidence_digest_swap(self):
        env = dict(self.env, evidence_digest="0"*64)
        self.assert_denied_unchanged(env)

    def test_signed_policy_revocation(self):
        env = dict(self.env, policy_version="revoked-policy")
        self.assert_denied_unchanged(env)

    def test_unsigned_approval_change(self):
        env = dict(self.env, approval_id="approval-attacker")
        self.assert_denied_unchanged(env, backend={**self.backend, "approval_id": env["approval_id"]},
                                     mac=sign_fixture(self.env, KEY))

    def test_nonce_not_consumed_on_bad_signature_then_valid(self):
        self.assert_denied_unchanged(self.env, mac="0"*64)
        self.assertEqual(self.verify(self.env)["decision"], "SIMULATE_ONLY")
        self.assertEqual(self.db.execute("SELECT count(*) FROM consumed_nonces").fetchone()[0], 1)

    def test_replay_does_not_consume_second_nonce(self):
        self.assertEqual(self.verify(self.env)["decision"], "SIMULATE_ONLY")
        before = self.db.total_changes
        self.assertEqual(self.verify(self.env)["decision"], "DENY")
        self.assertEqual(self.db.total_changes, before)
        self.assertEqual(self.db.execute("SELECT count(*) FROM consumed_nonces").fetchone()[0], 1)

    def test_backend_omits_principal(self):
        backend = dict(self.backend)
        del backend["principal_id"]
        self.assert_denied_unchanged(self.env, backend=backend)


if __name__ == "__main__":
    unittest.main()
