"""STAR public demo offline contract; does not contact the Debian portal."""
from pathlib import Path
import re
import unittest

ASSET = Path(__file__).resolve().parents[1] / "app/portal/public_demo_assets/AIOPS-EXECUTIVE-THEATER-PUBLIC.html"

class StarPublicContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = ASSET.read_text(encoding="utf-8")

    def test_twelve_narrative_scenes(self):
        self.assertEqual(len(re.findall(r'^\["(?:SITUATION|TÂCHE|ACTION|RÉSULTAT)"', self.html, re.M)), 12)

    def test_simulated_label_and_explicit_dgx_limit(self):
        self.assertIn("SIMULATED_TARGET", self.html)
        self.assertIn("pas de nouvel appel DGX", self.html)

    def test_no_remote_scripts_or_forms(self):
        self.assertNotRegex(self.html, r"<script[^>]+src=")
        self.assertNotRegex(self.html, r"<form\b")
        self.assertNotRegex(self.html, r"fetch\s*\(")

    def test_navigation_and_playback_handlers(self):
        for element in ("prev", "next", "reset", "toggle", "pace", "steps"):
            self.assertIn('id="'+element+'"', self.html)

if __name__ == "__main__":
    unittest.main()
