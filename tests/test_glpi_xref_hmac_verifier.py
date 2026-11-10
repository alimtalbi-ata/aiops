"""Offline HMAC verifier tests; keys and nonce store are disposable fixtures."""
import hashlib
import hmac
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from shared.glpi_xref_hmac_verifier import (
    XrefSignatureRejected, canonical_event_bytes, verify_hmac_xref_event,
)


class HmacXrefTests(unittest.TestCase):
    def setUp(self):
        self.secret = b"x" * 32
        self.claims = dict(aud="aiops-glpi-copilot-xref", iss="aiops-core-xref-signer", actor="operator",
                           tenant_id="tenant-a", ticket_id="201",
                           glpi_instance_id="ci", glpi_entity_id="7",
                           incident_id="INC-DEMO-12345678",
                           run_id="RUN-12345678", association_state="ACTIVE",
                           association_count=1, iat=1000, exp=1100,
                           nonce="nonce123456789012")
        self.seen = set()
        self.acl_calls = []

    def signed(self):
        return {"claims": dict(self.claims), "signature": hmac.new(
            self.secret, canonical_event_bytes(self.claims),
            hashlib.sha256).hexdigest()}

    def acl(self, **kwargs):
        self.acl_calls.append(kwargs)
        return True

    def nonce(self, **kwargs):
        value = (kwargs["tenant_id"], kwargs["nonce"])
        if value in self.seen:
            return False
        self.seen.add(value)
        return True

    def invoke(self, **kwargs):
        args = dict(event=self.signed(), actor="operator", tenant_id="tenant-a",
                    ticket_id="201", secret=self.secret, now=1050,
                    consume_nonce=self.nonce, authorize_actor=self.acl)
        args.update(kwargs)
        return verify_hmac_xref_event(**args)

    def test_signed_event_is_verified_once(self):
        claims = self.invoke()
        self.assertEqual(claims["run_id"], "RUN-12345678")
        with self.assertRaises(XrefSignatureRejected):
            self.invoke()

    def test_signature_tamper_rejected_before_acl(self):
        event = self.signed()
        event["claims"]["ticket_id"] = "202"
        with self.assertRaises(XrefSignatureRejected):
            self.invoke(event=event)
        self.assertEqual(self.acl_calls, [])

    def test_signed_scope_and_audience_rejected(self):
        for field, value in (("aud", "other"), ("iss", "other"), ("tenant_id", "other"),
                             ("actor", "other"), ("ticket_id", "202")):
            with self.subTest(field=field):
                self.claims[field] = value
                with self.assertRaises(XrefSignatureRejected):
                    self.invoke()
                self.claims[field] = dict(
                    aud="aiops-glpi-copilot-xref", iss="aiops-core-xref-signer", tenant_id="tenant-a",
                    actor="operator", ticket_id="201")[field]

    def test_expired_future_and_long_lived_rejected(self):
        for iat, exp in ((1000, 1050), (1081, 1100), (1000, 1400)):
            with self.subTest(iat=iat, exp=exp):
                self.claims["iat"], self.claims["exp"] = iat, exp
                with self.assertRaises(XrefSignatureRejected):
                    self.invoke()

    def test_acl_denial_and_missing_replay_store_block(self):
        with self.assertRaises(XrefSignatureRejected):
            self.invoke(authorize_actor=lambda **_: False)
        with self.assertRaises(XrefSignatureRejected):
            self.invoke(consume_nonce=None)

    def test_inactive_or_ambiguous_association_rejected_before_acl_and_nonce(self):
        for field, value in (("association_state", "REVOKED"),
                             ("association_count", 0),
                             ("association_count", 2),
                             ("association_count", True)):
            with self.subTest(field=field, value=value):
                original = self.claims[field]
                self.claims[field] = value
                with self.assertRaises(XrefSignatureRejected):
                    self.invoke()
                self.claims[field] = original
        self.assertEqual(self.acl_calls, [])
        self.assertEqual(self.seen, set())

    def test_missing_signed_identity_rejected_before_acl_and_nonce(self):
        for field in ("glpi_instance_id", "glpi_entity_id",
                      "incident_id", "run_id"):
            with self.subTest(field=field):
                original = self.claims.pop(field)
                with self.assertRaises(XrefSignatureRejected):
                    self.invoke()
                self.claims[field] = original
        self.assertEqual(self.acl_calls, [])
        self.assertEqual(self.seen, set())

    def test_malformed_signed_identity_never_consumes_nonce(self):
        for field, value in (("run_id", "RUN-../../bad"),
                             ("incident_id", "INC-?bad"),
                             ("glpi_entity_id", "-1"),
                             ("glpi_instance_id", "ci" + chr(10) + "other")):
            with self.subTest(field=field):
                original = self.claims[field]
                self.claims[field] = value
                with self.assertRaisesRegex(XrefSignatureRejected,
                                            "signed_identity_invalid"):
                    self.invoke()
                self.claims[field] = original
        self.assertEqual(self.acl_calls, [])
        self.assertEqual(self.seen, set())

    def test_unsigned_or_short_secret_rejected(self):
        with self.assertRaises(XrefSignatureRejected):
            self.invoke(secret=b"short")
        with self.assertRaises(XrefSignatureRejected):
            self.invoke(event={"claims": self.claims})


if __name__ == "__main__":
    unittest.main()
