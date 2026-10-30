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
        for path in ('href="/"', 'href="/twin?run_id=RUN-BLOCKED"', 'href="/timeline"',
                     'href="/policy-control?run_id=RUN-BLOCKED"', 'href="/evidence"'):
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

    def test_source_status_requires_schema_and_never_infers_installation(self):
        from portal import main as portal_main
        self.assertEqual(portal_main._source_state(
            {"open_incidents": 2}, "dashboard"), "CONNECTED")
        self.assertEqual(portal_main._source_state(
            {"nodes": [], "edges": []}, "graph"), "CONNECTED")
        self.assertEqual(portal_main._source_state(
            {"nodes": []}, "graph"), "UNKNOWN")
        self.assertEqual(portal_main._source_state(
            {"status": "UNKNOWN", "error_type": "HTTPError", "http_status": 404},
            "dashboard"), "UNKNOWN")
        self.assertEqual(portal_main._source_state(
            {"status": "UNKNOWN", "error_type": "Timeout"},
            "dashboard"), "UNAVAILABLE")
        self.assertEqual(portal_main._source_state(
            {"status": "UNKNOWN", "error_type": "HTTPError", "http_status": 403},
            "dashboard"), "UNAUTHORIZED")

    def test_get_preserves_http_401_without_secret_or_upstream_url(self):
        from requests import HTTPError, Response
        from portal import main as portal_main
        response = Response()
        response.status_code = 401
        error = HTTPError("upstream auth denied", response=response)
        with patch.object(portal_main, "get_json", side_effect=error):
            result = portal_main._get("/api/dashboard")
        self.assertEqual(result, {"status": "UNKNOWN",
                                  "error_type": "HTTPError", "http_status": 401})
        self.assertEqual(portal_main._source_state(result, "dashboard"), "UNAUTHORIZED")

    def test_demo_studio_route_shows_source_states_without_claiming_glpi(self):
        from fastapi.testclient import TestClient
        from portal import main as portal_main
        def source(path, base=None):
            if path == "/api/dashboard":
                return {"status": "UNKNOWN", "error_type": "HTTPError", "http_status": 401}
            if path == "/api/twin/graph":
                return {"status": "UNKNOWN", "error_type": "ConnectionError"}
            if path == "/api/twin/impact/ACME-SAN-FABRIC-A":
                return {"root": "ACME-SAN-FABRIC-A", "affected": []}
            if path == "/api/incidents":
                return {"items": []}
            return {}
        with (patch.object(portal_main, "_get", side_effect=source),
              patch.object(portal_main, "_runs", return_value=[
                  {"run_id": "RUN-DEMO", "mode": "DEMO", "status": "BLOCKED"}]),
              patch.object(portal_main, "graph_panel", return_value=""),
              patch.object(portal_main, "post_json",
                           side_effect=AssertionError("unexpected write"))):
            response = TestClient(portal_main.app).get("/demo-studio")
        self.assertEqual(response.status_code, 200)
        for marker in ("UNAUTHORIZED", "UNAVAILABLE", "CONNECTED", "NOT_INSTALLED",
                       "UNKNOWN", "SYNTHETIC", "GLPI", "Policy / HITL"):
            self.assertIn(marker, response.text)
        self.assertIn('href="/demo-studio/run/RUN-DEMO"', response.text)
        self.assertNotIn('href="/demo-studio/run/RUN-LIVE"', response.text)
        self.assertIn("Aucun ticket_id", response.text)

    def test_run_detail_has_same_run_navigation_without_fake_ticket(self):
        from portal import main as portal_main
        def source(path, base=None):
            if path == "/api/runs/RUN-ACME":
                return {"run": {"run_id": "RUN-ACME", "mode": "DEMO",
                                "status": "BLOCKED"}, "events": []}
            if path == "/api/runs/RUN-ACME/gates":
                return {"status": "UNKNOWN"}
            raise AssertionError(path)
        with (patch.object(portal_main, "_runs", return_value=[
                  {"run_id": "RUN-ACME", "mode": "DEMO", "status": "BLOCKED"}]),
              patch.object(portal_main, "_get", side_effect=source),
              patch.object(portal_main, "post_json",
                           side_effect=AssertionError("unexpected write"))):
            page = portal_main.demo_run_detail("RUN-ACME")
        self.assertIn('href="/timeline?run_id=RUN-ACME"', page)
        for path in ("/runs", "/twin?run_id=RUN-ACME",
                     "/evidence?run_id=RUN-ACME",
                     "/policy-control?run_id=RUN-ACME"):
            self.assertIn('href="' + path + '"', page)
        self.assertIn("ITSM GLPI", page)
        self.assertIn("UNKNOWN", page)
        self.assertNotIn("ticket connecté</a>", page)

    def test_evidence_itsm_route_rejects_unauthorized_before_core(self):
        from fastapi.responses import JSONResponse
        from fastapi.testclient import TestClient
        from portal import main as portal_main
        with (patch("portal.demo_ledger_read.read_demo_ledger",
                    return_value=JSONResponse({"status": "UNKNOWN"}, status_code=401)) as viewer,
              patch.object(portal_main, "_runs",
                           side_effect=AssertionError("no Core inventory before auth")),
              patch.object(portal_main, "_get",
                           side_effect=AssertionError("no Core detail before auth"))):
            response = TestClient(portal_main.app).get(
                "/api/demo-studio/runs/RUN-ACME/evidence-itsm")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers.get("cache-control"), "no-store")
        viewer.assert_called_once_with("RUN-ACME", None)

    def test_evidence_itsm_route_uses_existing_projection_without_glpi_claim(self):
        from fastapi.responses import JSONResponse
        from fastapi.testclient import TestClient
        from portal import main as portal_main
        ledger = {
            "schema": "aiops.demo-ledger-read.v1", "run_id": "RUN-ACME",
            "mode": "DEMO", "classification": "DEMO_CORE_RECORDED_NOT_LIVE",
            "source": "CORE_AI_LEDGER_INTERNAL_READ",
            "evidence_classification": "SYNTHETIC_ONLY",
            "tenant_acl_qualified": False, "runtime_attested": False,
            "event_link_verified": True,
            "evidence_refs": [{"evidence_id": "EVD-1", "source": "CORE",
                               "payload_sha256": "a" * 64,
                               "known_at": "2026-10-29T12:00:00+00:00"}],
            "analyses": [{"analysis_id": "ANA-1", "evidence_ids": ["EVD-1"]}],
            "critiques": [{"critique_id": "CRT-1", "analysis_id": "ANA-1",
                           "evidence_ids": ["EVD-1"]}],
            "policy_decisions": [{"policy_decision_id": "POL-1",
                                  "analysis_id": "ANA-1", "critique_id": "CRT-1"}],
        }
        listed = {"run_id": "RUN-ACME", "mode": "DEMO", "incident_id": "INC-1"}
        detail = {"run": listed, "events": []}
        with (patch("portal.demo_ledger_read.read_demo_ledger",
                    return_value=JSONResponse(ledger)),
              patch.object(portal_main, "_runs", return_value=[listed]),
              patch.object(portal_main, "_get", return_value=detail),
              patch.object(portal_main, "post_json",
                           side_effect=AssertionError("read-only route"))):
            response = TestClient(portal_main.app).get(
                "/api/demo-studio/runs/RUN-ACME/evidence-itsm")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["state"], "CORRELATED_UNATTESTED")
        self.assertEqual(payload["classification"], "SYNTHETIC_ONLY")
        self.assertEqual(payload["evidence_refs"][0]["evidence_id"], "EVD-1")
        self.assertEqual(payload["policy_decision_ids"], ["POL-1"])
        self.assertIsNone(payload["ticket_id"])
        self.assertFalse(payload["tenant_acl_qualified"])
        self.assertFalse(payload["runtime_attested"])
        self.assertFalse(payload["effect_applied"])
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_evidence_itsm_route_rejects_foreign_ledger_identity(self):
        from fastapi.responses import JSONResponse
        from fastapi.testclient import TestClient
        from portal import main as portal_main
        listed = {"run_id": "RUN-ACME", "mode": "DEMO", "incident_id": "INC-1"}
        with (patch("portal.demo_ledger_read.read_demo_ledger",
                    return_value=JSONResponse({"run_id": "RUN-FOREIGN"})),
              patch.object(portal_main, "_runs", return_value=[listed]),
              patch.object(portal_main, "_get",
                           return_value={"run": listed, "events": []}),
              patch.object(portal_main, "post_json",
                           side_effect=AssertionError("no writes"))):
            response = TestClient(portal_main.app).get(
                "/api/demo-studio/runs/RUN-ACME/evidence-itsm")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "UNKNOWN")
        self.assertNotIn("evidence_refs", response.json())

    def test_run_detail_links_viewer_evidence_itsm_without_claiming_hitl(self):
        from portal import main as portal_main
        listed = {"run_id": "RUN-ACME", "mode": "DEMO"}
        with (patch.object(portal_main, "_runs", return_value=[listed]),
              patch.object(portal_main, "_get",
                           side_effect=lambda path, base=None:
                           {"run": listed, "events": []}
                           if path == "/api/runs/RUN-ACME"
                           else {"status": "UNKNOWN"})):
            page = portal_main.demo_run_detail("RUN-ACME")
        self.assertIn("/api/demo-studio/runs/", page)
        self.assertIn("/evidence-itsm", page)
        self.assertIn('href="#demo-evidence-itsm-output"', page)
        self.assertIn("SYNTHETIC_ONLY", page)
        self.assertIn("approbation HITL et rollback réels", page)
        self.assertIn("UNKNOWN", page)

    def test_acme_stories_route_never_links_unverified_historical_run(self):
        from fastapi.testclient import TestClient
        from portal import main as portal_main
        with (patch.object(portal_main, "_runs", return_value=[
                  {"run_id": "RUN-LIVE", "mode": "LIVE", "status": "RESOLVED"},
                  {"run_id": "RUN-DUP", "mode": "DEMO", "status": "BLOCKED"},
                  {"run_id": "RUN-DUP", "mode": "STORY", "status": "RESOLVED"}]),
              patch.object(portal_main, "post_json",
                           side_effect=AssertionError("no writes"))):
            response=TestClient(portal_main.app).get("/acme-stories")
        self.assertEqual(response.status_code, 200)
        self.assertIn("aucun run DEMO/REPLAY/STORY non ambigu", response.text)
        self.assertNotIn('href="/demo-studio/run/', response.text)
        self.assertNotIn("RUN-A4449145A6E377FF", response.text)

    def test_acme_stories_links_only_current_unique_core_run(self):
        from portal import main as portal_main
        runs=[
            {"run_id": "RUN-OLD", "mode": "DEMO", "status": "RUNNING"},
            {"run_id": "RUN-LIVE", "mode": "LIVE", "status": "RESOLVED"},
            {"run_id": "RUN-OK", "mode": "REPLAY", "status": "BLOCKED"},
            {"run_id": "bad/run", "mode": "DEMO", "status": "RESOLVED"},
        ]
        with patch.object(portal_main, "_runs", return_value=runs):
            page=portal_main.acme_stories_page()
        self.assertIn('href="/demo-studio/run/RUN-OK"', page)
        self.assertIn('href="/timeline?run_id=RUN-OK"', page)
        self.assertNotIn('href="/demo-studio/run/RUN-LIVE"', page)
        self.assertNotIn('href="/demo-studio/run/bad', page)
        self.assertNotIn("RUN-A4449145A6E377FF", page)
        self.assertIn("inventaire non attesté", page)

    def test_context_routes_preserve_verified_core_run_without_business_join(self):
        from fastapi.testclient import TestClient
        from portal import main as portal_main
        listed = {"run_id": "RUN-OK", "mode": "DEMO", "synthetic": True}
        def source(path, base=None):
            return {"run": dict(listed), "events": []} if path == "/api/runs/RUN-OK" else {}
        with (patch.object(portal_main, "_runs", return_value=[listed]),
              patch.object(portal_main, "_get", side_effect=source),
              patch.object(portal_main, "graph_panel", return_value=""),
              patch.object(portal_main, "post_json",
                           side_effect=AssertionError("read-only"))):
            client = TestClient(portal_main.app)
            for path in ("/twin", "/evidence", "/policy-control"):
                with self.subTest(path=path):
                    response = client.get(path + "?run_id=RUN-OK")
                    self.assertEqual(response.status_code, 200)
                    self.assertIn('href="/demo-studio/run/RUN-OK"', response.text)
                    self.assertIn('href="/timeline?run_id=RUN-OK"', response.text)
                    self.assertIn('href="/policy-control?run_id=RUN-OK"', response.text)
                    self.assertIn("SYNTHETIC", response.text)
                    self.assertIn("aucune corrélation automatique", response.text)

    def test_context_routes_refuse_live_ambiguous_or_foreign_run(self):
        from fastapi.testclient import TestClient
        from portal import main as portal_main
        listed = [{"run_id": "RUN-LIVE", "mode": "LIVE"},
                  {"run_id": "RUN-DUP", "mode": "DEMO"},
                  {"run_id": "RUN-DUP", "mode": "STORY"},
                  {"run_id": "RUN-OK", "mode": "DEMO"}]
        with (patch.object(portal_main, "_runs", return_value=listed),
              patch.object(portal_main, "_get",
                           return_value={"run": {"run_id": "RUN-FOREIGN", "mode": "DEMO"}}),
              patch.object(portal_main, "post_json",
                           side_effect=AssertionError("read-only"))):
            client = TestClient(portal_main.app)
            for rid in ("RUN-LIVE", "RUN-DUP", "RUN-OK", "bad%2Frun"):
                with self.subTest(rid=rid):
                    response = client.get("/evidence?run_id=" + rid)
                    self.assertEqual(response.status_code, 200)
                    self.assertIn("Contexte run Core — UNKNOWN", response.text)
                    self.assertNotIn('href="/demo-studio/run/' + rid + '"', response.text)

    def test_core_provenance_requires_explicit_consistent_flag(self):
        from portal import main as portal_main
        listed = {"run_id": "RUN-OK", "mode": "DEMO"}
        detail = {"run": dict(listed, synthetic=False)}
        self.assertEqual(portal_main._core_run_provenance(detail, listed), "REAL")
        self.assertEqual(portal_main._core_run_provenance({"run": listed}, listed), "UNKNOWN")
        self.assertEqual(portal_main._core_run_provenance(
            detail, dict(listed, synthetic=True)), "UNKNOWN")
        self.assertEqual(portal_main._core_run_provenance(
            {"run": dict(listed, synthetic=True)}, listed), "SYNTHETIC")

    def test_demo_studio_journey_preserves_run_and_unknown_without_one(self):
        from portal import main as portal_main
        for runs, selected in [
            ([{"run_id": "RUN-OK", "mode": "DEMO", "status": "BLOCKED"}], True),
            ([{"run_id": "RUN-LIVE", "mode": "LIVE", "status": "RESOLVED"}], False),
        ]:
            with (self.subTest(selected=selected),
                  patch.object(portal_main, "_runs", return_value=runs),
                  patch.object(portal_main, "_get", return_value={}),
                  patch.object(portal_main, "graph_panel", return_value=""),
                  patch.object(portal_main, "post_json",
                               side_effect=AssertionError("no writes"))):
                page=portal_main.demo_studio()
            journey=page.split("Parcours opérationnel ACME — navigation guidée",1)[1]
            if selected:
                links=[
                    'href="/timeline?run_id=RUN-OK"',
                    'href="/demo-studio/run/RUN-OK"',
                    'href="/demo-studio/run/RUN-OK#demo-ledger-output"',
                    'href="/demo-studio/run/RUN-OK#demo-evidence-itsm-output"',
                    'href="/policy-control?run_id=RUN-OK"',
                ]
                positions=[journey.index(link) for link in links]
                self.assertEqual(positions, sorted(positions))
            else:
                self.assertIn("UNKNOWN — aucun run Core qualifié", journey)
                self.assertNotIn('href="/demo-studio/run/RUN-LIVE"', page)
                self.assertNotIn('href="/timeline?run_id=RUN-LIVE"', page)
            self.assertIn("Ticket ITSM GLPI", journey)
            self.assertIn("aucune liaison attestée", journey)

if __name__ == "__main__":
    unittest.main()
