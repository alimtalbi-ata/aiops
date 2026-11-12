"""GLPI Copilot canonical context selection offline regressions."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from shared.glpi_copilot_context_gate import select_copilot_run_context


class GLPICopilotContextGateTests(unittest.TestCase):
    def setUp(self):
        identity = dict(tenant_id="demo-tenant", glpi_instance_id="ci-glpi",
                        glpi_entity_id="2", ticket_id="17",
                        incident_id="INC-DEMO-12345678", run_id="RUN-12345678")
        self.core = dict(identity, mode="DEMO", execution_allowed=False,
                         core_run_readback_verified=True, tenant_acl_verified=True,
                         actor_acl_verified=True, association_state="ACTIVE",
                         association_count=1)
        self.glpi = dict(identity, glpi_ticket_readback_verified=True,
                         matching_ticket_count=1)

    def test_context_preserves_glpi_run_identity_without_actions(self):
        result = select_copilot_run_context(self.core, self.glpi)
        self.assertEqual(result["status"], "CANDIDATE_VERIFIED_INPUTS")
        self.assertEqual(result["run_id"], "RUN-12345678")
        self.assertEqual(result["ticket_id"], "17")
        self.assertFalse(result["proposal_created"])
        self.assertFalse(result["execution_allowed"])
        self.assertEqual(result["actions_performed"], [])

    def test_ticket_text_is_not_canonical_link(self):
        self.glpi["content"] = "RUN-12345678"
        self.glpi["run_id"] = "RUN-87654321"
        with self.assertRaises(ValueError):
            select_copilot_run_context(self.core, self.glpi)

    def test_no_readback_or_tenant_acl_blocks_copilot_context(self):
        for key, value in (("tenant_acl_verified", False),
                           ("actor_acl_verified", False),
                           ("core_run_readback_verified", False),
                           ("association_count", 0)):
            with self.subTest(key=key):
                core = dict(self.core, **{key: value})
                with self.assertRaises(ValueError):
                    select_copilot_run_context(core, self.glpi)
        with self.assertRaises(ValueError):
            select_copilot_run_context(
                self.core, dict(self.glpi, glpi_ticket_readback_verified=False))

    def test_cross_tenant_and_ambiguous_glpi_block_context(self):
        with self.assertRaises(ValueError):
            select_copilot_run_context(
                self.core, dict(self.glpi, tenant_id="another-tenant"))
        with self.assertRaises(ValueError):
            select_copilot_run_context(
                self.core, dict(self.glpi, matching_ticket_count=2))


if __name__ == "__main__":
    unittest.main()
