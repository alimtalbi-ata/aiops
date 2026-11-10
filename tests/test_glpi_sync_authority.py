"""Offline contract tests; no GLPI network, database, or ticket mutations."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from shared.glpi_sync_authority import authorize_existing_ticket_update


class GLPISyncAuthorityTests(unittest.TestCase):
    def setUp(self):
        identity = dict(
            tenant_id="tenant-demo", glpi_instance_id="glpi-ci",
            glpi_entity_id="7", ticket_id="201",
            incident_id="INC-FS1250-AUTOGLPI-625916362ACD42C9",
            run_id="RUN-8CA56A39E58944F1",
        )
        self.core = dict(identity, mode="DEMO", execution_allowed=False,
                         core_run_readback_verified=True,
                         tenant_acl_verified=True, actor_acl_verified=True,
                         association_state="ACTIVE", association_count=1)
        self.glpi = dict(identity, glpi_ticket_readback_verified=True,
                         matching_ticket_count=1)

    def test_exact_existing_identity_can_pass_precondition(self):
        self.assertEqual(
            authorize_existing_ticket_update(self.core, self.glpi)["ticket_id"], "201"
        )

    def test_missing_or_unverified_evidence_fails_closed(self):
        for field, value in (
            ("core_run_readback_verified", False),
            ("tenant_acl_verified", False),
            ("actor_acl_verified", False),
            ("association_state", "REVOKED"),
            ("association_count", 2),
            ("execution_allowed", True),
            ("mode", "LIVE"),
        ):
            with self.subTest(field=field):
                core = copy.deepcopy(self.core)
                core[field] = value
                with self.assertRaises(ValueError):
                    authorize_existing_ticket_update(core, self.glpi)
        for field, value in (
            ("glpi_ticket_readback_verified", False),
            ("matching_ticket_count", 2),
        ):
            with self.subTest(field=field):
                glpi = copy.deepcopy(self.glpi)
                glpi[field] = value
                with self.assertRaises(ValueError):
                    authorize_existing_ticket_update(self.core, glpi)

    def test_cross_tenant_entity_run_ticket_and_instance_fail_closed(self):
        for field, value in (
            ("tenant_id", "other-tenant"),
            ("glpi_instance_id", "other-instance"),
            ("glpi_entity_id", "8"),
            ("ticket_id", "202"),
            ("incident_id", "INC-OTHER-1234"),
            ("run_id", "RUN-AAAAAAAA"),
        ):
            with self.subTest(field=field):
                glpi = copy.deepcopy(self.glpi)
                glpi[field] = value
                with self.assertRaises(ValueError):
                    authorize_existing_ticket_update(self.core, glpi)

    def test_absent_identity_and_untrusted_payload_fail_closed(self):
        for field in ("tenant_id", "glpi_entity_id", "ticket_id", "run_id"):
            with self.subTest(field=field):
                glpi = copy.deepcopy(self.glpi)
                del glpi[field]
                with self.assertRaises(ValueError):
                    authorize_existing_ticket_update(self.core, glpi)
        with self.assertRaises(ValueError):
            authorize_existing_ticket_update(self.core, {"ticket_id": "201"})


if __name__ == "__main__":
    unittest.main()
