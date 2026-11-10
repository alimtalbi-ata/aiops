"""Offline HMAC → canonical xref → Core/GLPI comparison integration."""
import hashlib
import hmac
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from shared.glpi_hmac_qualification import (
    GLPIHmacQualificationBlocked, make_hmac_glpi_qualifier,
)
from shared.glpi_xref_hmac_verifier import canonical_event_bytes


class HmacQualificationTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.secret = b"k" * 32
        self.claims = dict(aud="aiops-glpi-copilot-xref", iss="aiops-core-xref-signer", actor="operator",
                           tenant_id="tenant-a", ticket_id="201",
                           glpi_instance_id="ci", glpi_entity_id="7",
                           incident_id="INC-DEMO-12345678",
                           run_id="RUN-12345678", association_state="ACTIVE",
                           association_count=1, iat=1000, exp=1100,
                           nonce="nonce123456789012")
        self.core = {"run": {"run_id": "RUN-12345678",
                             "incident_id": "INC-DEMO-12345678", "mode": "DEMO"}}
        self.glpi = {"id": 201, "entities_id": 7}

    def fetch(self, **kwargs):
        self.calls.append("fetch")
        return {"claims": dict(self.claims), "signature": hmac.new(
            self.secret, canonical_event_bytes(self.claims),
            hashlib.sha256).hexdigest()}

    def acl(self, **kwargs):
        self.calls.append("acl")
        return True

    def nonce(self, **kwargs):
        self.calls.append("nonce")
        return True

    def core_reader(self, **kwargs):
        self.calls.append("core")
        return self.core

    def glpi_reader(self, **kwargs):
        self.calls.append("glpi")
        return self.glpi

    def make(self, **kwargs):
        args = dict(secret=self.secret, fetch_signed_event=self.fetch,
                    consume_nonce=self.nonce, authorize_actor=self.acl,
                    read_core_raw=self.core_reader, read_glpi_raw=self.glpi_reader,
                    clock=lambda: 1050)
        args.update(kwargs)
        return make_hmac_glpi_qualifier(**args)

    def test_signed_event_and_both_readbacks_match_without_side_effects(self):
        result = self.make()(actor="operator", tenant_id="tenant-a",
                             ticket_id="201")
        self.assertEqual(self.calls, ["fetch", "acl", "nonce", "core", "glpi"])
        self.assertEqual(result["run_id"], "RUN-12345678")
        self.assertEqual(result["status"], "READ_ONLY_XREF_COMPARISON")
        self.assertFalse(result["glpi_write_performed"])
        self.assertFalse(result["copilot_query_performed"])
        self.assertFalse(result["hitl_proposal_created"])
        self.assertFalse(result["execution_allowed"])
        self.assertTrue(result["raw_readbacks_match"])
        for flag in ("canonical_association_attested", "tenant_acl_verified",
                     "actor_acl_verified", "copilot_context_authorized",
                     "hitl_proposal_authorized"):
            with self.subTest(flag=flag):
                self.assertIs(result[flag], False)

    def test_core_mismatch_fails(self):
        self.core["run"]["incident_id"] = "INC-OTHER-12345678"
        with self.assertRaises(GLPIHmacQualificationBlocked):
            self.make()(actor="operator", tenant_id="tenant-a", ticket_id="201")

    def test_glpi_entity_mismatch_fails(self):
        self.glpi["entities_id"] = 9
        with self.assertRaises(GLPIHmacQualificationBlocked):
            self.make()(actor="operator", tenant_id="tenant-a", ticket_id="201")

    def test_denied_acl_blocks_all_readbacks(self):
        with self.assertRaises(GLPIHmacQualificationBlocked):
            self.make(authorize_actor=lambda **_: False)(
                actor="operator", tenant_id="tenant-a", ticket_id="201")
        self.assertEqual(self.calls, ["fetch"])

    def test_missing_reader_fails_at_installation(self):
        with self.assertRaises(ValueError):
            self.make(read_glpi_raw=None)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
