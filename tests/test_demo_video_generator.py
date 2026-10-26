import json
import unittest
from pathlib import Path
from demo.generate_demo_video import SCENES, DURATION, scene_html, scenes_for


class DemoVideoContractTests(unittest.TestCase):
    def test_complete_nine_scene_story(self):
        self.assertEqual(len(SCENES), 9)
        self.assertEqual(len({scene[0] for scene in SCENES}), 9)
        self.assertEqual(len(SCENES) * DURATION, 72)
        self.assertIn("BILAN", SCENES[-1][1])

    def test_each_scene_discloses_simulation_and_provenance(self):
        for i, scene in enumerate(SCENES):
            with self.subTest(scene=scene[0]):
                html = scene_html(scene, i, len(SCENES))
                self.assertIn("SIMULATION", html)
                self.assertIn(scene[6], html)
                self.assertIn(f"SCÈNE {i+1:02d}", html)

    def test_payments_scenario_is_distinct_and_fail_closed(self):
        payments = scenes_for("PAYMENTS_P2")
        self.assertIn("PAYMENTS", payments[0][1])
        self.assertIn("SLO", payments[7][1])
        with self.assertRaises(ValueError):
            scenes_for("UNSAFE")

    def test_html_escapes_scene_content(self):
        scene = ("X", "<script>alert(1)</script>", "A & B", "SYSTEM", "STATUS", "PHASE", "Aucune action")
        html = scene_html(scene, 0, 1)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)


if __name__ == "__main__":
    unittest.main()
