"""Offline tests of HMAC-backed canonical resolver composition."""
import hashlib
import hmac
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from shared.glpi_xref_hmac_verifier import canonical_event_bytes
from shared.glpi_xref_resolver_factory import make_hmac_canonical_xref_resolver
from shared.glpi_signed_xref_boundary import CanonicalXrefBlocked


class HmacResolverFactoryTests(unittest.TestCase):
    def setUp(self):
        self.secret = b"s" * 32
        self.calls = []
        self.claims = dict(aud="aiops-glpi-copilot-xref", iss="aiops-core-xref-signer", actor="operator",
                           tenant_id="tenant-a", ticket_id="201",
                           glpi_instance_id="ci", glpi_entity_id="7",
                           incident_id="INC-DEMO-12345678",
                           run_id="RUN-12345678", association_state="ACTIVE",
                           association_count=1, iat=1000, exp=1100,
                           nonce="nonce123456789012")

    def fetch(self, **kwargs):
        self.calls.append("fetch")
        return {"claims": dict(self.claims),
                "signature": hmac.new(self.secret,
                    canonical_event_bytes(self.claims), hashlib.sha256).hexdigest()}

    def nonce(self, **kwargs):
        self.calls.append("nonce")
        return True

    def acl(self, **kwargs):
        self.calls.append("acl")
        return True

    def make(self, **kwargs):
        deps = dict(secret=self.secret, fetch_signed_event=self.fetch,
                    consume_nonce=self.nonce, authorize_actor=self.acl,
                    clock=lambda: 1050)
        deps.update(kwargs)
        return make_hmac_canonical_xref_resolver(**deps)

    def test_real_hmac_composition_returns_canonical_identity(self):
        identity = self.make()(actor="operator", tenant_id="tenant-a",
                               ticket_id="201")
        self.assertEqual(identity["run_id"], "RUN-12345678")
        self.assertEqual(self.calls, ["fetch", "acl", "nonce"])

    def test_missing_acl_or_nonce_blocks_at_factory(self):
        for field in ("authorize_actor", "consume_nonce"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.make(**{field: None})
        self.assertEqual(self.calls, [])

    def test_invalid_signature_blocks_before_acl_and_nonce(self):
        resolver = self.make(secret=b"z" * 32)
        with self.assertRaises(CanonicalXrefBlocked):
            resolver(actor="operator", tenant_id="tenant-a", ticket_id="201")
        self.assertEqual(self.calls, ["fetch"])

    def test_acl_denial_blocks_nonce_consumption(self):
        resolver = self.make(authorize_actor=lambda **_: False)
        with self.assertRaises(CanonicalXrefBlocked):
            resolver(actor="operator", tenant_id="tenant-a", ticket_id="201")
        self.assertEqual(self.calls, ["fetch"])

    def test_tenant_scope_drift_blocks(self):
        resolver = self.make()
        with self.assertRaises(CanonicalXrefBlocked):
            resolver(actor="operator", tenant_id="tenant-b", ticket_id="201")
        self.assertEqual(self.calls, ["fetch"])


if __name__ == "__main__":
    unittest.main()
