import hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("mission",ROOT/"tools/export_acme_mission_control_v2119.py")
mission=importlib.util.module_from_spec(spec);spec.loader.exec_module(mission)
class MissionControlTests(unittest.TestCase):
 def test_six_stories_seven_evidence_events(self):
  rows=mission.dataset();self.assertEqual(len(rows),6)
  self.assertTrue(all(len(r["timeline"])==7 for r in rows))
  self.assertTrue(all(all(e["source"]=="SYNTHETIC" for e in r["timeline"]) for r in rows))
 def test_policy_invariant(self):
  rows=mission.dataset();self.assertTrue(all(r["execution_allowed"] is False for r in rows))
  rows[0]["execution_allowed"]=True
  with self.assertRaises(ValueError):mission.build(rows)
 def test_safe_embedded_data(self):
  rows=mission.dataset();rows[0]["title"]="</script><script>alert(1)</script>"
  page=mission.build(rows)
  self.assertNotIn("</script><script>alert(1)",page)
  self.assertIn(r"\u003c/script\u003e",page)
  self.assertNotIn("fetch(",page)
 def test_six_scenario_ui_controls(self):
  page=mission.build(mission.dataset())
  for token in ('id="scenario"','id="nodes"','id="events"','id="reset"','SIMULATION SYNTHÉTIQUE','RUN-A4449145A6E377FF','REFUS SIMULÉ'):
   self.assertIn(token,page)
 def test_manifest(self):
  with tempfile.TemporaryDirectory() as temp:
   d=Path(temp);report=mission.export(d)
   self.assertEqual(report["sha256"],hashlib.sha256((d/"ACME-MISSION-CONTROL.html").read_bytes()).hexdigest())
   self.assertFalse(json.loads((d/"manifest.json").read_text())["execution_allowed"])
if __name__=="__main__":unittest.main()
