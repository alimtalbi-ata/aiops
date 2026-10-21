import ast,os,unittest
from pathlib import Path
from unittest.mock import patch
p=Path(__file__).resolve().parents[1]/"app/policy/main.py"
tree=ast.parse(p.read_text())
decision=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="Decision")
evaluate=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="evaluate")
# Load the full policy module only when FastAPI/Pydantic dependencies are installed.
try:
    import importlib.util
    spec=importlib.util.spec_from_file_location("acme_policy",p)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
except ImportError:
    mod=None
@unittest.skipIf(mod is None,"FastAPI/Pydantic unavailable on host")
class PolicyFreezeTests(unittest.TestCase):
    def setUp(self):
        self._state_patch=patch.object(mod.autonomy_store,"status",return_value={"mode":"NORMAL","healthy":True})
        self._state_patch.start()
        self.addCleanup(self._state_patch.stop)
    def sample(self,**kw):
        values=dict(mode="LIVE",command="EXECUTE",severity="P2",confidence=.99,
            evidence_count=5,critic_validated=True,redundancy_ok=True,
            evidence_fresh=True,preconditions_verified=True,fencing_verified=True,
            human_approved=True)
        values.update(kw)
        return mod.Decision(**values)
    def test_emergency_veto_overrides_all_approvals(self):
        with patch.dict(os.environ,{"AIOPS_POLICY_EMERGENCY_STOP":"true"}):
            d=mod.evaluate(self.sample(freeze_active=False))
        self.assertEqual(d["state"],"BLOCKED")
        self.assertIn("EMERGENCY_STOP",d["reason"])
    def test_unknown_freeze_is_denied(self):
        with patch.dict(os.environ,{"AIOPS_POLICY_EMERGENCY_STOP":"false"}):
            d=mod.evaluate(self.sample())
        self.assertIn("FREEZE_STATUS_UNKNOWN",d["reason"])
    def test_freeze_requires_two_distinct_approvals(self):
        with patch.dict(os.environ,{"AIOPS_POLICY_EMERGENCY_STOP":"false"}):
            d=mod.evaluate(self.sample(freeze_active=True,management_exception_verified=True))
        self.assertIn("CHANGE_FREEZE_ACTIVE",d["reason"])
    def test_no_live_executor_even_when_cleared(self):
        with patch.dict(os.environ,{"AIOPS_POLICY_EMERGENCY_STOP":"false"}):
            d=mod.evaluate(self.sample(freeze_active=False))
        self.assertEqual(d["state"],"BLOCKED")
        self.assertIn("LIVE_EFFECTS_NOT_QUALIFIED",d["reason"])
if __name__=="__main__":unittest.main()
