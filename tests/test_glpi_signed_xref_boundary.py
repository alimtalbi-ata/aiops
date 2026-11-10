"""Offline signed-xref trust boundary tests; fake verifier is NOT an attestation."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from shared.glpi_signed_xref_boundary import (
    CanonicalXrefBlocked, resolve_signed_glpi_xref
)


class SignedXrefBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.claims = dict(actor="operator-a", tenant_id="tenant-a",
                           ticket_id="201", glpi_instance_id="ci",
                           glpi_entity_id="7", incident_id="INC-DEMO-12345678",
                           run_id="RUN-12345678", association_state="ACTIVE",
                           association_count=1)

    def fetch(self, **kwargs):
        self.calls.append("fetch")
        return {"signed_event": "fixture-not-cryptographic-proof"}

    def verify(self, **kwargs):
        self.calls.append("verify")
        return dict(self.claims)

    def invoke(self, **kwargs):
        args = dict(actor="operator-a", tenant_id="tenant-a", ticket_id="201",
                    fetch_signed_event=self.fetch, verify_event_and_acl=self.verify)
        args.update(kwargs)
        return resolve_signed_glpi_xref(**args)

    def test_missing_verifier_blocks_without_fetch(self):
        with self.assertRaises(CanonicalXrefBlocked):
            self.invoke(verify_event_and_acl=None)
        self.assertEqual(self.calls, [])

    def test_fake_verifier_contract_returns_only_identity_not_proof(self):
        identity = self.invoke()
        self.assertEqual(identity["run_id"], "RUN-12345678")
        self.assertNotIn("signed_event", identity)
        self.assertNotIn("acl_verified", identity)
        self.assertEqual(self.calls, ["fetch", "verify"])

    def test_boolean_verification_not_accepted(self):
        with self.assertRaises(CanonicalXrefBlocked):
            self.invoke(verify_event_and_acl=lambda **_: True)

    def test_mismatched_actor_or_tenant_or_ticket_blocks(self):
        for field, value in (("actor", "other"), ("tenant_id", "other"),
                             ("ticket_id", "202"), ("association_count", True),
                             ("association_state", "PENDING")):
            with self.subTest(field=field):
                self.claims[field] = value
                with self.assertRaises(CanonicalXrefBlocked):
                    self.invoke()
                self.claims[field] = dict(actor="operator-a", tenant_id="tenant-a",
                    ticket_id="201", association_count=1,
                    association_state="ACTIVE")[field]

    def test_invalid_actor_and_tenant_rejected_before_signed_event_fetch(self):
        for changes in ({"actor": "operator" + chr(10) + "admin"},
                        {"tenant_id": "tenant" + chr(0) + "other"},
                        {"actor": "   "},
                        {"tenant_id": "tenant" + chr(127)}):
            with self.subTest(changes=changes):
                with self.assertRaises(CanonicalXrefBlocked):
                    self.invoke(**changes)
        self.assertEqual(self.calls, [])

    def test_invalid_ticket_rejected_before_fetch(self):
        with self.assertRaises(CanonicalXrefBlocked):
            self.invoke(ticket_id="201/../../")
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
