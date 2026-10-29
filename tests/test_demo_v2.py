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

    def test_synthetic_stage_markers_are_not_attestations(self):
        page = render_demo_v2(
            {"run": {"run_id": "RUN-SYN", "mode": "DEMO", "status": "RESOLVED"},
             "events": [{"sequence": 1, "stage": "POLICY",
                         "event_type": "STAGE_COMPLETED", "status": "PASS",
                         "payload": {"synthetic": True}},
                        {"sequence": 2, "stage": "HITL",
                         "event_type": "STAGE_COMPLETED", "status": "PASS",
                         "payload": {"synthetic": True}},
                        {"sequence": 3, "stage": "REMEDIATE",
                         "event_type": "STAGE_COMPLETED", "status": "PASS",
                         "payload": {"synthetic": True}},
                        {"sequence": 4, "stage": "VERIFY",
                         "event_type": "STAGE_COMPLETED", "status": "PASS",
                         "payload": {"synthetic": True}}]}, {}, {})
        for warning in ("Étapes DEMO", "validation non attestée",
                        "approbation humaine GLPI", "remédiation effectuée",
                        "PASS/SIMULATE", "RESOLVED n'atteste"):
            self.assertIn(warning, page)
        # Do not falsify the Core event itself: its original PASS stays visible.
        self.assertIn("STAGE_COMPLETED", page)

    def test_no_attestation_warning_for_unrelated_events(self):
        page = render_demo_v2(
            {"run": {"run_id": "RUN-N", "mode": "DEMO", "status": "BLOCKED"},
             "events": [{"stage": "NORMALIZE", "event_type": "STAGE_COMPLETED",
                         "status": "PASS", "payload": {"synthetic": True}}]}, {}, {})
        self.assertNotIn("Étapes DEMO — validation non attestée", page)

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


    def test_demo_route_renders_synthetic_policy_warning(self):
        from portal import main as portal_main
        def source(path, base=None):
            if path == "/api/runs/RUN-ROUTE":
                return {"run": {"run_id": "RUN-ROUTE", "mode": "DEMO", "status": "RESOLVED"},
                        "events": [{"sequence": 1, "stage": "POLICY",
                                    "event_type": "STAGE_COMPLETED", "status": "PASS",
                                    "payload": {"synthetic": True}}]}
            if path == "/api/runs/RUN-ROUTE/gates":
                return {"items": []}
            raise AssertionError(path)
        with patch.object(portal_main, "_runs", return_value=[
                {"run_id": "RUN-ROUTE", "mode": "DEMO"}]), \
             patch.object(portal_main, "_get", side_effect=source):
            page = portal_main.demo_run_detail("RUN-ROUTE")
        self.assertIn("Étapes DEMO — validation non attestée", page)
        self.assertIn("POLICY ne prouve pas", page)
        self.assertIn("STAGE_COMPLETED", page)

    def test_demo_route_does_not_invent_stage_warning(self):
        from portal import main as portal_main
        def source(path, base=None):
            if path == "/api/runs/RUN-ROUTE":
                return {"run": {"run_id": "RUN-ROUTE", "mode": "DEMO", "status": "BLOCKED"},
                        "events": [{"stage": "NORMALIZE", "event_type": "STAGE_COMPLETED",
                                    "status": "PASS"}]}
            if path == "/api/runs/RUN-ROUTE/gates":
                return {"status": "UNKNOWN"}
            raise AssertionError(path)
        with patch.object(portal_main, "_runs", return_value=[
                {"run_id": "RUN-ROUTE", "mode": "DEMO"}]), \
             patch.object(portal_main, "_get", side_effect=source):
            page = portal_main.demo_run_detail("RUN-ROUTE")
        self.assertNotIn("Étapes DEMO — validation non attestée", page)

if __name__ == "__main__":
    unittest.main()
