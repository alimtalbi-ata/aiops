import unittest
from datetime import datetime, timezone, timedelta
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

    def test_timeline_link_only_for_valid_core_id(self):
        page = render_demo_v2({"run": {"run_id": "RUN_ACME-42", "mode": "DEMO"}, "events": []}, {}, {})
        self.assertIn('href="/timeline?run_id=RUN_ACME-42"', page)
        self.assertIn('href="/runs"', page)

    def test_malicious_or_missing_run_id_never_links(self):
        for rid in ('<img src=x onerror=alert(1)>', '../other', 'RUN/1', 'x' * 129, None):
            with self.subTest(rid=rid):
                page = render_demo_v2({"run": {"run_id": rid}, "events": []}, {}, {})
                self.assertNotIn('href="/timeline?run_id=', page)
                self.assertIn("lien indisponible", page)
                self.assertNotIn('<img src=x', page)

    def test_running_freshness_uses_last_core_event_not_start_only(self):
        now = datetime(2026, 10, 28, 20, 0, tzinfo=timezone.utc)
        run = {"run_id": "RUN-1", "status": "RUNNING", "started_at": "2026-10-21T12:00:00Z"}
        fresh = render_demo_v2({"run": run, "events": [
            {"occurred_at": "2026-10-28T19:55:00Z"}]}, {}, {}, now=now)
        self.assertNotIn("statut RUNNING ancien à requalifier", fresh)
        stale = render_demo_v2({"run": run, "events": [
            {"occurred_at": "2026-10-28T18:00:00Z"}]}, {}, {}, now=now)
        self.assertIn("statut RUNNING ancien à requalifier", stale)
        self.assertIn("ne prouve ni un blocage", stale)

    def test_invalid_or_future_event_time_fails_closed(self):
        now = datetime(2026, 10, 28, 20, 0, tzinfo=timezone.utc)
        run = {"status": "RUNNING", "started_at": "2026-10-21T12:00:00Z"}
        for event in ({"occurred_at": "2026-10-29T00:00:00Z"},
                      {"occurred_at": "invalid"}, {"stage": "RUN"}):
            with self.subTest(event=event):
                page = render_demo_v2({"run": run, "events": [event]}, {}, {}, now=now)
                self.assertIn("Fraîcheur RUNNING — INCONNU", page)
                self.assertNotIn("statut RUNNING ancien à requalifier", page)

    def test_missing_events_or_future_start_cannot_prove_staleness(self):
        now = datetime(2026, 10, 28, 20, 0, tzinfo=timezone.utc)
        missing = render_demo_v2({"run": {"status": "RUNNING",
            "started_at": "2026-10-21T12:00:00Z"}}, {}, {}, now=now)
        self.assertNotIn("statut RUNNING ancien à requalifier", missing)
        future = render_demo_v2({"run": {"status": "RUNNING",
            "started_at": "2026-10-29T12:00:00Z"}, "events": []}, {}, {}, now=now)
        self.assertIn("horodatage Core futur", future)
        self.assertNotIn("Démarré récemment", future)
        self.assertNotIn("statut RUNNING ancien à requalifier", future)

    def test_old_running_marked_for_requalification(self):
        page = render_demo_v2(
            {"run": {"status": "RUNNING",
                     "started_at": "2026-10-21T13:21:01+00:00"},
             "events": []}, {}, {"items": []})
        self.assertIn("potentiellement bloquée", page)


if __name__ == "__main__":
    unittest.main()
