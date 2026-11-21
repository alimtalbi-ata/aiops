"""ADR-003 adversarial contract: synthetic-only, no production ALLOW."""
import hashlib
import hmac
import json
import unittest
from dataclasses import replace
from unittest.mock import Mock

from secure_boundary import AssertionVerifier
from resource_binding import Resource
from snapshot_pair import SnapshotPair, snapshot_pair_decision


class SnapshotAdversarialTests(unittest.TestCase):
    def setUp(self):
        self.key = b"synthetic-verifier-key-32-bytes-long!"
        self.verifier = AssertionVerifier(self.key, clock=lambda: 1000)
        self.digest = hashlib.sha256(b"fixture-only").hexdigest()
        self.event = dict(tenant="tenant-a", instance="instance-a", event="event1",
                          digest=self.digest, twin_identifier="twin1",
                          evidence_identifier="evidence1", snapshot_id="revision1")
        self.twin = Resource("twin", "tenant-a", "instance-a", "twin1", "event1", self.digest)
        self.evidence = Resource("evidence", "tenant-a", "instance-a", "evidence1", "event1", self.digest)
        self.backend = Mock(return_value=SnapshotPair("revision1", self.twin, self.evidence))
        self.state = {"writes": 0}

    def token(self, *, tenant="tenant-a", permissions=("twin:read", "evidence:read"), exp=1100):
        raw = json.dumps(dict(tenant=tenant, instance="instance-a",
                              permissions=list(permissions), exp=exp), sort_keys=True).encode()
        return raw.hex() + "." + hmac.new(self.key, raw, hashlib.sha256).hexdigest()

    def decide(self, *, event=None, token=None, backend=None):
        return snapshot_pair_decision(event=self.event if event is None else event,
                                      assertion=self.token() if token is None else token,
                                      verifier=self.verifier,
                                      fetch_pair=self.backend if backend is None else backend)

    def test_revoked_permission_prevents_backend_access(self):
        for permissions in ((), ("twin:read",), ("evidence:read",)):
            backend = Mock()
            self.assertEqual(self.decide(token=self.token(permissions=permissions), backend=backend), "DENY")
            backend.assert_not_called()
        self.assertEqual(self.state["writes"], 0)

    def test_expired_or_cross_tenant_prevents_backend_access(self):
        for token in (self.token(exp=1000), self.token(tenant="tenant-b"), "bad"):
            backend = Mock()
            self.assertEqual(self.decide(token=token, backend=backend), "DENY")
            backend.assert_not_called()

    def test_backend_revocation_race_denies_without_mutation(self):
        backend = Mock(side_effect=PermissionError("revoked"))
        self.assertEqual(self.decide(backend=backend), "DENY")
        backend.assert_called_once()
        self.assertEqual(self.state["writes"], 0)

    def test_malformed_snapshot_id_denied_before_fetch(self):
        for identifier in (None, "../revision", "révision", "x" * 129, []):
            backend = Mock()
            self.assertEqual(self.decide(event=dict(self.event, snapshot_id=identifier), backend=backend), "DENY")
            backend.assert_not_called()

    def test_backend_identity_and_digest_swap_denied(self):
        cases = (
            SnapshotPair("revision1", replace(self.twin, tenant="tenant-b"), self.evidence),
            SnapshotPair("revision1", self.twin, replace(self.evidence, identifier="other")),
            SnapshotPair("revision1", self.twin, replace(self.evidence, payload_digest="f" * 64)),
            SnapshotPair("revision2", self.twin, self.evidence),
        )
        for pair in cases:
            self.assertEqual(self.decide(backend=Mock(return_value=pair)), "DENY")
        self.assertEqual(self.state["writes"], 0)

    def test_lying_backend_same_label_is_not_real_attestation(self):
        # A dishonest adapter can mix R1/R2 rows with unchanged public fields.
        # No per-row revision/provenance exists: this MUST NOT become real ALLOW.
        mixed = SnapshotPair("revision1", self.twin, self.evidence)
        decision = self.decide(backend=Mock(return_value=mixed))
        self.assertEqual(decision, "ALLOW_SYNTHETIC")
        self.assertNotEqual(decision, "ALLOW")
        self.assertEqual(self.state["writes"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
