import importlib.util
import unittest
from pathlib import Path

path=Path(__file__).resolve().parents[1]/"01-Application"/"aiops2"/"policy.py"
spec=importlib.util.spec_from_file_location("aiops2_policy",path)
policy=importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)

class PolicyTests(unittest.TestCase):
 def test_p1_escalates(self):
  self.assertEqual(policy.evaluate({},{"severity":"P1","confidence":.99,"evidence":[{"source":"test"}]})["decision"],"ESCALATE")
 def test_missing_evidence_escalates(self):
  self.assertEqual(policy.evaluate({},{"severity":"P2","confidence":.99,"evidence":[]})["decision"],"ESCALATE")
 def test_high_risk_requires_human(self):
  self.assertEqual(policy.evaluate({},{"severity":"P2","confidence":.99,"evidence":[{"source":"test"}],"proposed_action":"restart"})["decision"],"HUMAN_APPROVAL")
 def test_low_confidence_requires_human(self):
  self.assertEqual(policy.evaluate({},{"severity":"P3","confidence":.4,"evidence":[{"source":"test"}]})["decision"],"HUMAN_APPROVAL")
 def test_unknown_severity_fails_closed(self):
  self.assertEqual(policy.evaluate({},{"severity":"UNKNOWN","confidence":.99,"evidence":[{"source":"test"}]})["decision"],"ESCALATE")

if __name__=="__main__": unittest.main(verbosity=2)