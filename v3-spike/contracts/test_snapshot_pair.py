"""Synthetic adversarial tests of the atomic pair adapter boundary."""
import hashlib
import hmac
import json
import unittest
from unittest.mock import Mock

from secure_boundary import AssertionVerifier
from resource_binding import Resource
from snapshot_pair import SnapshotPair, snapshot_pair_decision


class SnapshotPairTests(unittest.TestCase):
    def setUp(self):
        self.key = b"synthetic-verifier-key-32-bytes-long!"
        self.verifier = AssertionVerifier(self.key, clock=lambda: 1000)
        digest = hashlib.sha256(b"synthetic-payload").hexdigest()
        self.event = dict(tenant="demo-a", instance="collector-a", event="e1",
                          digest=digest, twin_identifier="ci1",
                          evidence_identifier="ev1", snapshot_id="rev1")
        self.twin = Resource("twin", "demo-a", "collector-a", "ci1", "e1", digest)
        self.evidence = Resource("evidence", "demo-a", "collector-a", "ev1", "e1", digest)
        self.rows = {"twin": self.twin, "evidence": self.evidence}
        self.fetch = Mock(return_value=SnapshotPair("rev1", self.twin, self.evidence))

    def token(self, tenant="demo-a", permissions=("twin:read", "evidence:read")):
        claims = dict(tenant=tenant, instance="collector-a",
                      permissions=list(permissions), exp=1100)
        payload = json.dumps(claims, sort_keys=True).encode()
        return payload.hex() + "." + hmac.new(self.key, payload, hashlib.sha256).hexdigest()

    def decide(self, event=None, token=None, fetch=None):
        return snapshot_pair_decision(
            event=self.event if event is None else event,
            assertion=self.token() if token is None else token,
            verifier=self.verifier, fetch_pair=self.fetch if fetch is None else fetch)

    def test_one_atomic_pair_call_and_synthetic_allow(self):
        self.assertEqual(self.decide(), "ALLOW_SYNTHETIC")
        self.fetch.assert_called_once_with(tenant="demo-a", instance="collector-a",
            twin_identifier="ci1", evidence_identifier="ev1", snapshot_id="rev1")

    def test_acl_and_invalid_ids_prevent_any_backend_call(self):
        for token in (self.token(tenant="demo-b"),
                      self.token(permissions=("twin:read",)), "malformed"):
            fetch = Mock()
            self.assertEqual(self.decide(token=token, fetch=fetch), "DENY")
            fetch.assert_not_called()
        for field, value in (("snapshot_id", "../rev"), ("twin_identifier", "é"),
                             ("evidence_identifier", None), ("digest", "X" * 64)):
            fetch = Mock()
            self.assertEqual(self.decide(event=dict(self.event, **{field: value}), fetch=fetch), "DENY")
            fetch.assert_not_called()

    def test_interleaved_revisions_deny_without_mutation(self):
        before = dict(self.rows)
        for response in (SnapshotPair("rev2", self.twin, self.evidence),
                         (SnapshotPair("rev1", self.twin, self.evidence),
                          SnapshotPair("rev2", self.twin, self.evidence)),
                         None):
            fetch = Mock(return_value=response)
            self.assertEqual(self.decide(fetch=fetch), "DENY")
            fetch.assert_called_once()
        self.assertEqual(before, self.rows)

    def test_backend_substitution_and_digest_deny(self):
        before = dict(self.rows)
        for pair in (
            SnapshotPair("rev1", Resource("twin", "demo-b", "collector-a", "ci1", "e1", self.event["digest"]), self.evidence),
            SnapshotPair("rev1", self.twin, Resource("evidence", "demo-a", "collector-a", "other", "e1", self.event["digest"])),
            SnapshotPair("rev1", self.twin, Resource("evidence", "demo-a", "collector-a", "ev1", "e1", "b" * 64)),
        ):
            self.assertEqual(self.decide(fetch=Mock(return_value=pair)), "DENY")
        self.assertEqual(before, self.rows)

    def test_untrusted_revision_label_not_sufficient_for_real_authorization(self):
        # An untrusted adapter can lie about a common revision. The synthetic
        # oracle cannot prove its transaction or signed attestation.
        self.assertEqual(self.decide(), "ALLOW_SYNTHETIC")
        self.assertNotEqual(self.decide(), "ALLOW")


if __name__ == "__main__":
    unittest.main(verbosity=2)
