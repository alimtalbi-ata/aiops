"""Offline dual-readback adapter contract: no network, writes or Copilot."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from shared.glpi_copilot_readback import (
    GLPICopilotReadbackBlocked, resolve_glpi_copilot_context,
)


class DualReadbackTests(unittest.TestCase):
    def setUp(self):
        self.identity = dict(
            tenant_id="tenant-a", glpi_instance_id="ci",
            glpi_entity_id="2", ticket_id="17",
            incident_id="INC-DEMO-12345678", run_id="RUN-12345678")
        self.calls = []
        self.core = dict(self.identity, mode="DEMO", execution_allowed=False,
                         core_run_readback_verified=True, tenant_acl_verified=True,
                         actor_acl_verified=True, association_state="ACTIVE",
                         association_count=1)
        self.glpi = dict(self.identity, glpi_ticket_readback_verified=True,
                         matching_ticket_count=1)

    def resolve(self, **kwargs):
        self.calls.append(("xref", kwargs))
        return dict(self.identity)

    def core_reader(self, **kwargs):
        self.calls.append(("core", kwargs))
        return dict(self.core)

    def glpi_reader(self, **kwargs):
        self.calls.append(("glpi", kwargs))
        return dict(self.glpi)

    def invoke(self, **overrides):
        args = dict(ticket_id="17", actor="operator-a", tenant_id="tenant-a",
                    resolve_canonical_xref=self.resolve,
                    read_core_run=self.core_reader,
                    read_glpi_ticket=self.glpi_reader)
        args.update(overrides)
        return resolve_glpi_copilot_context(**args)

    def test_uninstalled_adapter_fails_before_upstream_call(self):
        with self.assertRaises(GLPICopilotReadbackBlocked):
            self.invoke(resolve_canonical_xref=None)
        self.assertEqual(self.calls, [])

    def test_canonical_dual_readback_preserves_read_only_identity(self):
        result = self.invoke()
        self.assertEqual([c[0] for c in self.calls], ["xref", "core", "glpi"])
        self.assertEqual(result["run_id"], "RUN-12345678")
        self.assertEqual(result["status"], "CANDIDATE_VERIFIED_INPUTS")
        self.assertFalse(result["execution_allowed"])
        self.assertEqual(result["actions_performed"], [])

    def test_xref_scope_mismatch_fails_before_reading_upstreams(self):
        def wrong(**kwargs):
            return dict(self.identity, tenant_id="other")
        with self.assertRaises(GLPICopilotReadbackBlocked):
            self.invoke(resolve_canonical_xref=wrong)
        self.assertEqual(self.calls, [])

    def test_core_and_glpi_must_independently_match_canonical_identity(self):
        for field, value in (("glpi_entity_id", "9"), ("ticket_id", "18"),
                             ("incident_id", "INC-OTHER-12345678"),
                             ("run_id", "RUN-87654321")):
            with self.subTest(field=field):
                self.glpi = {**self.identity, "glpi_ticket_readback_verified": True,
                             "matching_ticket_count": 1, field: value}
                with self.assertRaises(GLPICopilotReadbackBlocked):
                    self.invoke()
                self.glpi = dict(self.identity, glpi_ticket_readback_verified=True,
                                 matching_ticket_count=1)
                self.core[field] = value
                with self.assertRaises(GLPICopilotReadbackBlocked):
                    self.invoke()
                self.core[field] = self.identity[field]

    def test_no_ticket_text_inference_or_unverified_flags(self):
        self.glpi["content"] = "RUN-12345678"
        self.glpi["glpi_ticket_readback_verified"] = False
        with self.assertRaises(GLPICopilotReadbackBlocked):
            self.invoke()

    def test_invalid_ticket_rejected_before_adapter_calls(self):
        with self.assertRaises(GLPICopilotReadbackBlocked):
            self.invoke(ticket_id="17/../../admin")
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
