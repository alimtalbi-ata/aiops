import unittest
from unittest.mock import patch
from portal.demo_v2 import render_demo_v2


class DemoV2Tests(unittest.TestCase):
    def test_canonical_events_and_policy(self):
        page = render_demo_v2(
            {"run": {"run_id": "RUN-1", "mode": "DEMO", "status": "RESOLVED"},
             "events": [{"sequence": 1, "stage": "NORMALIZE",
                         "event_type": "STAGE_COMPLETED", "status": "PASS",
                         "payload": {"synthetic": True}, "evidence_ids": ["EVD-1"]}]},
            {"status": "UNKNOWN", "error_type": "HTTPError"},
            {"items": [{"stage": "POLICY", "state": "PASS",
                        "decision": "SIMULATE", "reason": "no production mutation"}]})
        for marker in ("Mission Control V2", "EVD-1", "SIMULATE",
                       "Observations synthétiques", "accès ou API en erreur"):
            self.assertIn(marker, page)

    def test_missing_data_not_fabricated(self):
        page = render_demo_v2({"run": {"status": "BLOCKED"}}, {}, {})
        self.assertIn("INCONNU", page)
        self.assertNotIn("EVD-1", page)

    def test_html_escaping(self):
        payload = '<img src=x onerror=alert(1)>'
        page = render_demo_v2({"run": {"run_id": payload},
                               "events": [{"stage": payload}]}, {}, {})
        self.assertNotIn(payload, page)
        self.assertIn("&lt;img", page)

    def test_old_running_marked_for_requalification(self):
        page = render_demo_v2(
            {"run": {"status": "RUNNING",
                     "started_at": "2026-10-21T13:21:01+00:00"},
             "events": []}, {}, {"items": []})
        self.assertIn("potentiellement bloquée", page)


if __name__ == "__main__":
    unittest.main()
