import os
import unittest
from unittest.mock import patch

# Portal's internal HTTP client fails closed at import without an explicit test token.
os.environ.setdefault('AIOPS_INTERNAL_TOKEN', 'unit-test-only-demo-v2')
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


    def test_acme_business_story_uses_existing_portal_shell_without_calls(self):
        from portal import main as portal_main
        with (patch.object(portal_main, "_get", side_effect=AssertionError("no upstream calls")),
              patch.object(portal_main, "_runs", side_effect=AssertionError("no run calls"))):
            response = portal_main.demo_business_story()
        page = response.body.decode("utf-8")
        self.assertEqual(response.media_type, "text/html")
        self.assertIn('aria-label="Navigation principale"', page)
        self.assertIn('href="/demo-studio"', page)
        self.assertEqual(page.count('id="acme-step-'), 6)
        for marker in ("Payments", "ACME-SAN-FABRIC-A", "Analyst / Critic",
                       "GLPI", "SIMULATE", "HITL", "Evidence", "PROJECTED_ONLY",
                       "SIMULATED", "SOURCE-VERIFIED", "UNKNOWN"):
            self.assertIn(marker, page)
        self.assertNotIn("fetch(", page)
        self.assertNotIn('action="/api/', page)

    def test_acme_business_story_links_and_no_standalone_html(self):
        from pathlib import Path
        from portal import main as portal_main
        with (patch.object(portal_main, "_get", return_value={}),
              patch.object(portal_main, "_runs", return_value=[]),
              patch.object(portal_main, "graph_panel", return_value="")):
            self.assertIn('href="/demo-studio/business-story"', portal_main.home())
            self.assertIn('href="/demo-studio/business-story"', portal_main.demo_studio())
        self.assertFalse(Path(portal_main.__file__).with_name("acme_business_story.html").exists())
        import importlib.util
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location(
            "acme_p0_deployer_story", root / "deploy" / "deploy-acme-p0.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.classify("app/portal/main.py", "M"), "IMAGE_TRANSPORT")
        self.assertEqual(module.classify("app/portal/acme_business_story.html", "A"), "BLOCKED")


    def test_demo_studio_guides_to_existing_core_run_without_live_or_ticket(self):
        from portal import main as portal_main
        runs = [
            {"run_id": "RUN-STALE", "mode": "DEMO", "status": "RUNNING"},
            {"run_id": "RUN-LIVE", "mode": "LIVE", "status": "RESOLVED"},
            {"run_id": "RUN-BLOCKED", "mode": "DEMO", "status": "BLOCKED"},
            {"run_id": "<invalid>", "mode": "DEMO", "status": "RESOLVED"},
        ]
        with (patch.object(portal_main, "_get", return_value={}),
              patch.object(portal_main, "_runs", return_value=runs),
              patch.object(portal_main, "graph_panel", return_value=""),
              patch.object(portal_main, "post_json", side_effect=AssertionError("unexpected write"))):
            page = portal_main.demo_studio()
        self.assertIn('href="/demo-studio/run/RUN-BLOCKED"', page)
        self.assertIn('href="/timeline?run_id=RUN-BLOCKED"', page)
        self.assertNotIn('href="/demo-studio/run/RUN-LIVE"', page)
        self.assertNotIn('href="/demo-studio/run/%3Cinvalid%3E"', page)
        for path in ('href="/"', 'href="/twin"', 'href="/timeline"',
                     'href="/policy-control"', 'href="/evidence"'):
            self.assertIn(path, page)
        self.assertIn("Ticket ITSM GLPI", page)
        self.assertIn("UNKNOWN", page)
        self.assertIn("non attesté", page)

    def test_demo_studio_no_core_run_keeps_unknown_and_no_fake_deep_link(self):
        from portal import main as portal_main
        with (patch.object(portal_main, "_get", return_value={}),
              patch.object(portal_main, "_runs", return_value=[
                  {"run_id": "RUN-LIVE", "mode": "LIVE", "status": "RESOLVED"},
                  {"run_id": "bad/run", "mode": "DEMO", "status": "BLOCKED"}]),
              patch.object(portal_main, "graph_panel", return_value=""),
              patch.object(portal_main, "post_json", side_effect=AssertionError("unexpected write"))):
            page = portal_main.demo_studio()
        self.assertIn("aucun run DEMO/REPLAY/STORY valide", page)
        self.assertNotIn('href="/demo-studio/run/RUN-LIVE"', page)
        self.assertNotIn('href="/demo-studio/run/bad', page)


    def test_demo_studio_links_real_incident_state_from_core_without_status_alias(self):
        from portal import main as portal_main
        runs = [{"run_id": "RUN-ACME", "incident_id": "INC-ACME",
                 "mode": "DEMO", "status": "BLOCKED"}]
        def source(path, base=None):
            if path == "/api/incidents":
                return {"items": [{"incident_id": "INC-ACME",
                    "title": "SAN & Payments <test>", "severity": "P1",
                    "state": "OPEN", "status": "CLOSED"}]}
            return {}
        with (patch.object(portal_main, "_get", side_effect=source),
              patch.object(portal_main, "_runs", return_value=runs),
              patch.object(portal_main, "graph_panel", return_value=""),
              patch.object(portal_main, "post_json",
                           side_effect=AssertionError("unexpected write"))):
            page = portal_main.demo_studio()
        self.assertIn('href="/runs"', page)
        self.assertIn('href="/demo-studio/run/RUN-ACME"', page)
        self.assertIn("état incident OPEN", page)
        self.assertNotIn("état incident CLOSED", page)
        self.assertIn("SAN &amp; Payments &lt;test&gt;", page)
        self.assertNotIn("SAN & Payments <test>", page)
        self.assertIn("Corrélation SAN → Payments : UNKNOWN", page)

    def test_demo_studio_refuses_mismatched_or_missing_incident_identity(self):
        from portal import main as portal_main
        runs = [{"run_id": "RUN-ACME", "incident_id": "INC-ACME",
                 "mode": "DEMO", "status": "RESOLVED"}]
        def source(path, base=None):
            if path == "/api/incidents":
                return {"items": [{"incident_id": "INC-OTHER",
                                   "title": "Secret unrelated incident",
                                   "state": "OPEN"}]}
            return {}
        with (patch.object(portal_main, "_get", side_effect=source),
              patch.object(portal_main, "_runs", return_value=runs),
              patch.object(portal_main, "graph_panel", return_value="")):
            page = portal_main.demo_studio()
        self.assertIn("Incident Core associé :</strong> UNKNOWN", page)
        self.assertNotIn("Secret unrelated incident", page)
        self.assertNotIn("état incident OPEN", page)


    def test_runs_page_deep_links_only_unambiguous_demo_runs(self):
        from portal import main as portal_main
        records = [
            {"run_id": "RUN-OK", "mode": "DEMO", "status": "BLOCKED"},
            {"run_id": "RUN-REPLAY", "mode": "REPLAY", "status": "RESOLVED"},
            {"run_id": "RUN-LIVE", "mode": "LIVE", "status": "RESOLVED"},
            {"run_id": "bad/<id>", "mode": "DEMO", "status": "BLOCKED"},
            {"run_id": "RUN-DUP", "mode": "STORY", "status": "BLOCKED"},
            {"run_id": "RUN-DUP", "mode": "STORY", "status": "RESOLVED"},
        ]
        with patch.object(portal_main, "_runs", return_value=records):
            page = portal_main.runs_page()
        self.assertIn('href="/demo-studio/run/RUN-OK"', page)
        self.assertIn('href="/timeline?run_id=RUN-OK"', page)
        self.assertIn('href="/demo-studio/run/RUN-REPLAY"', page)
        self.assertNotIn('href="/demo-studio/run/RUN-LIVE"', page)
        self.assertNotIn('href="/demo-studio/run/RUN-DUP"', page)
        self.assertNotIn('href="/demo-studio/run/bad', page)
        self.assertIn('bad/&lt;id&gt;', page)  # Registry row is escaped, never linked.
        self.assertNotIn('bad/<id>', page)
        self.assertIn("RUN-LIVE", page)  # Inventory remains visible, not a DEMO deep link.

    def test_runs_page_without_qualified_demo_link_is_explicit_unknown(self):
        from portal import main as portal_main
        with patch.object(portal_main, "_runs", return_value=[
                {"run_id": "RUN-LIVE", "mode": "LIVE", "status": "RESOLVED"}]):
            page = portal_main.runs_page()
        self.assertIn("aucun run DEMO non ambigu accessible", page)
        self.assertNotIn('href="/demo-studio/run/', page)


    def test_timeline_default_prefers_terminal_demo_over_old_running_or_live(self):
        from portal import main as portal_main
        runs = [
            {"run_id": "RUN-OLD", "mode": "DEMO", "status": "RUNNING"},
            {"run_id": "RUN-LIVE", "mode": "LIVE", "status": "RESOLVED"},
            {"run_id": "RUN-DUP", "mode": "DEMO", "status": "RESOLVED"},
            {"run_id": "RUN-DUP", "mode": "DEMO", "status": "BLOCKED"},
            {"run_id": "RUN-BLOCKED", "mode": "DEMO", "status": "BLOCKED"},
        ]
        seen = []
        def source(path, base=None):
            seen.append(path)
            if path == "/api/incidents":
                return {"items": []}
            if path == "/api/runs/RUN-BLOCKED":
                return {"run": {"run_id": "RUN-BLOCKED", "mode": "DEMO",
                                "status": "BLOCKED"}, "events": []}
            if path == "/api/runs/RUN-BLOCKED/evidence":
                return {"items": []}
            return {}
        with (patch.object(portal_main, "_runs", return_value=runs),
              patch.object(portal_main, "_get", side_effect=source),
              patch.object(portal_main, "post_json",
                           side_effect=AssertionError("unexpected write"))):
            page = portal_main.timeline_page()
        self.assertIn("Run sélectionné : RUN-BLOCKED", page)
        self.assertIn('href="/demo-studio/run/RUN-BLOCKED"', page)
        self.assertIn("/api/runs/RUN-BLOCKED", seen)
        self.assertFalse(any("/api/runs/RUN-OLD" in p or
                             "/api/runs/RUN-LIVE" in p or
                             "/api/runs/RUN-DUP" in p for p in seen))

    def test_timeline_without_unambiguous_demo_run_keeps_unknown(self):
        from portal import main as portal_main
        runs = [
            {"run_id": "RUN-LIVE", "mode": "LIVE", "status": "RESOLVED"},
            {"run_id": "RUN-DUP", "mode": "STORY", "status": "BLOCKED"},
            {"run_id": "RUN-DUP", "mode": "STORY", "status": "RESOLVED"},
        ]
        seen = []
        def source(path, base=None):
            seen.append(path)
            return {"items": []}
        with (patch.object(portal_main, "_runs", return_value=runs),
              patch.object(portal_main, "_get", side_effect=source)):
            page = portal_main.timeline_page()
        self.assertIn("aucun run DEMO / REPLAY / STORY non ambigu", page)
        self.assertFalse(any(p.startswith("/api/runs/") for p in seen))


    def test_demo_studio_links_only_unique_core_demo_ids(self):
        from portal import main as portal_main
        records = [
            {"run_id": "RUN-DUP", "mode": "DEMO", "status": "BLOCKED"},
            {"run_id": "RUN-DUP", "mode": "LIVE", "status": "RESOLVED"},
            {"run_id": "RUN-OK", "mode": "STORY", "status": "RESOLVED"},
        ]
        with (patch.object(portal_main, "_runs", return_value=records),
              patch.object(portal_main, "_get", return_value={}),
              patch.object(portal_main, "graph_panel", return_value="")):
            page = portal_main.demo_studio()
        self.assertIn('href="/demo-studio/run/RUN-OK"', page)
        self.assertIn('href="/timeline?run_id=RUN-OK"', page)
        self.assertNotIn('href="/demo-studio/run/RUN-DUP"', page)
        self.assertNotIn('href="/timeline?run_id=RUN-DUP"', page)

    def test_timeline_explicit_live_or_ambiguous_run_refused(self):
        from fastapi import HTTPException
        from portal import main as portal_main
        records = [
            {"run_id": "RUN-LIVE", "mode": "LIVE", "status": "RESOLVED"},
            {"run_id": "RUN-DUP", "mode": "DEMO", "status": "BLOCKED"},
            {"run_id": "RUN-DUP", "mode": "STORY", "status": "RESOLVED"},
        ]
        def source(path, base=None):
            if path == "/api/incidents":
                return {"items": []}
            raise AssertionError("unexpected run detail read: " + path)
        with (patch.object(portal_main, "_runs", return_value=records),
              patch.object(portal_main, "_get", side_effect=source)):
            for rid in ("RUN-LIVE", "RUN-DUP"):
                with self.subTest(rid=rid), self.assertRaises(HTTPException) as ctx:
                    portal_main.timeline_page(run_id=rid)
                self.assertEqual(ctx.exception.status_code, 404)

    def test_detail_and_poll_refuse_ambiguous_core_identity_before_read(self):
        from fastapi import HTTPException
        from portal import main as portal_main
        records = [
            {"run_id": "RUN-DUP", "mode": "DEMO", "status": "BLOCKED"},
            {"run_id": "RUN-DUP", "mode": "DEMO", "status": "RESOLVED"},
        ]
        with (patch.object(portal_main, "_runs", return_value=records),
              patch.object(portal_main, "_get",
                           side_effect=AssertionError("no detail/gate read allowed"))):
            for endpoint in (portal_main.demo_run_detail, portal_main.demo_status):
                with self.subTest(endpoint=endpoint.__name__), self.assertRaises(HTTPException) as ctx:
                    endpoint("RUN-DUP")
                self.assertEqual(ctx.exception.status_code, 404)


    def test_detail_and_poll_hide_foreign_core_run_before_gates(self):
        from portal import main as portal_main
        foreign = {"run": {"run_id": "RUN-OTHER", "mode": "DEMO",
                           "status": "RESOLVED"},
                   "events": [{"stage": "FOREIGN-EVENT"}]}
        seen = []
        def source(path, base=None):
            seen.append(path)
            if path == "/api/runs/RUN-SELECTED":
                return foreign
            raise AssertionError("no foreign gate/evidence reads: " + path)
        with (patch.object(portal_main, "_runs", return_value=[
                  {"run_id": "RUN-SELECTED", "mode": "DEMO", "status": "BLOCKED"}]),
              patch.object(portal_main, "_get", side_effect=source)):
            page = portal_main.demo_run_detail("RUN-SELECTED")
            self.assertEqual(page.status_code, 503)
            self.assertIn("UNKNOWN", page.body.decode("utf-8"))
            self.assertNotIn("FOREIGN-EVENT", page.body.decode("utf-8"))
            status = portal_main.demo_status("RUN-SELECTED")
            self.assertEqual(status["status"], "UNKNOWN")
            self.assertEqual(status["events"], "INCONNU")
        self.assertEqual(seen, ["/api/runs/RUN-SELECTED"] * 2)

    def test_timeline_hides_foreign_core_detail_before_evidence(self):
        from portal import main as portal_main
        seen = []
        def source(path, base=None):
            seen.append(path)
            if path == "/api/incidents":
                return {"items": []}
            if path == "/api/runs/RUN-SELECTED":
                return {"run": {"run_id": "RUN-SELECTED", "mode": "LIVE"},
                        "events": [{"stage": "FOREIGN-EVENT"}]}
            raise AssertionError("no foreign evidence read: " + path)
        with (patch.object(portal_main, "_runs", return_value=[
                  {"run_id": "RUN-SELECTED", "mode": "DEMO", "status": "BLOCKED"}]),
              patch.object(portal_main, "_get", side_effect=source)):
            page = portal_main.timeline_page(run_id="RUN-SELECTED")
        self.assertIn("Timeline Core — UNKNOWN", page)
        self.assertNotIn("FOREIGN-EVENT", page)
        self.assertEqual(seen, ["/api/incidents", "/api/runs/RUN-SELECTED"])

    def test_core_detail_must_match_incident_and_scenario_when_listed(self):
        from portal import main as portal_main
        listed = {"run_id": "RUN-A", "mode": "DEMO",
                  "incident_id": "INC-A", "scenario_id": "SCN-A"}
        for field, value in (("incident_id", "INC-B"),
                             ("scenario_id", "SCN-B")):
            with self.subTest(field=field):
                detail = {"run": {**listed, field: value}, "events": []}
                self.assertFalse(portal_main._core_detail_matches_listed_run(detail, listed))
        self.assertTrue(portal_main._core_detail_matches_listed_run(
            {"run": listed, "events": []}, listed))

if __name__ == "__main__":
    unittest.main()
