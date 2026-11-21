"""Synthetic-only Twin/Evidence backend binding contract (V3 B).

The caller MUST authenticate via secure_boundary.verified_resource_read first.
The backend MUST enforce tenant/instance ACL in its own query; this in-memory
fixture demonstrates that obligation, not production authorization.
No client data, network, filesystem or privileged operations.
"""
from dataclasses import dataclass
from typing import Mapping
import unittest
from unittest.mock import Mock


@dataclass(frozen=True)
class Resource:
    resource: str
    tenant: str
    instance: str
    identifier: str
    event: str
    payload_digest: str
    classification: str = "SYNTHETIC"


def _identifier(value):
    if (not isinstance(value, str) or not 1 <= len(value) <= 128 or
            not value.isascii() or
            not all(c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_:-" for c in value)):
        raise PermissionError("unauthorized")


def _scope(value):
    if (not isinstance(value, str) or not 1 <= len(value) <= 128 or
            not value.isascii() or
            not all(c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-" for c in value)):
        raise PermissionError("unauthorized")


def _digest(value):
    if (not isinstance(value, str) or len(value) != 64 or not value.isascii() or
            any(c not in "0123456789abcdef" for c in value)):
        raise PermissionError("unauthorized")


class ScopedFixtureBackend:
    """Exact tuple key: no delimiter concatenation, no fallback or wildcard."""

    def __init__(self, resources=()):
        self._rows = {}
        for row in resources:
            self._validate(row)
            key = (row.resource, row.tenant, row.instance, row.identifier)
            if key in self._rows:
                raise ValueError("duplicate fixture identity")
            self._rows[key] = row

    @staticmethod
    def _validate(row):
        if not isinstance(row, Resource) or row.resource not in ("twin", "evidence"):
            raise PermissionError("unauthorized")
        _scope(row.tenant)
        _scope(row.instance)
        _identifier(row.identifier)
        _identifier(row.event)
        _digest(row.payload_digest)
        if row.classification != "SYNTHETIC":
            raise PermissionError("unauthorized")

    def fetch(self, *, resource, tenant, instance, identifier):
        if resource not in ("twin", "evidence"):
            raise PermissionError("unauthorized")
        _scope(tenant)
        _scope(instance)
        _identifier(identifier)
        return self._rows.get((resource, tenant, instance, identifier))


def verify_binding(fetch, *, resource, tenant, instance, identifier):
    """Defense in depth: verify result identity; never return unbound evidence.

    Must be called only *after* assertion authorization. An untrusted backend
    returning a different tenant, resource or identifier fails closed.
    """
    if resource not in ("twin", "evidence"):
        raise PermissionError("unauthorized")
    _scope(tenant)
    _scope(instance)
    _identifier(identifier)
    row = fetch(resource=resource, tenant=tenant, instance=instance, identifier=identifier)
    if row is None:
        return None
    if not isinstance(row, Resource):
        raise PermissionError("unauthorized")
    ScopedFixtureBackend._validate(row)
    if (row.resource, row.tenant, row.instance, row.identifier) != (resource, tenant, instance, identifier):
        raise PermissionError("unauthorized")
    return row


def policy_evaluate(*, event, twin, evidence):
    """Synthetic deny-first oracle; absence or contradictory evidence => DENY."""
    if not isinstance(event, Mapping):
        return "DENY"
    try:
        tenant, instance, event_id, digest = (event[k] for k in ("tenant", "instance", "event", "digest"))
        _scope(tenant)
        _scope(instance)
        _identifier(event_id)
        _digest(digest)
    except (KeyError, TypeError, PermissionError):
        return "DENY"
    if twin is None or evidence is None:
        return "DENY"
    try:
        for row, kind in ((twin, "twin"), (evidence, "evidence")):
            ScopedFixtureBackend._validate(row)
            if (row.resource, row.tenant, row.instance, row.event, row.payload_digest) != (
                    kind, tenant, instance, event_id, digest):
                return "DENY"
    except PermissionError:
        return "DENY"
    return "ALLOW_SYNTHETIC"


class BindingContractTests(unittest.TestCase):
    def setUp(self):
        self.digest = "a" * 64
        self.event = dict(tenant="demo-a", instance="collector-a", event="e1", digest=self.digest)
        self.twin = Resource("twin", "demo-a", "collector-a", "ci1", "e1", self.digest)
        self.evidence = Resource("evidence", "demo-a", "collector-a", "ev1", "e1", self.digest)
        self.backend = ScopedFixtureBackend((self.twin, self.evidence))

    def test_exact_scope_and_no_cross_tenant_disclosure(self):
        self.assertEqual(self.backend.fetch(resource="twin", tenant="demo-a", instance="collector-a", identifier="ci1"), self.twin)
        for tenant, instance, identifier in (("demo-b", "collector-a", "ci1"), ("demo-a", "other", "ci1"), ("demo-a", "collector-a", "ev1")):
            with self.subTest(tenant=tenant, instance=instance, identifier=identifier):
                self.assertIsNone(self.backend.fetch(resource="twin", tenant=tenant, instance=instance, identifier=identifier))

    def test_invalid_identifier_denied_before_backend(self):
        fetch = Mock()
        for value in (None, [], 1, "", "../ci1", "é", "x" * 129, "a.b", "a/b", "a\\b"):
            with self.subTest(value=repr(value)), self.assertRaisesRegex(PermissionError, "^unauthorized$"):
                verify_binding(fetch, resource="twin", tenant="demo-a", instance="collector-a", identifier=value)
        fetch.assert_not_called()

    def test_malicious_backend_response_denied(self):
        for row in (Resource("twin", "demo-b", "collector-a", "ci1", "e1", self.digest),
                    Resource("evidence", "demo-a", "collector-a", "ci1", "e1", self.digest),
                    Resource("twin", "demo-a", "collector-a", "other", "e1", self.digest),
                    dict(tenant="demo-a")):
            with self.subTest(row=repr(row)), self.assertRaisesRegex(PermissionError, "^unauthorized$"):
                verify_binding(Mock(return_value=row), resource="twin", tenant="demo-a", instance="collector-a", identifier="ci1")

    def test_tuple_identity_collision_resistance(self):
        rows = (Resource("twin", "demo-a", "collector-a:x", "e1", "e1", self.digest),
                Resource("twin", "demo-a", "collector-a", "x:e1", "e1", self.digest))
        backend = ScopedFixtureBackend(rows)
        for row in rows:
            self.assertEqual(backend.fetch(resource=row.resource, tenant=row.tenant, instance=row.instance, identifier=row.identifier), row)

    def test_policy_deny_missing_conflicting_and_digest(self):
        self.assertEqual(policy_evaluate(event=self.event, twin=self.twin, evidence=self.evidence), "ALLOW_SYNTHETIC")
        for twin, evidence in ((None, self.evidence), (self.twin, None),
                               (Resource("twin", "demo-b", "collector-a", "ci1", "e1", self.digest), self.evidence),
                               (self.twin, Resource("evidence", "demo-a", "collector-a", "ev1", "e1", "b" * 64))):
            self.assertEqual(policy_evaluate(event=self.event, twin=twin, evidence=evidence), "DENY")
        self.assertEqual(policy_evaluate(event=dict(self.event, digest="é"), twin=self.twin, evidence=self.evidence), "DENY")

    def test_no_mutation_on_failed_reads(self):
        before = dict(self.backend._rows)
        for value in ("../ci1", "é", None):
            with self.assertRaises(PermissionError):
                self.backend.fetch(resource="twin", tenant="demo-a", instance="collector-a", identifier=value)
        self.assertEqual(before, self.backend._rows)


if __name__ == "__main__":
    unittest.main(verbosity=2)
