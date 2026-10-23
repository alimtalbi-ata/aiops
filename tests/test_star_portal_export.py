import json
import tempfile
import unittest
from pathlib import Path
from demo.star_portal_export import build_preview, export_preview

class StaticExportTests(unittest.TestCase):
    def _manifest(self, root):
        p = root / "manifest.json"
        p.write_text(json.dumps({"run_id": "STAR-ACME-001", "captures": {}}), encoding="utf-8")
        return p

    def test_html_and_json_are_same_scenario(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            j,h=export_preview(self._manifest(root),root,"SAN_FABRIC_P1",root/"out")
            data=json.loads(j.read_text(encoding="utf-8"))
            page=h.read_text(encoding="utf-8")
            self.assertEqual(data["scenario"],"SAN_FABRIC_P1")
            self.assertEqual(len(data["frames"]),9)
            self.assertIn("SAN Fabric P1",page)
            self.assertIn("Capture indisponible",page)
            self.assertNotIn("<script",page)
            self.assertFalse(data["safety"]["runtime_authenticated"])
            self.assertEqual(j.stat().st_mode & 0o777, 0o600)

    def test_no_overwrite_and_no_symlink_output(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            m=self._manifest(root)
            export_preview(m,root,"PAYMENTS_P2",root/"out")
            with self.assertRaises(FileExistsError):
                export_preview(m,root,"PAYMENTS_P2",root/"out")
            (root/"alias").symlink_to(root/"out", target_is_directory=True)
            with self.assertRaises(ValueError):
                export_preview(m,root,"PAYMENTS_P2",root/"alias")

    def test_invalid_run_fails_before_files_are_created(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            p=root/"bad.json"
            p.write_text(json.dumps({"run_id":"../BAD","captures":{}}))
            with self.assertRaises(ValueError):
                export_preview(p,root,"PAYMENTS_P2",root/"out")
            self.assertFalse((root/"out").exists())

if __name__=="__main__":
    unittest.main()
