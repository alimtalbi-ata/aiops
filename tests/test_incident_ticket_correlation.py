"""Offline identity-join tests; no GLPI, Core, ACL or runtime integration."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.incident_ticket_correlation import correlate_incident_run_ticket


class IncidentTicketCorrelationTests(unittest.TestCase):
    def setUp(self):
        self.incident = {"incident_id": "INC-1", "tenant_id": "TEN-1"}
        self.run = {"run_id": "RUN-1", "incident_id": "INC-1",
                    "tenant_id": "TEN-1", "mode": "DEMO"}
        self.ticket = {"ticket_id": "GLPI-1", "incident_id": "INC-1",
                       "run_id": "RUN-1", "tenant_id": "TEN-1"}

    def join(self, **kwargs):
        return correlate_incident_run_ticket(self.incident, self.run, self.ticket, **kwargs)

    def test_missing_acl_fails_closed(self):
        result = self.join()
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertEqual(result["reason"], "ACTOR_TENANT_ACL_REQUIRED")
        self.assertFalse(result["tenant_acl_qualified"])

    def test_exact_synthetic_identity_only_unattested(self):
        result = self.join(actor_acl_qualified=True)
        self.assertEqual(result["state"], "MATCHED_UNATTESTED")
        self.assertTrue(result["incident_run_match"])
        self.assertTrue(result["ticket_run_match"])
        self.assertFalse(result["runtime_attested"])
        self.assertFalse(result["tenant_acl_qualified"])
        self.assertFalse(result["live_remediation_authorized"])
        self.assertNotIn("ticket_id", result)

    def test_cross_tenant_fails_closed(self):
        self.ticket["tenant_id"] = "TEN-2"
        result = self.join(actor_acl_qualified=True)
        self.assertEqual(result["reason"], "TENANT_MISMATCH")
        self.assertEqual(result["state"], "UNKNOWN")

    def test_mismatched_run_and_ticket_fails_closed(self):
        self.ticket["run_id"] = "RUN-2"
        result = self.join(actor_acl_qualified=True)
        self.assertEqual(result["reason"], "IDENTITY_MISMATCH")
        self.assertFalse(result["ticket_run_match"])

    def test_live_mode_refused(self):
        self.run["mode"] = "LIVE"
        result = self.join(actor_acl_qualified=True)
        self.assertEqual(result["reason"], "LIVE_OR_UNKNOWN_MODE_REFUSED")

    def test_invalid_identifiers_rejected(self):
        for bad in ("", "../x", "abc/def", "a" * 129, None, 42):
            with self.subTest(bad=bad):
                self.ticket["ticket_id"] = bad
                result = self.join(actor_acl_qualified=True)
                self.assertEqual(result["reason"], "INVALID_OR_MISSING_IDENTITY")


if __name__ == "__main__":
    unittest.main()
