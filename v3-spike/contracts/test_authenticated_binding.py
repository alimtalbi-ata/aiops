"""Synthetic integration gate: authenticated read -> backend identity binding -> policy.
Run from any directory: python v3-spike/contracts/test_authenticated_binding.py
No network, secrets, or production resources.
"""
import hashlib
import hmac
import json
import unittest
from unittest.mock import Mock

from secure_boundary import AssertionVerifier, verified_resource_read
from resource_binding import Resource, ScopedFixtureBackend, verify_binding, policy_evaluate


def authenticated_bound_read(fetch, assertion, verifier, *, resource, tenant, instance, identifier):
    """Compose both gates. Never expose the raw backend callback to the boundary."""
    def bound_fetch(*, resource, tenant, instance, identifier):
        return verify_binding(fetch, resource=resource, tenant=tenant,
                              instance=instance, identifier=identifier)
    return verified_resource_read(bound_fetch, assertion, verifier, resource=resource,
                                  tenant=tenant, instance=instance, identifier=identifier)


class AuthenticatedBindingTests(unittest.TestCase):
    def setUp(self):
        self.key = b"synthetic-verifier-key-32-bytes-long!"
        self.verifier = AssertionVerifier(self.key, clock=lambda: 1000)
        self.digest = hashlib.sha256(b"synthetic-payload").hexdigest()
        self.twin = Resource("twin", "demo-a", "collector-a", "ci1", "e1", self.digest)
        self.evidence = Resource("evidence", "demo-a", "collector-a", "ev1", "e1", self.digest)
        self.backend = ScopedFixtureBackend((self.twin, self.evidence))
        self.event = dict(tenant="demo-a", instance="collector-a", event="e1",
                          digest=self.digest, twin_identifier="ci1", evidence_identifier="ev1")

    def token(self, permissions, tenant="demo-a", instance="collector-a"):
        claims = dict(tenant=tenant, instance=instance, permissions=permissions, exp=1100)
        payload = json.dumps(claims, sort_keys=True).encode()
        return payload.hex() + "." + hmac.new(self.key, payload, hashlib.sha256).hexdigest()

    def read(self, fetch, *, resource="twin", tenant="demo-a", instance="collector-a",
             identifier="ci1", token=None):
        if token is None:
            token = self.token([resource + ":read"])
        return authenticated_bound_read(fetch, token, self.verifier, resource=resource,
                                        tenant=tenant, instance=instance, identifier=identifier)

    def test_authorized_pair_and_policy(self):
        twin = self.read(self.backend.fetch)
        evidence = self.read(self.backend.fetch, resource="evidence", identifier="ev1")
        self.assertEqual((twin, evidence), (self.twin, self.evidence))
        self.assertEqual(policy_evaluate(event=self.event, twin=twin, evidence=evidence),
                         "ALLOW_SYNTHETIC")

    def test_acl_before_fetch_and_no_mutation(self):
        fetch = Mock(return_value=self.twin)
        before = dict(self.backend._rows)
        cases = [
            dict(tenant="demo-b"),
            dict(token=self.token(["evidence:read"])),
            dict(token=self.token(["twin:read"], tenant="demo-b")),
            dict(identifier="../ci1"),
            dict(identifier="é"),
            dict(identifier=None),
        ]
        for patch in cases:
            with self.subTest(patch=repr(patch)), self.assertRaisesRegex(PermissionError, "^unauthorized$"):
                self.read(fetch, **patch)
        fetch.assert_not_called()
        self.assertEqual(before, self.backend._rows)

    def test_backend_substitution_rejected(self):
        rows = [
            Resource("twin", "demo-b", "collector-a", "ci1", "e1", self.digest),
            Resource("twin", "demo-a", "other", "ci1", "e1", self.digest),
            Resource("twin", "demo-a", "collector-a", "other", "e1", self.digest),
            Resource("evidence", "demo-a", "collector-a", "ci1", "e1", self.digest),
            Resource("twin", "demo-a", "collector-a", "ci1", "e1", "b" * 64),
        ]
        for row in rows:
            with self.subTest(row=repr(row)):
                if row.identifier == "ci1" and row.tenant == "demo-a" and row.instance == "collector-a" and row.resource == "twin":
                    # A digest substitution is not rejected by identity-only binding;
                    # it MUST be rejected by event policy.
                    bound = self.read(Mock(return_value=row))
                    self.assertEqual(policy_evaluate(event=self.event, twin=bound, evidence=self.evidence), "DENY")
                else:
                    with self.assertRaisesRegex(PermissionError, "^unauthorized$"):
                        self.read(Mock(return_value=row))

    def test_same_scope_wrong_event_or_digest_policy_deny(self):
        for row in (
            Resource("twin", "demo-a", "collector-a", "ci1", "other-event", self.digest),
            Resource("twin", "demo-a", "collector-a", "ci1", "e1", "b" * 64),
        ):
            bound = self.read(Mock(return_value=row))
            self.assertEqual(policy_evaluate(event=self.event, twin=bound, evidence=self.evidence), "DENY")


if __name__ == "__main__":
    unittest.main(verbosity=2)
