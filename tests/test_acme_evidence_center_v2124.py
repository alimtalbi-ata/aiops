import hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("kit",ROOT/"tools/export_acme_evidence_center_v2124.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def fixture():
 return {"run_id":"RUN-A4449145A6E377FF","run_status":"BLOCKED","run_mode":"DEMO","events":17,"stages":14,"evidence_records":7,"analyst_records":1,"critic_records":1,"policy_decisions":1,
 "analyst_evidence":{"references":2,"found_in_export":2,"missing_from_export":0},
 "critic_evidence":{"references":2,"found_in_export":2,"missing_from_export":0},
 "event_evidence":{"references":7,"found_in_export":7,"missing_from_export":0},
 "critic_validation_declarations":{"FALSE":1},"policy_decision_states":{"BLOCKED":1},
 "dgx_independently_attested":False,"live_execution_qualified":False}
class EvidenceCenterTests(unittest.TestCase):
 def test_explicit_provenance(self):
  page=m.index_html()
  self.assertIn("SYNTHETIC",page)
  self.assertIn("HISTORICAL AUDIT",page)
  self.assertIn("non une nouvelle lecture authentifiée",page)
  self.assertNotIn("fetch(",page)
 def test_export_files_integrity(self):
  with tempfile.TemporaryDirectory() as tmp:
   base=Path(tmp);source=base/"summary.json";source.write_text(json.dumps(fixture()),encoding="utf-8")
   output=base/"bundle";data=m.build(source,output)
   self.assertEqual(len(data["files"]),3)
   for f in data["files"]:self.assertEqual(f["sha256"],hashlib.sha256((output/f["name"]).read_bytes()).hexdigest())
   self.assertFalse(data["dgx_independently_attested"])
   self.assertFalse(data["live_execution_qualified"])
 def test_reject_unqualified_live_claims(self):
  with tempfile.TemporaryDirectory() as tmp:
   base=Path(tmp);source=base/"bad.json";data=fixture();data["live_execution_qualified"]=True;source.write_text(json.dumps(data))
   with self.assertRaises(ValueError):m.build(source,base/"out")
if __name__=="__main__":unittest.main()
