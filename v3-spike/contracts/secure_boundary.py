"""Synthetic-only authenticated boundary for the V3 event store.

The verifier key is injected by a trusted service, never from an event or client.
This module is NOT an HTTP authentication service or a production identity provider.
"""
import datetime as dt
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

    def now(self) -> int:
        return int(self._clock())

    def verify(self, assertion: str) -> VerifiedPrincipal:
        if not isinstance(assertion, str) or len(assertion) > 8192 or not assertion.isascii():
            raise PermissionError("unauthorized")
        try:
            payload_hex, signature = assertion.split(".")
            if len(signature) != 64 or len(payload_hex) > 8192 or len(payload_hex) % 2:
                raise PermissionError("unauthorized")
            payload = bytes.fromhex(payload_hex)
            expected = hmac.new(self._key, payload, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise PermissionError("unauthorized")
            def unique_pairs(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError("duplicate claim")
                    result[key] = value
                return result
            claims = json.loads(payload, object_pairs_hook=unique_pairs)
            if not isinstance(claims, dict):
                raise PermissionError("unauthorized")
            if set(claims) != {"tenant", "instance", "permissions", "exp"}:
                raise PermissionError("unauthorized")
            if not all(isinstance(claims[k], str) and 1 <= len(claims[k]) <= 128 and
                       claims[k].isascii() and all(c.isalnum() or c in "._:-" for c in claims[k])
                       for k in ("tenant", "instance")):
                raise PermissionError("unauthorized")
            permissions = claims["permissions"]
            if not isinstance(permissions, list) or len(permissions) > 4 or not all(isinstance(p, str) for p in permissions) or len(permissions) != len(set(permissions)):
                raise PermissionError("unauthorized")
            if any(p not in ("event:write", "event:read", "evidence:read", "twin:read") for p in permissions):
                raise PermissionError("unauthorized")
            exp = claims["exp"]
            current = self.now()
            if type(exp) is not int or not current < exp <= current + 300:
                raise PermissionError("unauthorized")
            return VerifiedPrincipal(claims["tenant"], claims["instance"], frozenset(permissions))
        except (ValueError, TypeError, KeyError, UnicodeError, json.JSONDecodeError) as exc:
            raise PermissionError("unauthorized") from exc


def _authorized(principal: VerifiedPrincipal, permission: str, tenant: str, instance: str):
    if (not isinstance(tenant, str) or not isinstance(instance, str) or
            not tenant.isascii() or not instance.isascii() or
            permission not in principal.permissions or
            not hmac.compare_digest(principal.tenant, tenant) or
            not hmac.compare_digest(principal.instance, instance)):
        raise PermissionError("unauthorized")


def verified_admit(store, path, body, payload: bytes, assertion: str, verifier: AssertionVerifier):
    """Verify source, permission and actual bytes BEFORE any store mutation."""
    principal = verifier.verify(assertion)
    if not isinstance(body, dict):
        raise PermissionError("unauthorized")
    _authorized(principal, "event:write", body.get("tenant", ""), body.get("instance", ""))
    if not isinstance(payload, bytes) or len(payload) > 1024 * 1024:
        raise PermissionError("unauthorized")
    actual = hashlib.sha256(payload).hexdigest()
    if not isinstance(body.get("digest"), str) or not hmac.compare_digest(actual, body["digest"]):
        raise PermissionError("unauthorized")
    return store.admit(path, body, tenant=principal.tenant, instance=principal.instance, now=dt.datetime.fromtimestamp(verifier.now(), tz=dt.timezone.utc))


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
                                    self.assertion(["event:write"]), self.verifier)
            self.assertEqual(result, "ACCEPT")
            self.store.admit.assert_called_once()
            self.assertEqual(self.store.admit.call_args.kwargs["now"], dt.datetime.fromtimestamp(1000, tz=dt.timezone.utc))
            self.assertIsInstance(self.store.admit.call_args.kwargs["now"], dt.datetime)

        def test_integrated_sqlite_durability_synthetic(self):
            # Integration gate: real event_store, synthetic payload, no external I/O.
            import tempfile
            from pathlib import Path
            import event_store

            timestamp = int(dt.datetime(2026, 11, 20, 12, tzinfo=dt.timezone.utc).timestamp())
            verifier = AssertionVerifier(self.key, clock=lambda: timestamp)
            body = dict(self.body, event="e1", domain="database", ci="db1",
                        mode="SYNTHETIC", at="2026-11-20T12:00:00Z")
            with tempfile.TemporaryDirectory() as directory:
                path = str(Path(directory) / "events.sqlite")
                event_store.initialize(path)
                claims = dict(tenant="demo-a", instance="collector-a",
                              permissions=["event:write"], exp=timestamp + 300)
                raw = json.dumps(claims, sort_keys=True).encode()
                token = raw.hex() + "." + hmac.new(self.key, raw, hashlib.sha256).hexdigest()
                self.assertEqual(verified_admit(event_store, path, body, self.payload, token, verifier), "ACCEPT")
                self.assertEqual(verified_admit(event_store, path, body, self.payload, token, verifier), "DUPLICATE")
                self.assertEqual(event_store.read(path, tenant="demo-a", instance="collector-a", event="e1"), body)

        def test_digest_tampering_denied_before_write(self):
            with self.assertRaises(PermissionError):
                verified_admit(self.store, "synthetic.db", self.body, b"altered",
                               self.assertion(["event:write"]), self.verifier)
            self.store.admit.assert_not_called()

        def test_tenant_impersonation_denied(self):
            with self.assertRaises(PermissionError):
                verified_admit(self.store, "synthetic.db", self.body, self.payload,
                               self.assertion(["event:write"], tenant="other"), self.verifier)
            self.store.admit.assert_not_called()

        def test_signature_and_expiry_denied(self):
            for token in (self.assertion(["event:write"])[:-1] + "0",
                          self.assertion(["event:write"], exp=999)):
                with self.subTest(token=token), self.assertRaises(PermissionError):
                    verified_admit(self.store, "synthetic.db", self.body, self.payload, token, self.verifier)
            self.store.admit.assert_not_called()

        def test_read_and_resource_acl(self):
            for token in (None, 42, "", "a" * 9000):
                with self.subTest(token=str(token)[:20]), self.assertRaises(PermissionError):
                    self.verifier.verify(token)
            for tenant in (None, 42, []):
                with self.subTest(tenant=tenant), self.assertRaises(PermissionError):
                    verified_admit(self.store, "synthetic.db", dict(self.body, tenant=tenant),
                                   self.payload, self.assertion(["event:write"]), self.verifier)
            for body in (None, 42, []):
                with self.subTest(body=body), self.assertRaises(PermissionError):
                    verified_admit(self.store, "synthetic.db", body, self.payload,
                                   self.assertion(["event:write"]), self.verifier)
            duplicate = b'{"tenant":"demo-a","tenant":"other","instance":"collector-a","permissions":["event:write"],"exp":1100}'
            token = duplicate.hex() + "." + hmac.new(self.key, duplicate, hashlib.sha256).hexdigest()
            with self.assertRaises(PermissionError):
                self.verifier.verify(token)
            with self.assertRaises(PermissionError):
                self.verifier.verify(self.assertion([42]))
            self.store.admit.assert_not_called()
            # Non-ASCII caller scopes must deny, not leak TypeError from compare_digest.
            for scope in ("ténant", "instancé"):
                with self.subTest(scope=scope), self.assertRaisesRegex(PermissionError, "^unauthorized$"):
                    verified_admit(self.store, "synthetic.db", dict(self.body, tenant=scope),
                                   self.payload, self.assertion(["event:write"]), self.verifier)
            for expiry, accepted in ((1300, True), (1301, False), (1000, False)):
                with self.subTest(expiry=expiry):
                    token = self.assertion(["event:write"], exp=expiry)
                    if accepted:
                        self.assertEqual(self.verifier.verify(token).tenant, "demo-a")
                    else:
                        with self.assertRaisesRegex(PermissionError, "^unauthorized$"):
                            self.verifier.verify(token)
            self.store.admit.assert_not_called()

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
