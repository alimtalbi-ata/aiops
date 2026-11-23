"""Synthetic backend-attestation boundary for Twin/Evidence integration.
This is a contract test, not production identity or key management.
"""
import hashlib
import hmac
import json
import sqlite3
import unittest

FIELDS = ("tenant_id", "principal_id", "event_id", "resource_id",
          "twin_revision", "evidence_digest", "policy_version", "approval_id")
KEY = b"synthetic-backend-key-32-bytes-minimum-0001"

def encode_claims(claims):
    if not isinstance(claims, dict) or set(claims) != set(FIELDS):
        raise ValueError("claims")
    if any(not isinstance(v, str) or not v or len(v) > 256 or
           any(ord(c) < 32 or ord(c) == 127 for c in v)
           for v in claims.values()):
        raise ValueError("fields")
    digest = claims["evidence_digest"]
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("digest")
    return json.dumps(claims, sort_keys=True, separators=(",", ":")).encode()

def sign_claims(claims, key=KEY):
    return hmac.new(key, encode_claims(claims), hashlib.sha256).hexdigest()

def attest_backend(claims, mac, key_id, trusted_backend_keys):
    """Fail closed; return an authenticated COPY, never an envelope-derived context."""
    try:
        if not isinstance(trusted_backend_keys, dict) or not isinstance(key_id, str):
            return None
        key = trusted_backend_keys.get(key_id)
        if not isinstance(key, bytes) or len(key) < 32 or not isinstance(mac, str):
            return None
        expected = hmac.new(key, encode_claims(claims), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, mac):
            return None
        return dict(claims)
    except (ValueError, TypeError, AttributeError):
        return None

class BackendAttestationBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.claims = dict(tenant_id="tenant-A", principal_id="p1", event_id="e1",
                           resource_id="opaque:001", twin_revision="r1",
                           evidence_digest=hashlib.sha256(b"synthetic").hexdigest(),
                           policy_version="policy1", approval_id="a1")
        self.keys = {"backend-issuer": KEY}
        self.mac = sign_claims(self.claims)
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE nonce (tenant TEXT, nonce TEXT, PRIMARY KEY(tenant,nonce))")
    def tearDown(self):
        self.db.close()
    def check(self, claims=None, mac=None, keys=None):
        return attest_backend(self.claims if claims is None else claims,
                              self.mac if mac is None else mac, "backend-issuer",
                              self.keys if keys is None else keys)
    def test_valid_attestation_returns_detached_copy(self):
        context = self.check()
        self.assertEqual(context, self.claims)
        self.assertIsNot(context, self.claims)
        context["tenant_id"] = "modified"
        self.assertEqual(self.claims["tenant_id"], "tenant-A")
    def test_tenant_substitution_fails_without_nonce_write(self):
        changed = dict(self.claims, tenant_id="tenant-B")
        self.assertIsNone(self.check(claims=changed))
        self.assertEqual(self.db.execute("SELECT count(*) FROM nonce").fetchone()[0], 0)
    def test_resource_substitution_fails_without_nonce_write(self):
        changed = dict(self.claims, resource_id="opaque:002")
        self.assertIsNone(self.check(claims=changed))
        self.assertEqual(self.db.execute("SELECT count(*) FROM nonce").fetchone()[0], 0)
    def test_digest_substitution_fails_without_nonce_write(self):
        changed = dict(self.claims, evidence_digest="0" * 64)
        self.assertIsNone(self.check(claims=changed))
        self.assertEqual(self.db.execute("SELECT count(*) FROM nonce").fetchone()[0], 0)
    def test_revoked_backend_issuer_fails(self):
        self.assertIsNone(self.check(keys={}))
        self.assertEqual(self.db.execute("SELECT count(*) FROM nonce").fetchone()[0], 0)
    def test_malformed_identity_and_key_fail_closed(self):
        for changed in (dict(self.claims, tenant_id="tenant-A\nspoof"),
                        dict(self.claims, resource_id=""),
                        dict(self.claims, evidence_digest="INVALID")):
            with self.subTest(changed=changed):
                self.assertIsNone(self.check(claims=changed))
        self.assertIsNone(self.check(keys={"backend-issuer": "not-bytes"}))
        self.assertEqual(self.db.execute("SELECT count(*) FROM nonce").fetchone()[0], 0)

if __name__ == "__main__":
    unittest.main()
