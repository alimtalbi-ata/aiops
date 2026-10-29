import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location("audit",Path(__file__).resolve().parents[1]/"tools/audit_dgx_export_v2120.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class EvidenceAuditTests(unittest.TestCase):
 def sample(self):
  return {"run_id":"RUN-A4449145A6E377FF","evidence":[
   {"id":"a","origin":"telemetry"},{"id":"b","origin":"model_response","synthetic":True},
   {"id":"c","stage_marker":True},{"id":"d","origin":"unspecified"}],
   "claims":[{"role":"critic","model":"declared-model","validated":True,"supporting_evidence_ids":["a","b","c","d","missing"]}]}
 def test_conservative_provenance(self):
  v=m.assess(self.sample());x=v["claims"][0]
  self.assertEqual([z["status"] for z in x["evidence"]],["RECORDED","SYNTHETIC","STAGE_MARKER","UNKNOWN","ABSENT"])
  self.assertEqual(x["validation"],"DECLARED_TRUE")
  self.assertFalse(v["dgx_execution_verified"])
  self.assertFalse(x["model_execution_independently_verified"])
 def test_missing_critic_validation_is_unknown(self):
  x=self.sample();x["claims"][0].pop("validated")
  self.assertEqual(m.assess(x)["claims"][0]["validation"],"UNKNOWN")
 def test_duplicate_evidence_refused(self):
  x=self.sample();x["evidence"].append(dict(x["evidence"][0]))
  with self.assertRaises(ValueError):m.assess(x)
 def test_invalid_claim_refs_refused(self):
  x=self.sample();x["claims"][0]["supporting_evidence_ids"]="a"
  with self.assertRaises(ValueError):m.assess(x)
if __name__=="__main__":unittest.main()
