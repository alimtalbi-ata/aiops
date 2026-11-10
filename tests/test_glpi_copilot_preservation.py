"""Protect existing GLPI Portal handoff and prevent false Copilot claims.

These are source-level regression checks, NOT GLPI/Copilot end-to-end proof.
The current main branch has a read-only GLPI handoff, not the historical
/api/copilot/ticket/{id} endpoint. The latter must be ported and qualified
separately, never replaced by a mock or asserted as already installed.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from portal.glpi_operator_view import PAGE, glpi_readonly_status, router
from portal.portal_integrations import build_navigation, render_navigation_html


class GLPICopilotPreservationTests(unittest.TestCase):
    def test_glpi_handoff_routes_preserved(self):
        paths = {(route.path, tuple(sorted(route.methods)))
                 for route in router.routes}
        self.assertIn(("/itsm", ("GET",)), paths)
        self.assertIn(("/api/portal/itsm", ("GET",)), paths)

    def test_glpi_handoff_remains_fail_closed(self):
        self.assertIn("TENANT_ACL_NOT_QUALIFIED", glpi_readonly_status.__doc__ or ""
                      if False else (ROOT / "app/portal/glpi_operator_view.py").read_text())
        self.assertIn("GLPI reste le système de référence", PAGE)
        self.assertIn("UNKNOWN", PAGE)
        self.assertNotIn("/api/copilot/ticket/", PAGE)

    def test_native_glpi_navigation_remains_available_without_claiming_auth(self):
        model = build_navigation({
            "AIOPS_PORTAL_LINK_GLPI": "https://glpi.example.invalid/"
        })
        glpi = next(item for item in model["items"] if item["id"] == "glpi")
        self.assertEqual(glpi["external_link_state"], "CONFIGURED_UNVERIFIED")
        self.assertFalse(glpi["runtime_authenticated"])
        self.assertIn("https://glpi.example.invalid/", render_navigation_html(model))

    def test_authority_module_has_no_glpi_or_copilot_side_effects(self):
        source = (ROOT / "app/shared/glpi_sync_authority.py").read_text()
        self.assertNotIn("requests.", source)
        self.assertNotIn("create_ticket(", source)
        self.assertNotIn("update_ticket(", source)
        self.assertNotIn("copilot", source.lower().split("def authorize_existing_ticket_update", 1)[-1])


if __name__ == "__main__":
    unittest.main()
