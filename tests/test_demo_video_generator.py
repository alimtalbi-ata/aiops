import json
import unittest
from pathlib import Path
from demo.generate_demo_video import SCENES, DURATION, scene_html


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
                self.assertIn("Aucune", html)
                self.assertIn(f"SCÈNE {i+1:02d}", html)

    def test_html_escapes_scene_content(self):
        scene = ("X", "<script>alert(1)</script>", "A & B", "SYSTEM", "STATUS", "PHASE", "Aucune action")
        html = scene_html(scene, 0, 1)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)


if __name__ == "__main__":
    unittest.main()
