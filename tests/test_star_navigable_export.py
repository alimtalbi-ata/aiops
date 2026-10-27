import json
import tempfile
import unittest
from pathlib import Path
from demo.star_navigable_export import export_navigable

class NavigableExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.manifest = self.root / "manifest.json"
        self.manifest.write_text(json.dumps({"run_id":"STAR-ACME-001","captures":{}}),encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_both_scenarios_export_nine_anchors(self):
        for scenario in ("SAN_FABRIC_P1", "PAYMENTS_P2"):
            with self.subTest(scenario=scenario):
                js, ht = export_navigable(self.manifest,self.root,scenario,self.root/scenario)
                report=json.loads(js.read_text(encoding="utf-8"))
                page=ht.read_text(encoding="utf-8")
                self.assertEqual(report["scenario"],scenario)
                self.assertEqual(len(report["frames"]),9)
                self.assertEqual(page.count('<section id="scene-'),9)
                self.assertEqual(page.count('href="#scene-'),9)
                self.assertIn("Capture absente",page)
                self.assertNotIn("<script",page)
                self.assertFalse(report["safety"]["runtime_authenticated"])

    def test_overwrite_and_symlink_refused(self):
        dest=self.root/"out"
        export_navigable(self.manifest,self.root,"SAN_FABRIC_P1",dest)
        with self.assertRaises(FileExistsError):
            export_navigable(self.manifest,self.root,"SAN_FABRIC_P1",dest)
        (self.root/"redirect").symlink_to(dest,target_is_directory=True)
        with self.assertRaises(ValueError):
            export_navigable(self.manifest,self.root,"SAN_FABRIC_P1",self.root/"redirect")

    def test_invalid_identity_creates_no_output(self):
        self.manifest.write_text(json.dumps({"run_id":"../invalid","captures":{}}))
        dest=self.root/"out"
        with self.assertRaises(ValueError):
            export_navigable(self.manifest,self.root,"PAYMENTS_P2",dest)
        self.assertFalse(dest.exists())

if __name__ == "__main__":
    unittest.main()
