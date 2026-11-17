"""External service theme assets and Compose wiring contract."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ExternalServiceThemeTests(unittest.TestCase):
    def test_grafana_server_defaults_to_dark_theme(self):
        compose = (ROOT / "compose.yml").read_text(encoding="utf-8")
        section = compose.split("  aiops2-grafana:", 1)[1].split("\n  aiops2-", 1)[0]
        self.assertIn("GF_USERS_DEFAULT_THEME: dark", section)

    def test_glpi_custom_palette_is_mounted_read_only(self):
        compose = (ROOT / "compose.yml").read_text(encoding="utf-8")
        section = compose.split("  aiops2-glpi:", 1)[1].split("\n  aiops2-", 1)[0]
        self.assertIn("./config/glpi/themes:/var/glpi/files/_themes:ro", section)

    def test_glpi_palette_is_scoped_dark_and_uses_brand_tokens(self):
        palette = (ROOT / "config/glpi/themes/aiops-premium.scss").read_text(encoding="utf-8")
        self.assertIn('$is-dark: true;', palette)
        self.assertIn(':root[data-glpi-theme="aiops-premium"]', palette)
        self.assertIn("--tblr-primary-rgb: 139, 92, 246", palette)
        self.assertIn("--tblr-link-color-rgb: 56, 189, 248", palette)
        self.assertIn("--glpi-palette-color-4: #38bdf8", palette)

    def test_grafana_dashboard_remains_dark_and_valid_json(self):
        path = ROOT / "config/grafana/dashboards/acme-command-center.json"
        dashboard = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(dashboard["style"], "dark")


if __name__ == "__main__":
    unittest.main()
