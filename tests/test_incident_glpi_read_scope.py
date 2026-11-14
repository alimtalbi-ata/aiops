"""Security regression tests for the offline read-scope restriction."""
import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.incident_glpi_read_scope import VerifiedReadScope, evaluate_ticket_read_scope


class IncidentGlpiReadScopeTests(unittest.TestCase):
    def setUp(self):
        self.scope = VerifiedReadScope(
            actor_id="actor-1", tenant_id="tenant-A", glpi_entity_id="entity-7",
            permitted_incident_ids=frozenset({"INC-1"}),
        )
        self.record = dict(tenant_id="tenant-A", glpi_entity_id="entity-7",
                           incident_id="INC-1", mode="DEMO")

    def check(self, scope=None, **changes):
        return evaluate_ticket_read_scope(
            self.scope if scope is None else scope,
            **(self.record | changes),
        )

    def test_matching_scope_is_never_runtime_or_write_authorization(self):
        result = self.check()
        self.assertEqual(result["state"], "SCOPE_MATCH_UNATTESTED")
        self.assertTrue(result["read_scope_match"])
        self.assertFalse(result["runtime_attested"])
        self.assertFalse(result["live_remediation_authorized"])
        self.assertFalse(result["glpi_write_enabled"])
        self.assertNotIn("tenant_id", result)
        self.assertNotIn("incident_id", result)

    def test_no_scope_and_untrusted_dictionary_refused(self):
        for scope in (None, {}, {"actor_id": "actor-1"}, "admin"):
            with self.subTest(scope=scope):
                result = evaluate_ticket_read_scope(scope, **self.record)
                self.assertEqual(result["reason"], "SERVER_AUTHORIZATION_REQUIRED")
                self.assertFalse(result["read_scope_match"])

    def test_cross_tenant_entity_and_incident_refused(self):
        for changes in ({"tenant_id": "tenant-B"}, {"glpi_entity_id": "entity-8"},
                        {"incident_id": "INC-2"}):
            with self.subTest(changes=changes):
                self.assertEqual(self.check(**changes)["state"], "DENIED")

    def test_live_and_unknown_modes_refused(self):
        for mode in ("LIVE", "live", "", None, True, "DEMO\\n"):
            with self.subTest(mode=mode):
                result = self.check(mode=mode)
                self.assertEqual(result["reason"], "LIVE_OR_UNKNOWN_MODE_REFUSED")

    def test_malformed_identity_and_scope_refused(self):
        self.assertEqual(self.check(incident_id="INC-1\\n")["reason"], "INVALID_IDENTITY")
        self.assertEqual(self.check(scope=replace(self.scope, actor_id=""))["reason"], "INVALID_IDENTITY")
        self.assertEqual(self.check(scope=replace(
            self.scope, permitted_incident_ids=frozenset({"INC-1", "bad id"})
        ))["reason"], "INVALID_SCOPE")

    def test_permitted_scope_is_not_sufficient_for_authentication(self):
        self.assertEqual(self.check()["reason"], "LOCAL_SCOPE_MATCH_NOT_AUTHENTICATION")


if __name__ == "__main__":
    unittest.main()
