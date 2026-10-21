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

    def test_demo_run_details_are_source_backed(self):
        def get(base,path,**kw):
            if path=="/api/runs":return {"items":[{"run_id":"RUN-DEMO-42","mode":"DEMO","status":"RESOLVED"}]}
            if path=="/api/runs/RUN-DEMO-42":return {"run_id":"RUN-DEMO-42","status":"RESOLVED"}
            if path.endswith("/ai-ledger"):return {"analysis":"ANL-SOURCE-42","critic":"CRT-SOURCE-42"}
            if path.endswith("/gates"):return {"decision":"SIMULATE"}
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
            if path=="/api/runs" else {"status":"RUNNING"})):
            result=self.portal.demo_status("RUN-DEMO")
            self.assertEqual(result["status"],"RUNNING")
            with self.assertRaises(HTTPException) as exc:
                self.portal.demo_status("RUN-LIVE")
            self.assertEqual(exc.exception.status_code,404)

    def test_demo_detail_contains_live_status_poll(self):
        def get(base,path):
            if path=="/api/runs":return {"items":[{"run_id":"RUN-DEMO","mode":"DEMO"}]}
            return {"status":"RUNNING"}
        with patch.object(self.portal,"get_json",side_effect=get):
            page=self.portal.demo_run_detail("RUN-DEMO")
        self.assertIn('id="run-watch-status"',page)
        self.assertIn("/api/demo-status/",page)
        self.assertIn("setInterval(refresh,5000)",page)

    def test_demo_live_trace_is_source_backed(self):
        def get(base,path):
            if path=="/api/runs":return {"items":[{"run_id":"RUN-DEMO","mode":"DEMO"}]}
            if path=="/api/runs/RUN-DEMO":return {"status":"BLOCKED","events":[{"event_type":"CRITIC_COMPLETED"}]}
            if path.endswith("/ai-ledger"):return {"critic":"REJECTED"}
            if path.endswith("/gates"):return {"decision":"BLOCKED"}
            raise AssertionError(path)
        with patch.object(self.portal,"get_json",side_effect=get):
            response=self.portal.demo_status("RUN-DEMO")
        self.assertEqual(response["status"],"BLOCKED")
        self.assertEqual(response["events"][0]["event_type"],"CRITIC_COMPLETED")
        self.assertEqual(response["ledger"]["critic"],"REJECTED")
        self.assertEqual(response["gates"]["decision"],"BLOCKED")

    def test_demo_missing_event_list_is_not_invented(self):
        def get(base,path):
            if path=="/api/runs":return {"items":[{"run_id":"RUN-DEMO","mode":"DEMO"}]}
            return {"status":"RUNNING"}
        with patch.object(self.portal,"get_json",side_effect=get):
            response=self.portal.demo_status("RUN-DEMO")
        self.assertEqual(response["events"],"INCONNU")

    def test_demo_status_parses_actual_core_nested_run_contract(self):
        def get(base,path):
            if path=="/api/runs":return {"items":[{"run_id":"RUN-X","mode":"DEMO"}]}
            if path=="/api/runs/RUN-X":return {"run":{"run_id":"RUN-X","status":"RESOLVED"},"events":[{"sequence":1,"event_type":"STAGE_COMPLETED"}]}
            return {"items":[]}
        with patch.object(self.portal,"get_json",side_effect=get):
            response=self.portal.demo_status("RUN-X")
        self.assertEqual(response["status"],"RESOLVED")
        self.assertEqual(response["events"][0]["sequence"],1)

    def test_demo_run_timeline_uses_canonical_core_events(self):
        def get(base,path):
            if path=="/api/runs":return {"items":[{"run_id":"RUN-DEMO","mode":"DEMO"}]}
            if path=="/api/runs/RUN-DEMO":
                return {"run":{"status":"RESOLVED"},"events":[{"sequence":3,"occurred_at":"2026-10-21T08:00:00Z","stage":"CRITIC","event_type":"CRITIC_COMPLETED","status":"DONE","decision":"SIMULATE"}]}
            return {"items":[]}
        with patch.object(self.portal,"get_json",side_effect=get):
            result=self.portal.demo_run_detail("RUN-DEMO")
        self.assertIn("Timeline canonique des événements",result)
        self.assertIn("CRITIC_COMPLETED",result)
        self.assertIn("2026-10-21T08:00:00Z",result)

if __name__=="__main__":
    unittest.main()
