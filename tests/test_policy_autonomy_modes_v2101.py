import importlib.util,os,unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"app"))
from unittest.mock import patch
p=Path(__file__).resolve().parents[1]/"app/policy/main.py"
spec=importlib.util.spec_from_file_location("policy_modes",p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class AutonomyTests(unittest.TestCase):
    def setUp(self):
        self._state_patch=patch.object(m.autonomy_store,"status",return_value={"mode":os.getenv("AIOPS_POLICY_AUTONOMY_MODE","STOP_AUTO"),"healthy":True})
        self._state_patch.start()
        self.addCleanup(self._state_patch.stop)
    def request(self,cls="AUTONOMOUS_REMEDIATION"):
        return m.Decision(mode="LIVE",command="EXECUTE",severity="P2",confidence=.99,
          evidence_count=5,critic_validated=True,redundancy_ok=True,
          evidence_fresh=True,preconditions_verified=True,fencing_verified=True,
          human_approved=True,freeze_active=False,operation_class=cls)
    def test_default_stop_auto(self):
        with patch.dict(os.environ,{},clear=True):
            self.assertEqual(m.evaluate(self.request())["reason"],"AUTONOMOUS_REMEDIATION_SUSPENDED")
    def test_freeze_blocks_unclassified_remediation(self):
        with patch.dict(os.environ,{"AIOPS_POLICY_AUTONOMY_MODE":"FREEZE","AIOPS_POLICY_EMERGENCY_STOP":"false"}):
            self.assertEqual(m.evaluate(self.request())["reason"],"FREEZE_RESTRICTS_OPERATION_CLASS")
    def test_freeze_standard_change_still_requires_live_safety(self):
        with patch.dict(os.environ,{"AIOPS_POLICY_AUTONOMY_MODE":"FREEZE","AIOPS_POLICY_EMERGENCY_STOP":"false"}):
            result=m.evaluate(self.request("STANDARD_CHANGE"))
            self.assertEqual(result["state"],"BLOCKED")
            self.assertEqual(result["reason"],"FREEZE_STATUS_UNKNOWN: effect prohibited" if False else "LIVE_EFFECTS_NOT_QUALIFIED: real effect adapters and fencing are disabled")
    def test_invalid_mode_fails_closed(self):
        with patch.dict(os.environ,{"AIOPS_POLICY_AUTONOMY_MODE":"unexpected"}):
            self.assertEqual(m.evaluate(self.request())["reason"],"INVALID_AUTONOMY_MODE")
if __name__=="__main__":unittest.main()
