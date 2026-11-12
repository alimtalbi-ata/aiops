import unittest
from app.core.fs364_ticket147_correlation import qualify_link

ALERT = {"fingerprint": "alert-fs-lab-20261106", "status": "firing", "mode": "DEMO"}
RUN = {"run_id": "RUN-4FABD1786F107E51", "incident_id": "INC-DEMO-FS-001",
       "alert_fingerprint": ALERT["fingerprint"], "glpi_ticket_id": 147,
       "mode": "DEMO", "live_effects": False}
EVIDENCE = {"evidence_id": "EVD-D2069BA816126499", "run_id": RUN["run_id"],
            "incident_id": RUN["incident_id"], "alert_fingerprint": ALERT["fingerprint"],
            "glpi_ticket_id": 147, "mode": "DEMO", "live_effects": False}
TICKET = {"id": 147, "reference": "AIOPS2-REAL-FS-20261106"}


class CorrelationTests(unittest.TestCase):
    def test_read_only_correlated(self):
        result = qualify_link(ALERT, RUN, EVIDENCE, TICKET)
        self.assertEqual(result["status"], "CORRELATED_READ_ONLY")
        self.assertFalse(result["can_execute"])
        self.assertFalse(result["can_resolve"])

    def test_wrong_ticket_and_historical_approval_cannot_pass(self):
        for bad in ({"id": 146, "reference": TICKET["reference"], "validation": "ACCEPTED"},
                    {"id": True, "reference": TICKET["reference"]},
                    {"id": 147, "reference": "old"}):
            self.assertNotEqual(qualify_link(ALERT, RUN, EVIDENCE, bad)["status"], "CORRELATED_READ_ONLY")

    def test_mismatched_run_or_evidence(self):
        for change in ({"run_id": "RUN-0000000000000000"},
                       {"alert_fingerprint": "other-fingerprint"},
                       {"glpi_ticket_id": 146}):
            self.assertEqual(qualify_link(ALERT, RUN, {**EVIDENCE, **change}, TICKET)["status"], "BLOCKED")

    def test_no_alert_or_live(self):
        self.assertEqual(qualify_link({**ALERT, "status": "resolved"}, RUN, EVIDENCE, TICKET)["status"], "BLOCKED")
        self.assertEqual(qualify_link(ALERT, {**RUN, "mode": "LIVE"}, EVIDENCE, TICKET)["status"], "BLOCKED")
        self.assertEqual(qualify_link(ALERT, RUN, {**EVIDENCE, "live_effects": 0}, TICKET)["status"], "BLOCKED")

    def test_absent_or_invalid_inputs(self):
        for value in (None, [], {}, "147"):
            self.assertEqual(qualify_link(ALERT, RUN, value, TICKET)["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
