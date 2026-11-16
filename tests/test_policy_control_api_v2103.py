"""Integration-contract tests for the Policy Control Center; isolated temporary DB."""
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import HTTPException

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"app"))
from policy import autonomy_store as store
from policy import main as policy

class PolicyAPIIntegration(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=store.PATH
        store.PATH=Path(self.temp.name)/"mode.sqlite3"
        self.token=policy.INTERNAL_TOKEN
        policy.INTERNAL_TOKEN="test-internal-token-only"
    def tearDown(self):
        store.PATH=self.path
        policy.INTERNAL_TOKEN=self.token
        self.temp.cleanup()
    def auth(self):
        return "Bearer test-internal-token-only"
    def change(self,mode,revision=0):
        return policy.ModeChange(mode=mode,actor="ACME-operator",
            reason="Incident response lockdown for demo",expected_revision=revision)
    def test_auth_required_for_read_and_write(self):
        for fn,arg in [(policy.autonomy_read,None),
                       (policy.autonomy_history,None)]:
            with self.assertRaises(HTTPException) as caught:
                fn(authorization=arg)
            self.assertEqual(caught.exception.status_code,401)
        with self.assertRaises(HTTPException) as caught:
            policy.autonomy_change(self.change("STOP_AUTO"),authorization=None)
        self.assertEqual(caught.exception.status_code,401)
    def test_default_mode_and_audited_lockdown(self):
        self.assertEqual(policy.autonomy_read(self.auth())["mode"],"STOP_AUTO")
        saved=policy.autonomy_change(self.change("STOP_AUTO"),authorization=self.auth())
        self.assertEqual(saved["revision"],1)
        audit=policy.autonomy_history(self.auth())["items"]
        self.assertEqual(len(audit),1)
        self.assertEqual(audit[0]["actor"],"ACME-operator")
    def test_relaxation_denied_even_with_internal_token(self):
        for mode in ("NORMAL","FREEZE"):
            with self.assertRaises(HTTPException) as caught:
                policy.autonomy_change(self.change(mode),authorization=self.auth())
            self.assertEqual(caught.exception.status_code,403)
        self.assertEqual(policy.autonomy_read(self.auth())["revision"],0)
    def test_stale_revision_is_rejected(self):
        policy.autonomy_change(self.change("STOP_AUTO"),authorization=self.auth())
        with self.assertRaises(HTTPException) as caught:
            policy.autonomy_change(self.change("STOP_AUTO"),authorization=self.auth())
        self.assertEqual(caught.exception.status_code,409)
        self.assertEqual(len(policy.autonomy_history(self.auth())["items"]),1)
    def test_current_mode_checked_afresh_during_decision(self):
        request=policy.Decision(mode="LIVE",command="REMEDIATE",severity="P2",
             confidence=.99,evidence_count=4,critic_validated=True,
             evidence_fresh=True,redundancy_ok=True,preconditions_verified=True,
             fencing_verified=True,human_approved=True,freeze_active=False)
        with patch.dict(os.environ,{"AIOPS_POLICY_EMERGENCY_STOP":"false"}):
            with patch.object(store,"status",return_value={"mode":"NORMAL","healthy":True}):
                before=policy.evaluate(request)
            policy.autonomy_change(self.change("STOP_AUTO"),authorization=self.auth())
            after=policy.evaluate(request)
        self.assertEqual(after["reason"],"AUTONOMOUS_REMEDIATION_SUSPENDED")
        self.assertEqual(after["state"],"BLOCKED")
        self.assertNotEqual(before["reason"],after["reason"])

if __name__=="__main__":
    unittest.main()
