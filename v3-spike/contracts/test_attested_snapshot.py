"""Synthetic negative controls for independently witnessed snapshot boundary."""
import hashlib
import hmac
import json
import unittest
from dataclasses import replace
from unittest.mock import Mock
from secure_boundary import AssertionVerifier
from resource_binding import Resource
from snapshot_pair import SnapshotPair
from attested_snapshot import AttestedPair, SyntheticIndependentWitness, attested_snapshot_decision


class AttestedSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.auth_key = b"synthetic-auth-key-32-bytes-long!!!"
        self.witness = SyntheticIndependentWitness(b"independent-witness-key-32-bytes!!")
        self.verifier = AssertionVerifier(self.auth_key, clock=lambda: 1000)
        digest = hashlib.sha256(b"synthetic-event").hexdigest()
        self.event = dict(tenant="tenant-a", instance="instance-a", event="event1",
                          digest=digest, twin_identifier="twin1",
                          evidence_identifier="evidence1", snapshot_id="rev1")
        twin = Resource("twin", "tenant-a", "instance-a", "twin1", "event1", digest)
        evidence = Resource("evidence", "tenant-a", "instance-a", "evidence1", "event1", digest)
        self.pair = SnapshotPair("rev1", twin, evidence)
        self.state = {"writes": 0, "revision": "rev1"}

    def token(self, tenant="tenant-a", permissions=("twin:read", "evidence:read")):
        raw = json.dumps(dict(tenant=tenant, instance="instance-a",
                              permissions=list(permissions), exp=1100), sort_keys=True).encode()
        return raw.hex() + "." + hmac.new(self.auth_key, raw, hashlib.sha256).hexdigest()

    _AUTO_RECEIPT = object()

    def response(self, twin_rev="rev1", evidence_rev="rev1", receipt=_AUTO_RECEIPT, pair=None):
        return AttestedPair(self.pair if pair is None else pair, twin_rev, evidence_rev,
                            self.witness.issue_fixture_receipt(self.event, twin_rev)
                            if receipt is self._AUTO_RECEIPT else receipt)

    def decide(self, response=None, event=None, token=None, backend=None):
        before = dict(self.state)
        fetch = backend if backend is not None else Mock(return_value=response)
        result = attested_snapshot_decision(event=self.event if event is None else event,
                   assertion=self.token() if token is None else token,
                   verifier=self.verifier, fetch_pair=fetch, witness=self.witness)
        self.assertEqual(before, self.state, "fixture backend mutated")
        return result, fetch

    def test_valid_independently_witnessed_fixture_is_only_synthetic(self):
        result, fetch = self.decide(self.response())
        self.assertEqual(result, "ALLOW_SYNTHETIC")
        fetch.assert_called_once()
        self.assertNotEqual(result, "ALLOW")

    def test_unwitnessed_backend_same_label_denied(self):
        result, _ = self.decide(self.pair)
        self.assertEqual(result, "DENY")

    def test_interleaved_r1_r2_with_valid_r1_receipt_denied(self):
        result, _ = self.decide(self.response(evidence_rev="rev2"))
        self.assertEqual(result, "DENY")

    def test_backend_forged_or_missing_receipt_denied(self):
        for receipt in ("0" * 64, "", "f" * 64, "é" * 64, None):
            with self.subTest(receipt=repr(receipt)):
                result, _ = self.decide(self.response(receipt=receipt))
                self.assertEqual(result, "DENY")

    def test_replay_receipt_across_event_or_tenant_denied(self):
        for field, value in (("event", "event2"), ("tenant", "tenant-b"),
                             ("digest", "a" * 64), ("twin_identifier", "other")):
            changed = dict(self.event, **{field: value})
            result, _ = self.decide(self.response(), event=changed)
            self.assertEqual(result, "DENY")

    def test_acl_rejection_precedes_backend_call(self):
        for token in (self.token(tenant="tenant-b"),
                      self.token(permissions=("twin:read",)), "malformed"):
            result, backend = self.decide(token=token, backend=Mock())
            self.assertEqual(result, "DENY")
            backend.assert_not_called()

    def test_resource_swap_denied_even_with_valid_receipt(self):
        changed = replace(self.pair.twin, tenant="tenant-b")
        result, _ = self.decide(self.response(pair=SnapshotPair("rev1", changed, self.pair.evidence)))
        self.assertEqual(result, "DENY")

    def test_backend_revocation_during_fetch_denied(self):
        result, fetch = self.decide(backend=Mock(side_effect=PermissionError("revoked")))
        self.assertEqual(result, "DENY")
        fetch.assert_called_once()

    def test_malformed_identifier_denied_before_fetch(self):
        for bad in ("../rev1", "rév1", None, "x" * 129):
            result, backend = self.decide(event=dict(self.event, snapshot_id=bad), backend=Mock())
            self.assertEqual(result, "DENY")
            backend.assert_not_called()


    def test_backend_side_effect_is_detected_by_instrumented_oracle(self):
        def malicious_backend(**kwargs):
            self.state["writes"] += 1
            self.state["revision"] = "rev2"
            return self.response()
        with self.assertRaisesRegex(AssertionError, "fixture backend mutated"):
            self.decide(backend=malicious_backend)

    def test_backend_with_stolen_witness_key_cannot_grant_real_allow(self):
        # Demonstrates trust-boundary limitation: a compromised witness can
        # forge a synthetic receipt. This must never become production ALLOW.
        stolen_key = self.witness._key
        forged = hmac.new(stolen_key, __import__("attested_snapshot")._message(
            self.event, "rev1"), hashlib.sha256).hexdigest()
        result, _ = self.decide(self.response(receipt=forged))
        self.assertEqual(result, "ALLOW_SYNTHETIC")
        self.assertNotEqual(result, "ALLOW")

    def test_witness_rejects_receipt_for_other_snapshot_revision(self):
        other_event = dict(self.event, snapshot_id="rev2")
        receipt = self.witness.issue_fixture_receipt(other_event, "rev2")
        result, _ = self.decide(self.response(receipt=receipt))
        self.assertEqual(result, "DENY")


if __name__ == "__main__":
    unittest.main(verbosity=2)
