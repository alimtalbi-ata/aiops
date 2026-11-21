"""Synthetic fail-closed decision boundary for Event -> Twin/Evidence.

Not production authorization. Both resources must be authenticated and bound
before a policy result can be returned; never expose raw backend rows to GAMMA.
No network, secrets, or customer data.
"""
import hashlib
import hmac
import json
import unittest
from unittest.mock import Mock

from secure_boundary import AssertionVerifier
from resource_binding import Resource, ScopedFixtureBackend, verify_binding, policy_evaluate, _identifier, _scope, _digest


def authenticated_pair_decision(*, event, assertion, verifier, fetch):
    """Atomic *decision*, not a storage transaction or cryptographic CMDB proof.

    A single assertion must carry BOTH read permissions; backend identity checks
    are mandatory for each read. Any denial, missing row, or malformed event
    returns DENY. No ALLOW is an authorization to mutate a resource.
    """
    if not isinstance(event, dict):
        return "DENY"
    try:
        tenant, instance = event["tenant"], event["instance"]
        twin_id, evidence_id = event["twin_identifier"], event["evidence_identifier"]
        _scope(tenant)
        _scope(instance)
        _identifier(twin_id)
        _identifier(evidence_id)
        _identifier(event["event"])
        _digest(event["digest"])
        # Verify once and require both permissions before any backend access.
        principal = verifier.verify(assertion)
        if (principal.tenant != tenant or principal.instance != instance or
                not {"twin:read", "evidence:read"}.issubset(principal.permissions)):
            return "DENY"
        # One trusted verification sample: no re-verification between reads.
        # Validate the Twin binding and event/digest before fetching Evidence.
        twin = verify_binding(fetch, resource="twin", tenant=tenant,
                              instance=instance, identifier=twin_id)
        if twin is None:
            return "DENY"
        if twin.event != event["event"] or twin.payload_digest != event["digest"]:
            return "DENY"
        evidence = verify_binding(fetch, resource="evidence", tenant=tenant,
                                  instance=instance, identifier=evidence_id)
        return policy_evaluate(event=event, twin=twin, evidence=evidence)
    except (PermissionError, KeyError, TypeError, ValueError, AttributeError):
        return "DENY"


class PairDecisionTests(unittest.TestCase):
    def setUp(self):
        self.key = b"synthetic-verifier-key-32-bytes-long!"
        self.verifier = AssertionVerifier(self.key, clock=lambda: 1000)
        self.digest = hashlib.sha256(b"synthetic-payload").hexdigest()
        self.twin = Resource("twin", "demo-a", "collector-a", "ci1", "e1", self.digest)
        self.evidence = Resource("evidence", "demo-a", "collector-a", "ev1", "e1", self.digest)
        self.backend = ScopedFixtureBackend((self.twin, self.evidence))
        self.event = dict(tenant="demo-a", instance="collector-a", event="e1",
                          digest=self.digest, twin_identifier="ci1",
                          evidence_identifier="ev1")

    def token(self, permissions=("twin:read", "evidence:read"), tenant="demo-a"):
        claims = dict(tenant=tenant, instance="collector-a",
                      permissions=list(permissions), exp=1100)
        payload = json.dumps(claims, sort_keys=True).encode()
        return payload.hex() + "." + hmac.new(self.key, payload, hashlib.sha256).hexdigest()

    def decide(self, event=None, token=None, fetch=None):
        return authenticated_pair_decision(
            event=self.event if event is None else event,
            assertion=self.token() if token is None else token,
            verifier=self.verifier,
            fetch=self.backend.fetch if fetch is None else fetch)

    def test_valid_pair_only_synthetic_allow(self):
        self.assertEqual(self.decide(), "ALLOW_SYNTHETIC")

    def test_missing_permission_and_cross_tenant_zero_backend_calls(self):
        for token in (self.token(("twin:read",)), self.token(("evidence:read",)),
                      self.token(tenant="demo-b"), "malformed"):
            fetch = Mock()
            with self.subTest(token=token[:18]):
                self.assertEqual(self.decide(token=token, fetch=fetch), "DENY")
                fetch.assert_not_called()

    def test_invalid_opaque_ids_deny_before_backend(self):
        for key in ("twin_identifier", "evidence_identifier"):
            for bad in (None, "../escape", "é", "x" * 129, [], "a.b"):
                fetch = Mock()
                with self.subTest(key=key, bad=repr(bad)):
                    self.assertEqual(self.decide(event=dict(self.event, **{key: bad}), fetch=fetch), "DENY")
                    fetch.assert_not_called()

    def test_backend_substitution_and_digest_deny(self):
        for bad in (Resource("twin", "demo-b", "collector-a", "ci1", "e1", self.digest),
                    Resource("twin", "demo-a", "collector-a", "other", "e1", self.digest),
                    Resource("twin", "demo-a", "collector-a", "ci1", "e1", "b" * 64)):
            fetch = Mock(side_effect=lambda **kw: bad if kw["resource"] == "twin" else self.evidence)
            with self.subTest(bad=repr(bad)):
                self.assertEqual(self.decide(fetch=fetch), "DENY")

    def test_single_verification_clock_sample(self):
        ticks = iter((1000, 1001))
        verifier = AssertionVerifier(self.key, clock=lambda: next(ticks))
        self.assertEqual(authenticated_pair_decision(
            event=self.event, assertion=self.token(), verifier=verifier,
            fetch=self.backend.fetch), "ALLOW_SYNTHETIC")
        self.assertEqual(next(ticks), 1001)

    def test_twin_event_or_digest_mismatch_never_fetches_evidence(self):
        before = dict(self.backend._rows)
        for bad in (Resource("twin", "demo-a", "collector-a", "ci1", "other", self.digest),
                    Resource("twin", "demo-a", "collector-a", "ci1", "e1", "b" * 64)):
            fetch = Mock(side_effect=lambda **kw: bad if kw["resource"] == "twin" else self.evidence)
            with self.subTest(bad=repr(bad)):
                self.assertEqual(self.decide(fetch=fetch), "DENY")
                self.assertEqual(fetch.call_count, 1)
                self.assertEqual(fetch.call_args.kwargs["resource"], "twin")
        self.assertEqual(before, self.backend._rows)

    def test_missing_evidence_and_no_mutation(self):
        before = dict(self.backend._rows)
        fetch = Mock(side_effect=lambda **kw: self.twin if kw["resource"] == "twin" else None)
        self.assertEqual(self.decide(fetch=fetch), "DENY")
        self.assertEqual(self.decide(event=dict(self.event, digest="é")), "DENY")
        self.assertEqual(self.decide(event=dict(self.event, evidence_identifier="wrong")), "DENY")
        self.assertEqual(before, self.backend._rows)


if __name__ == "__main__":
    unittest.main(verbosity=2)
