"""Synthetic-only authenticated boundary for the V3 event store.

The verifier key is injected by a trusted service, never from an event or client.
This module is NOT an HTTP authentication service or a production identity provider.
"""
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class VerifiedPrincipal:
    tenant: str
    instance: str
    permissions: frozenset[str]


class AssertionVerifier:
    """Verify short-lived, service-issued HMAC assertions, fail closed."""
    def __init__(self, key: bytes, clock: Callable[[], int] = lambda: int(time.time())):
        if not isinstance(key, bytes) or len(key) < 32:
            raise ValueError("service verification key must be >=32 bytes")
        self._key = key
        self._clock = clock

    def verify(self, assertion: str) -> VerifiedPrincipal:
        try:
            payload_hex, signature = assertion.split(".")
            payload = bytes.fromhex(payload_hex)
            expected = hmac.new(self._key, payload, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise PermissionError("unauthorized")
            claims = json.loads(payload)
            if set(claims) != {"tenant", "instance", "permissions", "exp"}:
                raise PermissionError("unauthorized")
            if not all(isinstance(claims[k], str) and claims[k] for k in ("tenant", "instance")):
                raise PermissionError("unauthorized")
            permissions = claims["permissions"]
            if not isinstance(permissions, list) or len(permissions) != len(set(permissions)):
                raise PermissionError("unauthorized")
            if any(p not in ("event:write", "event:read", "evidence:read", "twin:read") for p in permissions):
                raise PermissionError("unauthorized")
            exp = claims["exp"]
            if type(exp) is not int or not self._clock() < exp <= self._clock() + 300:
                raise PermissionError("unauthorized")
            return VerifiedPrincipal(claims["tenant"], claims["instance"], frozenset(permissions))
        except (ValueError, TypeError, KeyError, UnicodeError, json.JSONDecodeError) as exc:
            raise PermissionError("unauthorized") from exc


def _authorized(principal: VerifiedPrincipal, permission: str, tenant: str, instance: str):
    if (permission not in principal.permissions or
            not hmac.compare_digest(principal.tenant, tenant) or
            not hmac.compare_digest(principal.instance, instance)):
        raise PermissionError("unauthorized")


def verified_admit(store, path, body, payload: bytes, assertion: str, verifier: AssertionVerifier, now):
    """Verify source, permission and actual bytes BEFORE any store mutation."""
    principal = verifier.verify(assertion)
    _authorized(principal, "event:write", body.get("tenant", ""), body.get("instance", ""))
    if not isinstance(payload, bytes) or len(payload) > 1024 * 1024:
        raise PermissionError("unauthorized")
    actual = hashlib.sha256(payload).hexdigest()
    if not isinstance(body.get("digest"), str) or not hmac.compare_digest(actual, body["digest"]):
        raise PermissionError("unauthorized")
    return store.admit(path, body, tenant=principal.tenant, instance=principal.instance, now=now)


def verified_read(store, path, assertion: str, verifier: AssertionVerifier, *, tenant: str, instance: str, event: str):
    principal = verifier.verify(assertion)
    _authorized(principal, "event:read", tenant, instance)
    return store.read(path, tenant=principal.tenant, instance=principal.instance, event=event)


def verified_resource_read(fetch, assertion: str, verifier: AssertionVerifier, *, resource: str, tenant: str, instance: str, identifier: str):
    if resource not in ("evidence", "twin"):
        raise PermissionError("unauthorized")
    principal = verifier.verify(assertion)
    _authorized(principal, resource + ":read", tenant, instance)
    return fetch(resource=resource, tenant=principal.tenant, instance=principal.instance, identifier=identifier)


# Tests use only synthetic fixtures; no external service or client data.
if __name__ == "__main__":
    import unittest
    from unittest.mock import Mock

    class SecurityTests(unittest.TestCase):
        def setUp(self):
            self.key = b"synthetic-verifier-key-32-bytes-long!"
            self.verifier = AssertionVerifier(self.key, clock=lambda: 1000)
            self.payload = b"synthetic-event"
            self.body = {"tenant": "demo-a", "instance": "collector-a", "digest": hashlib.sha256(self.payload).hexdigest()}
            self.store = Mock()
            self.store.admit.return_value = "ACCEPT"

        def assertion(self, permissions, tenant="demo-a", instance="collector-a", exp=1100):
            claims = dict(tenant=tenant, instance=instance, permissions=permissions, exp=exp)
            payload = json.dumps(claims, sort_keys=True).encode()
            return payload.hex() + "." + hmac.new(self.key, payload, hashlib.sha256).hexdigest()

        def test_verified_admission(self):
            result = verified_admit(self.store, "synthetic.db", self.body, self.payload,
                                    self.assertion(["event:write"]), self.verifier, now=1000)
            self.assertEqual(result, "ACCEPT")
            self.store.admit.assert_called_once()

        def test_digest_tampering_denied_before_write(self):
            with self.assertRaises(PermissionError):
                verified_admit(self.store, "synthetic.db", self.body, b"altered",
                               self.assertion(["event:write"]), self.verifier, now=1000)
            self.store.admit.assert_not_called()

        def test_tenant_impersonation_denied(self):
            with self.assertRaises(PermissionError):
                verified_admit(self.store, "synthetic.db", self.body, self.payload,
                               self.assertion(["event:write"], tenant="other"), self.verifier, now=1000)
            self.store.admit.assert_not_called()

        def test_signature_and_expiry_denied(self):
            for token in (self.assertion(["event:write"])[:-1] + "0",
                          self.assertion(["event:write"], exp=999)):
                with self.subTest(token=token), self.assertRaises(PermissionError):
                    verified_admit(self.store, "synthetic.db", self.body, self.payload, token, self.verifier, now=1000)
            self.store.admit.assert_not_called()

        def test_read_and_resource_acl(self):
            fetch = Mock(return_value={"synthetic": True})
            with self.assertRaises(PermissionError):
                verified_read(self.store, "synthetic.db", self.assertion(["event:write"]),
                              self.verifier, tenant="demo-a", instance="collector-a", event="e1")
            with self.assertRaises(PermissionError):
                verified_resource_read(fetch, self.assertion(["evidence:read"]), self.verifier,
                                       resource="twin", tenant="demo-a", instance="collector-a", identifier="ci1")
            fetch.assert_not_called()
            self.assertEqual(verified_resource_read(fetch, self.assertion(["evidence:read"]), self.verifier,
                                                    resource="evidence", tenant="demo-a", instance="collector-a",
                                                    identifier="ev1"), {"synthetic": True})

    unittest.main()
