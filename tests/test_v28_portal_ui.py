import importlib
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"app"))
os.environ.setdefault("AIOPS_INTERNAL_TOKEN","test-v28-non-production")
os.environ.setdefault("AIOPS_ADMIN_TOKEN","test-v28-non-production")

class PortalPageContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.portal=importlib.import_module("portal.main")
        cls.ui=importlib.import_module("portal.ui_theme")

    def test_all_target_page_routes_registered(self):
        paths={r.path for r in self.portal.app.routes}
        self.assertTrue({"/","/runs","/timeline","/twin","/evidence","/policy","/copilot","/qualification"}.issubset(paths))

    def test_shell_has_navigation_theme_and_accessibility(self):
        page=self.ui.shell("/twin","Digital Twin","description","<p>contenu</p>")
        for value in ('lang="fr"','aria-current="page"','prefers-reduced-motion','theme-toggle','/timeline','/qualification'):
            self.assertIn(value,page)

    def test_server_values_are_escaped(self):
        x='<img src=x onerror=alert(1)>'
        rendered=self.ui.table(["Title"],[[x]])
        self.assertNotIn(x,rendered)
        self.assertIn("&lt;img",rendered)
        self.assertNotIn("<img",rendered)

    def test_pages_do_not_fabricate_live_data(self):
        with patch.object(self.portal,"get_json",side_effect=ConnectionError("backend unavailable")):
            for view in (self.portal.home,self.portal.runs_page,self.portal.timeline_page,self.portal.twin_page,self.portal.evidence_page,self.portal.policy_page,self.portal.qualification_page):
                page=view()
                self.assertIn("ACME",page)
                self.assertNotIn("latence écriture 48 ms",page)
                self.assertNotIn("2 min 33",page)
        with patch.object(self.portal,"get_json",side_effect=ConnectionError("backend unavailable")):
            self.assertIn("INCONNU",self.portal.home())

    def test_demo_disabled_rejects_before_side_effects(self):
        from fastapi import HTTPException
        with patch.dict(os.environ,{"AIOPS_DEMO_LAUNCH_ENABLED":"false"}):
            with patch.object(self.portal,"post_json",side_effect=AssertionError("unsafe side effect")):
                with self.assertRaises(HTTPException) as ctx:
                    self.portal.demo()
                self.assertEqual(ctx.exception.status_code,403)

    def test_demo_enabled_requires_real_token(self):
        from fastapi import HTTPException
        with patch.dict(os.environ,{
            "AIOPS_DEMO_LAUNCH_ENABLED":"true",
            "AIOPS_INTERNAL_TOKEN":"ci-test-only-secret",
        }):
            with patch.object(self.portal,"post_json",side_effect=AssertionError("unsafe side effect")):
                with self.assertRaises(HTTPException) as ctx:
                    self.portal.demo("Bearer invalid")
                self.assertEqual(ctx.exception.status_code,401)
                with self.assertRaises(HTTPException) as missing:
                    self.portal.demo(None)
                self.assertEqual(missing.exception.status_code,401)

    def test_twin_graph_escapes_hostile_label(self):
        from portal.twin_graph import graph_panel
        unsafe = '</script><img src=x onerror=alert(1)>'
        graph = {"nodes":[{"node_id":"n1","name":unsafe,"type":"SWITCH","state":"DEGRADED"}],"edges":[]}
        page = graph_panel(graph)
        self.assertNotIn('</script><img',page)
        self.assertIn('twin-graph',page)
        self.assertIn('application/json',page)
        self.assertIn('textContent',page)

    def test_twin_graph_rejects_missing_data(self):
        from portal.twin_graph import graph_panel
        self.assertIn("INCONNU",graph_panel({"nodes":None,"edges":[]}))
        self.assertIn("INCONNU",graph_panel(None))

    def test_twin_graph_filters_orphan_edges(self):
        from portal.twin_graph import graph_panel
        page=graph_panel({"nodes":[{"node_id":"a","name":"SAN"}],
                          "edges":[{"source_id":"a","target_id":"missing"}]})
        self.assertIn("0 relations",page)

    def test_twin_impact_marks_only_authoritative_affected_nodes(self):
        from portal.twin_graph import graph_panel
        graph={"nodes":[{"node_id":"san-a","name":"SAN"},{"node_id":"svc-pay","name":"Payment"}],
               "edges":[{"source_id":"san-a","target_id":"svc-pay"}]}
        impact={"root":"san-a","affected":[{"node_id":"san-a"},{"node_id":"svc-pay"}]}
        page=graph_panel(graph,impact=impact)
        self.assertIn('"impact_known":true',page)
        self.assertIn('"impact_ids":["san-a","svc-pay"]',page)
        unknown=graph_panel(graph,impact={"status":"UNKNOWN"})
        self.assertIn('"impact_known":false',unknown)
        self.assertIn('"impact_ids":[]',unknown)

    def test_twin_graph_zoom_and_faceted_filters_present(self):
        from portal.twin_graph import graph_panel
        page=graph_panel({"nodes":[{"node_id":"s1","name":"Switch 1","site":"PARIS","state":"DEGRADED"}],"edges":[]})
        for control in ("graph-zoom-in","graph-zoom-out","graph-site","graph-state"):
            self.assertIn(control,page)
        self.assertIn("Math.min(3,scale*1.25)",page)
        self.assertIn("Math.max(0.65,scale/1.25)",page)
        self.assertIn("siteInput.addEventListener",page)
        self.assertIn("stateInput.addEventListener",page)

    def test_connected_demo_studio_remains_read_only_on_upstream_failure(self):
        self.assertIn("/demo-studio",{r.path for r in self.portal.app.routes})
        with patch.object(self.portal,"get_json",side_effect=ConnectionError("backend unavailable")):
            with patch.object(self.portal,"post_json",side_effect=AssertionError("unexpected write")):
                page=self.portal.demo_studio()
        self.assertIn("LECTURE SEULE",page)
        self.assertIn("INCONNU",page)
        self.assertIn("Demo Studio",page)

    def test_demo_impact_scope_never_certifies_payments_from_root_only(self):
        root = "ACME-SAN-FABRIC-A"
        only_root = {"root": root, "affected": [{"node_id": root}]}
        label, valid = self.portal._demo_impact_scope(only_root)
        self.assertTrue(valid)
        self.assertIn("RACINE SEULE", label)
        self.assertIn("NON PROUVÉE", label)
        declared = {"root": root, "affected": [{"node_id": root},
                                               {"node_id": "ACME-SVC-PAYMENTS"}]}
        label, valid = self.portal._demo_impact_scope(declared)
        self.assertTrue(valid)
        self.assertIn("2 NŒUDS TWIN DÉCLARÉS", label)
        self.assertIn("NON ATTESTÉE", label)
        for malformed in (
            {"status": "UNKNOWN", **declared},
            {"status": "ERROR", **declared},
            {"error_type": "HTTPError", "http_status": 401, **declared},
            {"root": root, "affected": [{"node_id": "ACME-SVC-PAYMENTS"}]},
            {"root": root, "affected": [{"node_id": root}, {"node_id": root}]},
            {"root": root, "affected": [{"node_id": root}, "ACME-SVC-PAYMENTS"]},
            {"root": root, "affected": []},
        ):
            with self.subTest(malformed=malformed):
                label, valid = self.portal._demo_impact_scope(malformed)
                self.assertFalse(valid)
                self.assertIn("INCONNU", label)

    def test_demo_impact_scope_rejects_foreign_root_even_with_payments(self):
        # A well-formed Twin response for SAN-B must never qualify SAN-A.
        foreign = {"root": "ACME-SAN-FABRIC-B", "affected": [
            {"node_id": "ACME-SAN-FABRIC-B"},
            {"node_id": "ACME-SAN-FABRIC-A"},
            {"node_id": "ACME-SVC-PAYMENTS"}]}
        label, valid = self.portal._demo_impact_scope(foreign)
        self.assertFalse(valid)
        self.assertIn("INCONNU", label)

    def test_demo_studio_foreign_twin_root_never_highlights_impact(self):
        root = "ACME-SAN-FABRIC-A"
        foreign = "ACME-SAN-FABRIC-B"
        graph = {"nodes": [
            {"node_id": root, "name": "SAN A"},
            {"node_id": foreign, "name": "SAN B"},
            {"node_id": "ACME-SVC-PAYMENTS", "name": "Payments"}],
            "edges": [{"source_id": root, "target_id": "ACME-SVC-PAYMENTS"}]}
        def getter(base, path):
            if path == "/api/dashboard":
                return {"status": "ok"}
            if path == "/api/runs":
                return {"items": []}
            if path == "/api/twin/graph":
                return graph
            if path == "/api/twin/impact/" + root:
                return {"root": foreign, "affected": [
                    {"node_id": foreign}, {"node_id": root},
                    {"node_id": "ACME-SVC-PAYMENTS"}]}
            raise AssertionError(path)
        with patch.object(self.portal, "get_json", side_effect=getter):
            with patch.object(self.portal, "post_json",
                              side_effect=AssertionError("read-only")):
                page = self.portal.demo_studio()
        self.assertIn("INCONNU — portée de l'impact Twin non vérifiable", page)
        self.assertIn('"impact_known":false', page)
        self.assertIn('"impact_ids":[]', page)
        self.assertNotIn('"impact_known":true', page)

    def test_demo_studio_root_only_and_error_impact_do_not_claim_payments(self):
        root = "ACME-SAN-FABRIC-A"
        graph = {"nodes": [{"node_id": root, "name": "SAN"},
                           {"node_id": "ACME-SVC-PAYMENTS", "name": "Payments"}],
                 "edges": [{"source_id": root, "target_id": "ACME-SVC-PAYMENTS"}]}
        for impact, expected, impact_known in (
            ({"root": root, "affected": [{"node_id": root}]},
             "RACINE SEULE", "true"),
            ({"status": "UNKNOWN", "error_type": "HTTPError",
              "http_status": 401, "root": root,
              "affected": [{"node_id": root},
                           {"node_id": "ACME-SVC-PAYMENTS"}]},
             "INCONNU", "false"),
        ):
            with self.subTest(impact=impact):
                def getter(base, path):
                    if path == "/api/dashboard":
                        return {"status": "ok"}
                    if path == "/api/runs":
                        return {"items": []}
                    if path == "/api/twin/graph":
                        return graph
                    if path.startswith("/api/twin/impact/"):
                        return impact
                    raise AssertionError(path)
                with patch.object(self.portal, "get_json", side_effect=getter):
                    with patch.object(self.portal, "post_json",
                                      side_effect=AssertionError("read-only")):
                        page = self.portal.demo_studio()
                self.assertIn(expected, page)
                self.assertIn("SAN→Payments", page)
                self.assertIn('"impact_known":' + impact_known, page)
                self.assertNotIn("propagation SAN→Payments PROUVÉE", page)
                if impact_known == "true":
                    self.assertIn('"impact_ids":["' + root + '"]', page)
                    self.assertNotIn('"impact_ids":["' + root + '","ACME-SVC-PAYMENTS"]', page)
                else:
                    self.assertIn('"impact_ids":[]', page)

    def test_connected_demo_studio_uses_twin_payload_only(self):
        def getter(base,path,**kwargs):
            if path=="/api/dashboard":return {"open_p1":0}
            if path=="/api/runs":return {"items":[{"run_id":"RUN-DEMO","mode":"DEMO","status":"BLOCKED","scenario_id":"ACME"},{"run_id":"RUN-LIVE","mode":"LIVE","status":"RUNNING"}]}
            if path=="/api/twin/graph":return {"nodes":[{"node_id":"ACME-SAN-FABRIC-A","name":"SAN"}],"edges":[]}
            if path.startswith("/api/twin/impact/"):return {"root":"ACME-SAN-FABRIC-A","affected":[{"node_id":"ACME-SAN-FABRIC-A"}]}
            raise AssertionError(path)
        with patch.object(self.portal,"get_json",side_effect=getter):
            with patch.object(self.portal,"post_json",side_effect=AssertionError("unexpected write")):
                page=self.portal.demo_studio()
        self.assertIn("RUN-DEMO",page)
        self.assertNotIn("RUN-LIVE",page)
        self.assertIn('"impact_known":true',page)

    def test_demo_core_detail_envelope_and_event_identity_fail_closed(self):
        listed = {"run_id": "RUN-DEMO", "mode": "DEMO", "tenant_id": "ACME"}
        run = {"run_id": "RUN-DEMO", "mode": "DEMO", "tenant_id": "ACME",
               "status": "RESOLVED"}
        cases = [
            {"status": "UNKNOWN", "error_type": "HTTPError",
             "run": run, "events": [{"event_type": "FORGED-FOREIGN-EVENT"}]},
            {"status": "ERROR", "run": run,
             "events": [{"event_type": "FORGED-FOREIGN-EVENT"}]},
            {"run": run, "events": [{"run_id": "OTHER-RUN",
                                     "event_type": "FORGED-FOREIGN-EVENT"}]},
            {"run": run, "events": [{"tenant_id": "OTHER-TENANT",
                                     "event_type": "FORGED-FOREIGN-EVENT"}]},
            {"run": run, "events": [{"tenant_id": "ACME",
                                     "run_id": "RUN-DEMO"}, None]},
        ]
        for detail in cases:
            with self.subTest(detail=detail):
                requested = []
                def get(base, path):
                    requested.append(path)
                    if path == "/api/runs":
                        return {"items": [listed]}
                    if path == "/api/runs/RUN-DEMO":
                        return detail
                    raise AssertionError("unexpected privileged registry read: " + path)
                with patch.object(self.portal, "get_json", side_effect=get):
                    page = self.portal.demo_run_detail("RUN-DEMO")
                    poll = self.portal.demo_status("RUN-DEMO")
                self.assertIn("Chronologie Core — INCONNU", page)
                self.assertNotIn("FORGED-FOREIGN-EVENT", page)
                self.assertEqual(poll["status"], "UNKNOWN")
                self.assertEqual(poll["events"], "INCONNU")
                self.assertEqual(poll["ledger"], {"status": "UNKNOWN"})
                self.assertEqual(poll["gates"], {"status": "UNKNOWN"})
                self.assertEqual(requested, ["/api/runs", "/api/runs/RUN-DEMO"] * 2)

    def test_demo_core_event_matching_explicit_identity_remains_readable(self):
        listed = {"run_id": "RUN-DEMO", "mode": "DEMO", "tenant_id": "ACME"}
        detail = {"run": {**listed, "status": "BLOCKED"},
                  "events": [{"run_id": "RUN-DEMO", "tenant_id": "ACME",
                              "sequence": 1, "event_type": "MATCHED-EVENT"}]}
        def get(base, path):
            if path == "/api/runs":
                return {"items": [listed]}
            if path == "/api/runs/RUN-DEMO":
                return detail
            if path.endswith("/ai-ledger"):
                return {"status": "UNKNOWN"}
            if path.endswith("/gates"):
                return {"items": []}
            raise AssertionError(path)
        with patch.object(self.portal, "get_json", side_effect=get):
            page = self.portal.demo_run_detail("RUN-DEMO")
            poll = self.portal.demo_status("RUN-DEMO")
        self.assertIn("MATCHED-EVENT", page)
        self.assertEqual(poll["events"][0]["event_type"], "MATCHED-EVENT")

    def test_demo_run_details_are_source_backed(self):
        def get(base,path,**kw):
            if path=="/api/runs":return {"items":[{"run_id":"RUN-DEMO-42","mode":"DEMO","status":"RESOLVED"}]}
            if path=="/api/runs/RUN-DEMO-42":return {"run":{"run_id":"RUN-DEMO-42","mode":"DEMO","status":"RESOLVED"},"events":[]}
            if path.endswith("/ai-ledger"):return {"analysis":"ANL-SOURCE-42","critic":"CRT-SOURCE-42"}
            if path.endswith("/gates"):return {"items":[{"stage":"POLICY","decision":"SIMULATE"}]}
            raise AssertionError(path)
        with patch.object(self.portal,"get_json",side_effect=get):
            with patch.object(self.portal,"post_json",side_effect=AssertionError("read-only violation")):
                result=self.portal.demo_run_detail("RUN-DEMO-42")
        self.assertIn("ANL-SOURCE-42",result)
        self.assertIn("CRT-SOURCE-42",result)
        self.assertIn("SIMULATE",result)

    def test_demo_run_details_exclude_live_and_invalid_ids(self):
        from fastapi import HTTPException
        with patch.object(self.portal,"get_json",return_value={"items":[{"run_id":"RUN-LIVE","mode":"LIVE"}]}):
            with self.assertRaises(HTTPException) as failure:
                self.portal.demo_run_detail("RUN-LIVE")
            self.assertEqual(failure.exception.status_code,404)
        with self.assertRaises(HTTPException):
            self.portal.demo_run_detail("../../secrets")

    def test_demo_launch_control_is_opt_in_only(self):
        with patch.dict(os.environ,{"AIOPS_DEMO_LAUNCH_ENABLED":"false"}):
            with patch.object(self.portal,"get_json",side_effect=ConnectionError("offline")):
                page=self.portal.demo_studio()
                self.assertNotIn('id="launch-acme"',page)
        with patch.dict(os.environ,{"AIOPS_DEMO_LAUNCH_ENABLED":"true"}):
            with patch.object(self.portal,"get_json",side_effect=ConnectionError("offline")):
                page=self.portal.demo_studio()
                self.assertIn('id="launch-acme"',page)
                self.assertIn('type="password"',page)
                self.assertIn('t.value=""',page)
                self.assertIn('"/api/demo"',page)

    def test_demo_poll_status_filters_live_runs(self):
        from fastapi import HTTPException
        with patch.object(self.portal,"get_json",side_effect=lambda base,path: (
            {"items":[{"run_id":"RUN-DEMO","mode":"DEMO"},{"run_id":"RUN-LIVE","mode":"LIVE"}]}
            if path=="/api/runs" else {"run":{"run_id":"RUN-DEMO","mode":"DEMO","status":"RUNNING"}})):
            result=self.portal.demo_status("RUN-DEMO")
            self.assertEqual(result["status"],"RUNNING")
            with self.assertRaises(HTTPException) as exc:
                self.portal.demo_status("RUN-LIVE")
            self.assertEqual(exc.exception.status_code,404)

    def test_demo_detail_contains_live_status_poll(self):
        def get(base,path):
            if path=="/api/runs":return {"items":[{"run_id":"RUN-DEMO","mode":"DEMO"}]}
            if path=="/api/runs/RUN-DEMO":return {"run":{"run_id":"RUN-DEMO","mode":"DEMO","status":"RUNNING"},"events":[]}
            return {"items":[]}
        with patch.object(self.portal,"get_json",side_effect=get):
            page=self.portal.demo_run_detail("RUN-DEMO")
        self.assertIn('id="run-watch-status"',page)
        self.assertIn("/api/demo-status/",page)
        self.assertIn("setInterval(refresh,5000)",page)

    def test_demo_live_trace_is_source_backed(self):
        def get(base,path):
            if path=="/api/runs":return {"items":[{"run_id":"RUN-DEMO","mode":"DEMO"}]}
            if path=="/api/runs/RUN-DEMO":return {"run":{"run_id":"RUN-DEMO","mode":"DEMO","status":"BLOCKED"},"events":[{"event_type":"CRITIC_COMPLETED"}]}
            if path.endswith("/ai-ledger"):return {"critic":"REJECTED"}
            if path.endswith("/gates"):return {"items":[{"stage":"POLICY","decision":"BLOCKED"}]}
            raise AssertionError(path)
        with patch.object(self.portal,"get_json",side_effect=get):
            response=self.portal.demo_status("RUN-DEMO")
        self.assertEqual(response["status"],"BLOCKED")
        self.assertEqual(response["events"][0]["event_type"],"CRITIC_COMPLETED")
        self.assertEqual(response["ledger"]["critic"],"REJECTED")
        self.assertEqual(response["gates"]["items"][0]["decision"],"BLOCKED")

    def test_unverified_policy_items_never_leak_in_raw_detail_or_poll(self):
        # The renderer was already fail-closed, but the raw HTML panel and
        # polling JSON must not re-expose an unverified forged gate.
        for gate in (
            {"status":"UNKNOWN","error_type":"HTTPError","http_status":401,
             "items":[{"decision":"FORGED-POLICY-PASS"}],"secret":"DO-NOT-ECHO"},
            {"status":"UNKNOWN","items":[{"decision":"FORGED-POLICY-PASS"}]},
            {"items":[{"decision":"FORGED-POLICY-PASS"},None]},
            {"status":"ERROR","items":[{"decision":"FORGED-POLICY-PASS"}]},
            {"items":[{"run_id":"OTHER-RUN","decision":"FORGED-POLICY-PASS"}]},
        ):
            with self.subTest(gate=gate):
                def get(base,path):
                    if path=="/api/runs":
                        return {"items":[{"run_id":"RUN-DEMO","mode":"DEMO"}]}
                    if path=="/api/runs/RUN-DEMO":
                        return {"run":{"run_id":"RUN-DEMO","mode":"DEMO",
                                       "status":"BLOCKED"},"events":[]}
                    if path.endswith("/ai-ledger"):return {"items":[]}
                    if path.endswith("/gates"):return gate
                    raise AssertionError(path)
                with patch.object(self.portal,"get_json",side_effect=get):
                    with patch.object(self.portal,"post_json",
                                      side_effect=AssertionError("read-only")):
                        page=self.portal.demo_run_detail("RUN-DEMO")
                        polled=self.portal.demo_status("RUN-DEMO")
                self.assertNotIn("FORGED-POLICY-PASS",page)
                self.assertNotIn("DO-NOT-ECHO",page)
                self.assertNotIn("FORGED-POLICY-PASS",str(polled))
                self.assertNotIn("DO-NOT-ECHO",str(polled))
                self.assertEqual(polled["gates"]["status"],"UNKNOWN")
                self.assertNotIn("items",polled["gates"])
                if gate.get("http_status")==401:
                    self.assertIn("HTTP 401",page)
                    self.assertEqual(polled["gates"]["http_status"],401)

    def test_verified_policy_projection_preserves_simulate_and_evidence(self):
        gate={"items":[{"stage":"POLICY","state":"PASS","decision":"SIMULATE",
                        "reason":"synthetic only","evidence_ids":["EVD-1"],
                        "unexpected_private":"DO-NOT-ECHO"}]}
        def get(base,path):
            if path=="/api/runs":
                return {"items":[{"run_id":"RUN-DEMO","mode":"DEMO"}]}
            if path=="/api/runs/RUN-DEMO":
                return {"run":{"run_id":"RUN-DEMO","mode":"DEMO",
                               "status":"RESOLVED"},"events":[]}
            if path.endswith("/ai-ledger"):return {"items":[]}
            if path.endswith("/gates"):return gate
            raise AssertionError(path)
        with patch.object(self.portal,"get_json",side_effect=get):
            page=self.portal.demo_run_detail("RUN-DEMO")
            polled=self.portal.demo_status("RUN-DEMO")
        self.assertIn("SIMULATE",page)
        self.assertIn("EVD-1",page)
        self.assertNotIn("DO-NOT-ECHO",page)
        self.assertEqual(polled["gates"]["items"][0]["decision"],"SIMULATE")
        self.assertEqual(polled["gates"]["items"][0]["evidence_ids"],["EVD-1"])
        self.assertNotIn("unexpected_private",polled["gates"]["items"][0])

    def test_demo_missing_event_list_is_not_invented(self):
        def get(base,path):
            if path=="/api/runs":return {"items":[{"run_id":"RUN-DEMO","mode":"DEMO"}]}
            if path=="/api/runs/RUN-DEMO":return {"run":{"run_id":"RUN-DEMO","mode":"DEMO","status":"RUNNING"}}
            return {"items":[]}
        with patch.object(self.portal,"get_json",side_effect=get):
            response=self.portal.demo_status("RUN-DEMO")
        self.assertEqual(response["events"],"INCONNU")

    def test_demo_status_parses_actual_core_nested_run_contract(self):
        def get(base,path):
            if path=="/api/runs":return {"items":[{"run_id":"RUN-X","mode":"DEMO"}]}
            if path=="/api/runs/RUN-X":return {"run":{"run_id":"RUN-X","mode":"DEMO","status":"RESOLVED"},"events":[{"sequence":1,"event_type":"STAGE_COMPLETED"}]}
            return {"items":[]}
        with patch.object(self.portal,"get_json",side_effect=get):
            response=self.portal.demo_status("RUN-X")
        self.assertEqual(response["status"],"RESOLVED")
        self.assertEqual(response["events"][0]["sequence"],1)

    def test_demo_run_timeline_uses_canonical_core_events(self):
        def get(base,path):
            if path=="/api/runs":return {"items":[{"run_id":"RUN-DEMO","mode":"DEMO"}]}
            if path=="/api/runs/RUN-DEMO":
                return {"run":{"run_id":"RUN-DEMO","mode":"DEMO","status":"RESOLVED"},"events":[{"sequence":3,"occurred_at":"2026-10-21T08:00:00Z","stage":"CRITIC","event_type":"CRITIC_COMPLETED","status":"DONE","decision":"SIMULATE"}]}
            return {"items":[]}
        with patch.object(self.portal,"get_json",side_effect=get):
            result=self.portal.demo_run_detail("RUN-DEMO")
        self.assertIn("Chronologie canonique — Core",result)
        self.assertIn("CRITIC_COMPLETED",result)
        self.assertIn("2026-10-21T08:00:00Z",result)


    def test_v2_is_wired_once_to_source_backed_detail_page(self):
        def get(base,path):
            if path=="/api/runs":
                return {"items":[{"run_id":"RUN-DEMO","mode":"DEMO","scenario_id":"SCN-ACME"}]}
            if path=="/api/runs/RUN-DEMO":
                return {"run":{"run_id":"RUN-DEMO","mode":"DEMO","scenario_id":"SCN-ACME",
                               "status":"BLOCKED"},
                        "events":[{"sequence":1,"occurred_at":"2026-10-28T20:00:00Z",
                                   "event_type":"ACME_CORE_EVENT","payload":{"synthetic":True}}]}
            if path.endswith("/ai-ledger"):return {"status":"UNKNOWN"}
            if path.endswith("/gates"):return {"items":[]}
            raise AssertionError(path)
        with patch.object(self.portal,"get_json",side_effect=get):
            with patch.object(self.portal,"post_json",side_effect=AssertionError("write forbidden")):
                page=self.portal.demo_run_detail("RUN-DEMO")
        self.assertEqual(page.count("Mission Control V2 — provenance et fraîcheur"),1)
        self.assertIn("Chronologie canonique — Core",page)
        self.assertIn("ACME_CORE_EVENT",page)
        self.assertIn("Observations synthétiques",page)
        self.assertNotIn("LIVE qualifié",page)

    def test_detail_identity_conflicts_hide_other_run_and_skip_ledger(self):
        variants=(
            {"run":{"run_id":"RUN-OTHER","mode":"DEMO","status":"RESOLVED"},
             "events":[{"event_type":"SENSITIVE-OTHER-RUN"}]},
            {"run":{"run_id":"RUN-DEMO","mode":"LIVE","status":"RESOLVED"},
             "events":[{"event_type":"SENSITIVE-OTHER-RUN"}]},
            {"run":{"run_id":"RUN-DEMO","mode":"DEMO","scenario_id":"WRONG"},
             "events":[{"event_type":"SENSITIVE-OTHER-RUN"}]},
            {"status":"UNKNOWN","error_type":"HTTPError","http_status":401},
            {"run_id":"RUN-DEMO","mode":"DEMO","status":"RUNNING"},
        )
        for detail in variants:
            with self.subTest(detail=detail):
                calls=[]
                def get(base,path):
                    calls.append(path)
                    if path=="/api/runs":
                        return {"items":[{"run_id":"RUN-DEMO","mode":"DEMO",
                                          "scenario_id":"SCN-ACME"}]}
                    if path=="/api/runs/RUN-DEMO":return detail
                    raise AssertionError("ledger/gates must not be queried")
                with patch.object(self.portal,"get_json",side_effect=get):
                    page=self.portal.demo_run_detail("RUN-DEMO")
                self.assertIn("Chronologie Core — INCONNU",page)
                self.assertNotIn("SENSITIVE-OTHER-RUN",page)
                self.assertNotIn("Mission Control V2",page)
                self.assertEqual(calls,["/api/runs","/api/runs/RUN-DEMO"])

    def test_poll_identity_conflicts_fail_closed_without_ledger_reads(self):
        variants=(
            {"run":{"run_id":"RUN-OTHER","mode":"DEMO","status":"RESOLVED"},
             "events":[{"event_type":"SENSITIVE-OTHER-RUN"}]},
            {"run":{"run_id":"RUN-DEMO","mode":"LIVE","status":"RUNNING"}},
            {"run":{"run_id":"RUN-DEMO","mode":"DEMO","incident_id":"WRONG"}},
            {"status":"UNKNOWN","error_type":"HTTPError","http_status":403},
            {},
        )
        for detail in variants:
            with self.subTest(detail=detail):
                calls=[]
                def get(base,path):
                    calls.append(path)
                    if path=="/api/runs":
                        return {"items":[{"run_id":"RUN-DEMO","mode":"DEMO",
                                          "incident_id":"INC-ACME"}]}
                    if path=="/api/runs/RUN-DEMO":return detail
                    raise AssertionError("ledger/gates must not be queried")
                with patch.object(self.portal,"get_json",side_effect=get):
                    result=self.portal.demo_status("RUN-DEMO")
                self.assertEqual(result["status"],"UNKNOWN")
                self.assertEqual(result["source"],"CORE_IDENTITY_UNVERIFIED")
                self.assertEqual(result["events"],"INCONNU")
                self.assertEqual(result["ledger"],{"status":"UNKNOWN"})
                self.assertEqual(calls,["/api/runs","/api/runs/RUN-DEMO"])


    def test_tenant_identity_disagreement_blocks_detail_and_poll_before_ledger(self):
        # Core may omit tenant_id from one projection; neither omission nor
        # disagreement is sufficient to authorize cross-tenant evidence.
        for listed_tenant, detail_tenant in (
            ("TENANT-A", "TENANT-B"), ("TENANT-A", None),
            (None, "TENANT-A"), ("", "")):
            with self.subTest(listed=listed_tenant, detail=detail_tenant):
                listed={"run_id":"RUN-DEMO","mode":"DEMO"}
                detail={"run_id":"RUN-DEMO","mode":"DEMO","status":"RESOLVED"}
                if listed_tenant is not None:
                    listed["tenant_id"]=listed_tenant
                if detail_tenant is not None:
                    detail["tenant_id"]=detail_tenant
                calls=[]
                def get(base,path):
                    calls.append(path)
                    if path=="/api/runs":return {"items":[listed]}
                    if path=="/api/runs/RUN-DEMO":
                        return {"run":detail,"events":[{"event_type":"PRIVATE-TENANT-EVENT"}]}
                    raise AssertionError("ledger/gates must not be read")
                with patch.object(self.portal,"get_json",side_effect=get):
                    page=self.portal.demo_run_detail("RUN-DEMO")
                    result=self.portal.demo_status("RUN-DEMO")
                self.assertIn("Chronologie Core — INCONNU",page)
                self.assertNotIn("PRIVATE-TENANT-EVENT",page)
                self.assertEqual(result["source"],"CORE_IDENTITY_UNVERIFIED")
                self.assertEqual(result["events"],"INCONNU")
                self.assertEqual(calls,["/api/runs","/api/runs/RUN-DEMO"]*2)

    def test_duplicate_core_inventory_run_id_refuses_before_detail_io(self):
        from fastapi import HTTPException
        calls=[]
        def get(base,path):
            calls.append(path)
            if path=="/api/runs":
                return {"items":[
                    {"run_id":"RUN-DEMO","mode":"DEMO","tenant_id":"TENANT-A"},
                    {"run_id":"RUN-DEMO","mode":"DEMO","tenant_id":"TENANT-B"}]}
            raise AssertionError("ambiguous run must never trigger detail/ledger I/O")
        with patch.object(self.portal,"get_json",side_effect=get):
            for action in (self.portal.demo_run_detail,self.portal.demo_status):
                with self.assertRaises(HTTPException) as ctx:
                    action("RUN-DEMO")
                self.assertEqual(ctx.exception.status_code,404)
        self.assertEqual(calls,["/api/runs","/api/runs"])

    def test_live_demo_run_id_collision_refuses_before_detail_or_ledger(self):
        # A Core inventory containing the same ID in LIVE and DEMO is
        # ambiguous even if exactly one item has an allowed demo mode.
        from fastapi import HTTPException
        demo={"run_id":"RUN-SHARED","mode":"DEMO","tenant_id":"TENANT-A"}
        live={"run_id":"RUN-SHARED","mode":"LIVE","tenant_id":"TENANT-B"}
        for inventory in ([demo,live],[live,demo]):
            with self.subTest(modes=[r["mode"] for r in inventory]):
                calls=[]
                def get(base,path):
                    calls.append(path)
                    if path=="/api/runs":
                        return {"items":inventory}
                    raise AssertionError("ambiguous run must not read detail/ledger/gates")
                with patch.object(self.portal,"get_json",side_effect=get):
                    for action in (self.portal.demo_run_detail,self.portal.demo_status):
                        with self.assertRaises(HTTPException) as ctx:
                            action("RUN-SHARED")
                        self.assertEqual(ctx.exception.status_code,404)
                self.assertEqual(calls,["/api/runs","/api/runs"])

    def test_matching_core_tenant_preserves_read_only_demo_path(self):
        calls=[]
        def get(base,path):
            calls.append(path)
            if path=="/api/runs":
                return {"items":[{"run_id":"RUN-DEMO","mode":"DEMO",
                                  "tenant_id":"TENANT-A"}]}
            if path=="/api/runs/RUN-DEMO":
                return {"run":{"run_id":"RUN-DEMO","mode":"DEMO",
                               "tenant_id":"TENANT-A","status":"BLOCKED"},
                        "events":[{"sequence":1,"occurred_at":"2026-10-28T20:00:00Z",
                                   "event_type":"SYNTHETIC-EVENT"}]}
            if path.endswith("/ai-ledger"):return {"status":"UNKNOWN"}
            if path.endswith("/gates"):return {"items":[]}
            raise AssertionError(path)
        with patch.object(self.portal,"get_json",side_effect=get):
            with patch.object(self.portal,"post_json",side_effect=AssertionError("write forbidden")):
                page=self.portal.demo_run_detail("RUN-DEMO")
                result=self.portal.demo_status("RUN-DEMO")
        self.assertIn("Mission Control V2",page)
        self.assertEqual(result["status"],"BLOCKED")
        self.assertEqual(result["events"][0]["event_type"],"SYNTHETIC-EVENT")
        self.assertEqual(len(calls),8)


    def test_demo_ledger_foreign_identity_and_error_body_fail_closed(self):
        forged = (
            {"run_id": "RUN-OTHER", "analysis": "FOREIGN-LEDGER-SECRET"},
            {"tenant_id": "TENANT-B", "analysis": "FOREIGN-LEDGER-SECRET"},
            {"items": [{"run_id": "RUN-OTHER", "analysis": "FOREIGN-LEDGER-SECRET"}]},
            {"analysis": {"tenant_id": "TENANT-B", "text": "FOREIGN-LEDGER-SECRET"}},
            {"status": "UNKNOWN", "error_type": "HTTPError",
             "http_status": 401, "analysis": "FOREIGN-LEDGER-SECRET"},
        )
        for ledger in forged:
            with self.subTest(ledger=ledger):
                def get(base, path):
                    if path == "/api/runs":
                        return {"items": [{"run_id": "RUN-DEMO", "mode": "DEMO",
                                           "tenant_id": "TENANT-A"}]}
                    if path == "/api/runs/RUN-DEMO":
                        return {"run": {"run_id": "RUN-DEMO", "mode": "DEMO",
                                        "tenant_id": "TENANT-A", "status": "BLOCKED"},
                                "events": []}
                    if path.endswith("/ai-ledger"):
                        return ledger
                    if path.endswith("/gates"):
                        return {"items": []}
                    raise AssertionError(path)
                with patch.object(self.portal, "get_json", side_effect=get):
                    with patch.object(self.portal, "post_json",
                                      side_effect=AssertionError("read-only")):
                        page = self.portal.demo_run_detail("RUN-DEMO")
                        poll = self.portal.demo_status("RUN-DEMO")
                self.assertNotIn("FOREIGN-LEDGER-SECRET", page)
                self.assertNotIn("FOREIGN-LEDGER-SECRET", str(poll))
                self.assertEqual(poll["ledger"]["status"], "UNKNOWN")
                if ledger.get("http_status") == 401:
                    self.assertIn("HTTP 401", page)
                    self.assertEqual(poll["ledger"]["http_status"], 401)

    def test_demo_ledger_matching_identity_preserves_source_data(self):
        def get(base, path):
            if path == "/api/runs":
                return {"items": [{"run_id": "RUN-DEMO", "mode": "DEMO",
                                   "tenant_id": "TENANT-A"}]}
            if path == "/api/runs/RUN-DEMO":
                return {"run": {"run_id": "RUN-DEMO", "mode": "DEMO",
                                "tenant_id": "TENANT-A", "status": "RESOLVED"},
                        "events": []}
            if path.endswith("/ai-ledger"):
                return {"run_id": "RUN-DEMO", "tenant_id": "TENANT-A",
                        "analysis": "MATCHED-LEDGER-DEMO"}
            if path.endswith("/gates"):
                return {"items": []}
            raise AssertionError(path)
        with patch.object(self.portal, "get_json", side_effect=get):
            with patch.object(self.portal, "post_json",
                              side_effect=AssertionError("read-only")):
                page = self.portal.demo_run_detail("RUN-DEMO")
                poll = self.portal.demo_status("RUN-DEMO")
        self.assertIn("MATCHED-LEDGER-DEMO", page)
        self.assertEqual(poll["ledger"]["analysis"], "MATCHED-LEDGER-DEMO")

if __name__=="__main__":
    unittest.main()
