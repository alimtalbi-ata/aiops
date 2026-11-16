import hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("cockpit",ROOT/"tools/export_acme_investigation_cockpit_v2118.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class CockpitTests(unittest.TestCase):
 def test_six_incidents_seven_events(self):
  rows=m.records();self.assertEqual(len(rows),6)
  self.assertTrue(all(len(row["timeline"])==7 for row in rows))
  self.assertTrue(all(all(e["source"]=="SYNTHETIC" for e in row["timeline"]) for row in rows))
 def test_no_effects_and_browser_controls(self):
  page=m.build(m.records())
  for value in ("SIMULATION INTÉGRALE","Analyst","Critic","RUN-A4449145A6E377FF",'id="incident"','id="replay"','aria-pressed'):
   self.assertIn(value,page)
  self.assertNotIn("fetch(",page)
 def test_bad_ci_rejected(self):
  rows=m.records();rows[0]["timeline"][0]["ci"]="UNMAPPED-CI"
  with self.assertRaises(ValueError):m.build(rows)
 def test_manifest_sha(self):
  with tempfile.TemporaryDirectory() as d:
   result=m.export(Path(d))
   self.assertEqual(result["sha256"],hashlib.sha256((Path(d)/"ACME-INVESTIGATION-COCKPIT.html").read_bytes()).hexdigest())
   self.assertEqual(json.loads((Path(d)/"manifest.json").read_text())["effects"],"NONE")
 def test_json_script_escaping(self):
  data=m.records();data[0]["title"]="</script><script>alert(1)</script>"
  output=m.build(data)
  self.assertNotIn("</script><script>alert(1)",output)
  self.assertIn(r"\u003c/script\u003e",output)
if __name__=="__main__":unittest.main()
