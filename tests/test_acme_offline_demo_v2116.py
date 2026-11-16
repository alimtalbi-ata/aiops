import hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("offline_acme",ROOT/"tools/export_acme_offline_demo_v2116.py")
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class OfflineDemoTests(unittest.TestCase):
    def test_catalog_and_provenance(self):
        stories=module.load_stories();self.assertEqual(len(stories),6)
        markup=module.build_html(stories)
        self.assertEqual(markup.count('class="story"'),6)
        for phrase in ("SCÉNARIO FICTIF","RUN HISTORIQUE","ÉVALUATION SYNTHÉTIQUE","RUN-A4449145A6E377FF"):self.assertIn(phrase,markup)
        for network in ("fetch(","https://","http://"):self.assertNotIn(network,markup)
    def test_manifest_integrity(self):
        with tempfile.TemporaryDirectory() as folder:
            page,manifest=module.export(Path(folder),module.load_stories())
            self.assertEqual(hashlib.sha256(page.read_bytes()).hexdigest(),manifest["files"][0]["sha256"])
            self.assertEqual(json.loads((Path(folder)/"manifest.json").read_text())["effects"],"NONE")
    def test_duplicate_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/"catalog.py";s=module.load_stories()[0]
            source.write_text("STORIES = "+repr([s,s]),encoding="utf-8")
            with self.assertRaises(ValueError):module.load_stories(source)
    def test_html_escaping(self):
        s=dict(module.load_stories()[0]);s["title"]="<img src=x onerror=alert(1)>"
        markup=module.build_html([s]);self.assertNotIn("<img",markup);self.assertIn("&lt;img",markup)
if __name__=="__main__":unittest.main()
