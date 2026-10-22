import hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("acme_dep",ROOT/"tools/export_acme_dependency_map_v2117.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class DependencyMapTests(unittest.TestCase):
    def test_six_scenarios_and_synthetic_disclosure(self):
        stories=m.get_catalog()
        result=m.build(stories)
        self.assertEqual(len(stories),6)
        for marker in ("TOPOLOGIE 100 % SYNTHÉTIQUE","acme-data","RUN-A4449145A6E377FF","aria-pressed","scenario.addEventListener"):
            self.assertIn(marker,result)
        self.assertNotIn("fetch(",result)
    def test_catalog_mismatch_denied(self):
        with self.assertRaises(ValueError):m.build(m.get_catalog()[:-1])
    def test_manifest_hash_and_no_effects(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)
            info=m.export(output)
            self.assertEqual(info["effects"],"NONE")
            self.assertEqual(info["sha256"],hashlib.sha256((output/"ACME-DEPENDENCY-MAP.html").read_bytes()).hexdigest())
            self.assertEqual(json.loads((output/"manifest.json").read_text())["sha256"],info["sha256"])
    def test_unsafe_catalog_strings_escaped_from_js(self):
        stories=m.get_catalog()
        stories[0]["title"]="</script><script>alert(1)</script>"
        result=m.build(stories)
        self.assertNotIn("</script><script>alert(1)",result)
        self.assertIn(r"\\u003c/script\\u003e",result)
if __name__=="__main__":unittest.main()
