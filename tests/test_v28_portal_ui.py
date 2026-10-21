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

if __name__=="__main__":
    unittest.main()
