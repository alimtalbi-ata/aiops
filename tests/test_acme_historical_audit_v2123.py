import importlib.util,json,tempfile,unittest,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("historical",ROOT/"tools/export_acme_historical_audit_v2123.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def fixture():
 return {"run_id":"RUN-A4449145A6E377FF","run_status":"BLOCKED","run_mode":"DEMO","events":17,"stages":14,"evidence_records":7,"analyst_records":1,"critic_records":1,"policy_decisions":1,
 "analyst_evidence":{"references":2,"found_in_export":2,"missing_from_export":0},
 "critic_evidence":{"references":2,"found_in_export":2,"missing_from_export":0},
 "event_evidence":{"references":7,"found_in_export":7,"missing_from_export":0},
 "critic_validation_declarations":{"FALSE":1},"policy_decision_states":{"BLOCKED":1},
 "dgx_independently_attested":False,"live_execution_qualified":False}
class HistoricalPanelTests(unittest.TestCase):
 def test_history_is_distinct_and_qualified(self):
  content=m.render(fixture())
  for term in ("RUN-A4449145A6E377FF","17","Critic","FALSE","BLOCKED","n'inférence DGX authentifiée","métadonnées".upper()):
   self.assertIn(term,content)
  self.assertNotIn("fetch(",content)
 def test_reject_fake_dgx_qualification(self):
  data=fixture();data["dgx_independently_attested"]=True
  with self.assertRaises(ValueError):m.render(data)
 def test_reject_reference_mismatch(self):
  data=fixture();data["analyst_evidence"]["references"]=3
  with self.assertRaises(ValueError):m.render(data)
 def test_html_escape(self):
  data=fixture();data["run_status"]="<script>alert(1)</script>"
  markup=m.render(data)
  self.assertNotIn("<script>alert(1)",markup)
 def test_output_manifest(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);source=root/"input.json";source.write_text(json.dumps(fixture()),encoding="utf-8")
   output=root/"output";res=m.export(source,output)
   self.assertEqual(res["sha256"],hashlib.sha256((output/"ACME-HISTORICAL-AUDIT.html").read_bytes()).hexdigest())
if __name__=="__main__":unittest.main()
