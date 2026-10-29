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
                       "Observations synthétiques", "source non vérifiée ou indisponible"):
            self.assertIn(marker, page)

    def test_unverified_policy_envelope_never_displays_spoofed_gate(self):
        forged = {"stage": "POLICY", "state": "PASS",
                  "decision": "SPOOFED-UNVERIFIED-GATE"}
        for gates in (
            {"status": "UNKNOWN", "items": [forged]},
            {"status": "UNKNOWN", "error_type": "HTTPError",
             "http_status": 401, "items": [forged]},
            {"error_type": "ConnectionError", "items": [forged]},
            {"items": [None, forged]},
            {"items": {"stage": "POLICY", "decision": "SPOOFED-UNVERIFIED-GATE"}},
        ):
            with self.subTest(gates=gates):
                page = render_demo_v2(
                    {"run": {"run_id": "RUN-DEMO", "mode": "DEMO"},
                     "events": []}, {}, gates)
                self.assertNotIn("SPOOFED-UNVERIFIED-GATE", page)
                self.assertIn("INCONNU — décisions Policy non vérifiables", page)
                self.assertIn("INCONNU — décisions Policy indisponibles", page)

    def test_verified_policy_list_remains_visible_in_read_only_view(self):
        page = render_demo_v2(
            {"run": {"run_id": "RUN-DEMO", "mode": "DEMO"}, "events": []},
            {}, {"items": [{"stage": "POLICY", "state": "PASS",
                            "decision": "SIMULATE", "reason": "synthetic only"}]})
        self.assertIn("SIMULATE", page)
        self.assertIn("synthetic only", page)
        self.assertIn("DISPONIBLE — données reçues (non attestées)", page)

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
            {"sequence": 1, "occurred_at": "2026-10-28T19:55:00Z"}]}, {}, {}, now=now)
        self.assertNotIn("statut RUNNING ancien à requalifier", fresh)
        stale = render_demo_v2({"run": run, "events": [
            {"sequence": 1, "occurred_at": "2026-10-28T18:00:00Z"}]}, {}, {}, now=now)
        self.assertIn("statut RUNNING ancien à requalifier", stale)
        self.assertIn("ne prouve ni un blocage", stale)

    def test_invalid_or_future_event_time_fails_closed(self):
        now = datetime(2026, 10, 28, 20, 0, tzinfo=timezone.utc)
        run = {"status": "RUNNING", "started_at": "2026-10-21T12:00:00Z"}
        for event in ({"sequence": 1, "occurred_at": "2026-10-29T00:00:00Z"},
                      {"sequence": 1, "occurred_at": "invalid"},
                      {"sequence": 1, "stage": "RUN"}):
            with self.subTest(event=event):
                page = render_demo_v2({"run": run, "events": [event]}, {}, {}, now=now)
                self.assertIn("Fraîcheur RUNNING — INCONNU", page)
                self.assertNotIn("statut RUNNING ancien à requalifier", page)

    def test_missing_events_or_future_start_cannot_prove_staleness(self):
        now = datetime(2026, 10, 28, 20, 0, tzinfo=timezone.utc)
        missing = render_demo_v2({"run": {"status": "RUNNING",
            "started_at": "2026-10-21T12:00:00Z"}}, {}, {}, now=now)
        self.assertNotIn("statut RUNNING ancien à requalifier", missing)
        self.assertIn("Fraîcheur RUNNING — INCONNU", missing)
        future = render_demo_v2({"run": {"status": "RUNNING",
            "started_at": "2026-10-29T12:00:00Z"}, "events": []}, {}, {}, now=now)
        self.assertIn("horodatage Core futur", future)
        self.assertNotIn("Démarré récemment", future)
        self.assertNotIn("statut RUNNING ancien à requalifier", future)

    def test_canonical_sequence_order_is_visible_even_if_transport_shuffles(self):
        now = datetime(2026, 10, 28, 20, 0, tzinfo=timezone.utc)
        events = [
            {"sequence": 2, "occurred_at": "2026-10-28T19:10:00Z", "event_type": "EVT-LATER"},
            {"sequence": 1, "occurred_at": "2026-10-28T19:00:00Z", "event_type": "EVT-FIRST"},
        ]
        page = render_demo_v2({"run": {"run_id": "RUN-1", "mode": "DEMO"},
                               "events": events}, {}, {}, now=now)
        self.assertLess(page.index("EVT-FIRST"), page.index("EVT-LATER"))
        self.assertIn("COHÉRENT — ordre par séquence Core", page)
        self.assertIn("non attesté indépendamment", page)

    def test_duplicate_gap_and_invalid_sequence_fail_closed_on_running(self):
        now = datetime(2026, 10, 28, 20, 0, tzinfo=timezone.utc)
        def event(seq):
            return {"sequence": seq, "occurred_at": "2026-10-28T18:00:00Z",
                    "event_type": "DEMO"}
        cases = [
            [event(1), event(1)],
            [event(1), event(3)],
            [event(True)],
            [event("1")],
            [event(0)],
            [{"occurred_at": "2026-10-28T18:00:00Z"}],
        ]
        for events in cases:
            with self.subTest(events=events):
                page = render_demo_v2({"run": {"status": "RUNNING",
                    "started_at": "2026-10-21T12:00:00Z"},
                    "events": events}, {}, {}, now=now)
                self.assertIn("Intégrité de la chronologie", page)
                self.assertIn("Fraîcheur RUNNING — INCONNU", page)
                self.assertNotIn("statut RUNNING ancien à requalifier", page)

    def test_backward_core_clock_does_not_prove_stale_running(self):
        now = datetime(2026, 10, 28, 20, 0, tzinfo=timezone.utc)
        page = render_demo_v2({"run": {"status": "RUNNING",
            "started_at": "2026-10-21T12:00:00Z"},
            "events": [
                {"sequence": 1, "occurred_at": "2026-10-28T18:30:00Z"},
                {"sequence": 2, "occurred_at": "2026-10-28T18:00:00Z"},
            ]}, {}, {}, now=now)
        self.assertIn("horodatages Core non monotones", page)
        self.assertIn("Fraîcheur RUNNING — INCONNU", page)
        self.assertNotIn("statut RUNNING ancien à requalifier", page)

    def test_old_running_without_events_does_not_claim_staleness(self):
        page = render_demo_v2(
            {"run": {"status": "RUNNING",
                     "started_at": "2026-10-21T13:21:01+00:00"},
             "events": []}, {}, {"items": []})
        self.assertIn("Fraîcheur RUNNING — INCONNU", page)
        self.assertIn("Intégrité de la chronologie", page)
        self.assertNotIn("statut RUNNING ancien à requalifier", page)

    def test_truncated_first_sequence_is_unknown_even_with_old_events(self):
        now = datetime(2026, 10, 28, 20, 0, tzinfo=timezone.utc)
        page = render_demo_v2({"run": {"status": "RUNNING",
            "started_at": "2026-10-21T12:00:00Z"}, "events": [
                {"sequence": 2, "occurred_at": "2026-10-28T18:00:00Z", "event_type": "EVT-2"},
                {"sequence": 3, "occurred_at": "2026-10-28T18:05:00Z", "event_type": "EVT-3"},
            ]}, {}, {}, now=now)
        self.assertIn("sans première séquence", page)
        self.assertIn("Fraîcheur RUNNING — INCONNU", page)
        self.assertNotIn("COHÉRENT — ordre par séquence Core", page)
        self.assertNotIn("statut RUNNING ancien à requalifier", page)

    def test_missing_events_payload_is_unknown_not_stale(self):
        now = datetime(2026, 10, 28, 20, 0, tzinfo=timezone.utc)
        page = render_demo_v2({"run": {"status": "RUNNING",
            "started_at": "2026-10-21T12:00:00Z"}}, {}, {}, now=now)
        self.assertIn("Fraîcheur RUNNING — INCONNU", page)
        self.assertIn("événements Core indisponibles", page)
        self.assertNotIn("statut RUNNING ancien à requalifier", page)


if __name__ == "__main__":
    unittest.main()
