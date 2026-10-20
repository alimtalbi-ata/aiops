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

if __name__=="__main__":
    unittest.main()
