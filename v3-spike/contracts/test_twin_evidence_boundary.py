"""Adversarial synthetic tests for immutable Twin/Evidence boundary."""
import dataclasses
import hashlib
import sqlite3
import unittest
from twin_evidence_boundary import correlate, TwinEvidenceView

SCHEMA = """CREATE TABLE acl(tenant TEXT,principal TEXT,allowed INTEGER);
CREATE TABLE twin(tenant TEXT,instance TEXT,revision TEXT,payload TEXT);
CREATE TABLE evidence(tenant TEXT,instance TEXT,event TEXT,revision TEXT,digest TEXT,payload TEXT);"""

class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:", isolation_level=None)
        self.db.executescript(SCHEMA)
        self.db.execute("INSERT INTO acl VALUES (?,?,?)", ("a", "alice", 1))
        self.db.execute("INSERT INTO acl VALUES (?,?,?)", ("b", "alice", 1))
        self.db.execute("INSERT INTO twin VALUES (?,?,?,?)", ("a", "opaque-1", "r1", "twin"))
        self.db.execute("INSERT INTO evidence VALUES (?,?,?,?,?,?)",
                        ("a", "opaque-1", "event-1", "r1", hashlib.sha256(b"proof").hexdigest(), "proof"))
        self.kw = dict(tenant="a", instance="opaque-1", principal="alice",
                       event="event-1", revision="r1", evidence_sha256=hashlib.sha256(b"proof").hexdigest())
    def tearDown(self):
        self.db.close()
    def decide(self, **kw):
        return correlate(self.db, **(self.kw | kw))
    def test_valid_simulation(self):
        r = self.decide()
        self.assertEqual(r["decision"], "SIMULATE_ONLY")
        self.assertFalse(r["production_authorized"])
        self.assertFalse(self.db.in_transaction)
    def test_cross_tenant(self):
        self.assertEqual(self.decide(tenant="b")["decision"], "DENY")
    def test_opaque_instance(self):
        self.assertEqual(self.decide(instance="opaque-2")["decision"], "DENY")
    def test_wrong_event(self):
        self.assertEqual(self.decide(event="event-2")["decision"], "DENY")
    def test_revision(self):
        self.assertEqual(self.decide(revision="r2")["decision"], "DENY")
    def test_digest(self):
        self.assertEqual(self.decide(evidence_sha256="0"*64)["decision"], "DENY")
    def test_mutated_evidence(self):
        self.db.execute("UPDATE evidence SET payload='changed'")
        self.assertEqual(self.decide()["decision"], "DENY")
    def test_revocation(self):
        self.db.execute("UPDATE acl SET allowed=0")
        self.assertEqual(self.decide()["decision"], "DENY")
    def test_frozen_view(self):
        def check(v):
            self.assertIsInstance(v, TwinEvidenceView)
            with self.assertRaises(dataclasses.FrozenInstanceError):
                v.tenant = "b"
            self.assertFalse(hasattr(v, "execute"))
            return True
        check(TwinEvidenceView("a", "opaque-1", "event-1", "r1", "twin", "proof", self.kw["evidence_sha256"]))
        self.assertEqual(self.decide(inspect=check)["decision"], "DENY")
    def test_nonboolean_inspection(self):
        self.assertEqual(self.decide(inspect=lambda v: "true")["decision"], "DENY")
    def test_exception_rolls_back(self):
        def bad(v):
            raise RuntimeError("synthetic")
        self.assertEqual(self.decide(inspect=bad)["decision"], "DENY")
        self.assertFalse(self.db.in_transaction)
    def test_authorizer_bypass_no_raw_handle(self):
        def bypass(v):
            v.set_authorizer(None)
            return True
        self.assertEqual(self.decide(inspect=bypass)["decision"], "DENY")
    def test_closure_cannot_disable_authorizer(self):
        called = []
        def malicious(_view):
            called.append(True)
            self.db.set_authorizer(None)
            self.db.execute("CREATE TABLE injected(secret TEXT)")
            return True
        result = self.decide(inspect=malicious)
        self.assertEqual(result, {"decision": "DENY", "reason": "untrusted_inspector"})
        self.assertEqual(called, [])
        self.assertIsNone(self.db.execute(
            "SELECT name FROM sqlite_master WHERE name='injected'").fetchone())
        self.assertFalse(self.db.in_transaction)
    def test_closure_cannot_revoke_acl(self):
        def malicious(_view):
            self.db.execute("UPDATE acl SET allowed=0 WHERE tenant='a'")
            return True
        self.assertEqual(self.decide(inspect=malicious)["decision"], "DENY")
        self.assertEqual(self.db.execute(
            "SELECT allowed FROM acl WHERE tenant='a' AND principal='alice'").fetchone(), (1,))
    def test_callback_never_invoked_even_if_benign(self):
        invoked = []
        self.assertEqual(self.decide(inspect=lambda v: invoked.append(v) or True)["decision"], "DENY")
        self.assertEqual(invoked, [])
        self.assertEqual(self.decide()["decision"], "SIMULATE_ONLY")
    def test_duplicate_acl_denied_even_when_first_allows(self):
        self.db.execute("INSERT INTO acl VALUES (?,?,?)", ("a", "alice", 1))
        self.assertEqual(self.decide()["reason"], "ambiguous_backend_rows")
        self.assertFalse(self.db.in_transaction)
    def test_duplicate_twin_denied_even_when_first_matches(self):
        self.db.execute("INSERT INTO twin VALUES (?,?,?,?)", ("a", "opaque-1", "r1", "twin"))
        self.assertEqual(self.decide()["reason"], "ambiguous_backend_rows")
        self.assertFalse(self.db.in_transaction)
    def test_duplicate_evidence_denied_even_when_first_matches(self):
        self.db.execute("INSERT INTO evidence VALUES (?,?,?,?,?,?)",
                        ("a", "opaque-1", "event-1", "r1", self.kw["evidence_sha256"], "proof"))
        self.assertEqual(self.decide()["reason"], "ambiguous_backend_rows")
        self.assertFalse(self.db.in_transaction)
    def test_conflicting_acl_denied_regardless_of_row_order(self):
        self.db.execute("INSERT INTO acl VALUES (?,?,?)", ("a", "alice", 0))
        self.assertEqual(self.decide()["decision"], "DENY")
    def test_deterministic_correlation(self):
        self.assertEqual(self.decide()["correlation"], self.decide()["correlation"])
    def test_invalid_input(self):
        self.assertEqual(self.decide(principal="")["decision"], "DENY")
    def test_existing_transaction_not_mutated(self):
        self.db.execute("BEGIN")
        try:
            self.assertEqual(self.decide()["decision"], "DENY")
            self.assertTrue(self.db.in_transaction)
        finally:
            self.db.rollback()

if __name__ == "__main__":
    unittest.main()
