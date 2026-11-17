"""Static safety contract for the public ACME Workbench qualification page.

No Portal imports, network, credentials, or browser execution.
"""
import ast
import unittest
from pathlib import Path

from scripts.acme_portal_route_inventory import inventory


class WorkbenchPortalPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path("app/portal/main.py").read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)
        cls.fn = next(node for node in cls.tree.body
                      if isinstance(node, ast.FunctionDef)
                      and node.name == "acme_workbench_qualification_page")

    def test_page_is_registered_in_existing_portal(self):
        result = inventory(self.source)
        self.assertTrue(result["workbench_qualification_route_in_source"])
        self.assertFalse(result["workbench_qualification_browser_verified"])
        self.assertFalse(result["seven_scenes_browser_qualified"])

    def test_page_contains_no_service_calls_or_runtime_evidence_reads(self):
        # Whitelist only local rendering imports and calls, not service access.
        calls = [n for statement in self.fn.body for n in ast.walk(statement)
                 if isinstance(n, ast.Call)]
        self.assertTrue(calls)
        for call in calls:
            self.assertIsInstance(call.func, ast.Name)
            self.assertIn(call.func.id, {"panel", "table", "shell", "public_qualification_snapshot", "public_milestone_contract", "enumerate"})
        imports = [n for statement in self.fn.body for n in ast.walk(statement)
                   if isinstance(n, ast.ImportFrom)]
        self.assertEqual([(n.module, [a.name for a in n.names]) for n in imports],
                         [("portal.ui_theme", ["shell", "panel", "table"]),
                          ("portal.acme_qualification_view", ["public_qualification_snapshot"]),
                          ("portal.acme_milestones", ["public_milestone_contract"])])

    def test_demo_studio_links_to_workbench_without_adding_api_calls(self):
        studio = next(node for node in self.tree.body
                      if isinstance(node, ast.FunctionDef)
                      and node.name == "demo_studio")
        source = ast.get_source_segment(self.source, studio)
        self.assertIn('href="/acme-workbench"', source)
        self.assertNotIn('fetch("/acme-workbench"', source)

    def test_no_false_runtime_or_browser_claim(self):
        text = ast.get_source_segment(self.source, self.fn)
        for phrase in ("NO_GO", "SIMULATION UNIQUEMENT",
                       "Aucun appel Core"):
            self.assertIn(phrase, text)
        self.assertNotIn("get_json(", text)
        self.assertNotIn("post_json(", text)


if __name__ == "__main__":
    unittest.main()
