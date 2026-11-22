"""Shared Portal theme coverage: all HTML surfaces use the local design system."""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "ci-only-theme-test-token"}):
    from portal.main import app
from fastapi.testclient import TestClient


class PortalThemeTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()

    def test_theme_stylesheet_is_local_and_served(self):
        response = self.client.get("/assets/aiops-theme.css")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/css", response.headers["content-type"])
        self.assertIn("--ai-violet: #8b5cf6", response.text)
        self.assertIn("--ai-blue: #38bdf8", response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_shared_shell_palette_aliases(self):
        css = self.client.get("/assets/aiops-theme.css").text
        for alias, canonical in {
            "bg": "bg", "card": "surface", "text": "text",
            "muted": "muted", "line": "border", "hero": "bg-soft",
            "c": "violet",
        }.items():
            with self.subTest(alias=alias):
                self.assertIn(f"--{alias}: var(--ai-{canonical});", css)
                self.assertIn(f"--ai-{canonical}:", css)

    def test_all_portal_html_surfaces_load_shared_theme(self):
        for path in ("/", "/itsm", "/runs/RUN-73AFC6FF9315376C", "/demo/explore-story", "/demo/acme-impact"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertIn(response.status_code, (200, 401, 503))
                self.assertIn('/assets/aiops-theme.css', response.text)
                self.assertIn("'self'", response.headers["content-security-policy"])
                self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])

    def test_grafana_command_center_uses_dark_mode_and_keeps_metrics(self):
        path = Path(__file__).resolve().parents[1] / "config/grafana/dashboards/acme-command-center.json"
        dashboard = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(dashboard["style"], "dark")
        self.assertEqual(
            [target["expr"] for panel in dashboard["panels"] for target in panel["targets"]],
            [
                "aiops_runs_total", "aiops_runs_running", "aiops_runs_blocked",
                "aiops_runs_resolved", "aiops_twin_nodes", "aiops_evidence_total",
            ],
        )

    def test_api_responses_are_not_rewritten_as_html(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('/assets/aiops-theme.css', response.text)


if __name__ == "__main__":
    unittest.main()
