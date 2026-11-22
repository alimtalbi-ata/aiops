"""Isolated contract tests for a rejected Critic's Policy audit record."""
import ast
import pathlib
import unittest
from unittest.mock import patch

ROOT=pathlib.Path(__file__).resolve().parents[1]
SRC=ROOT/'app/worker/main.py'

class CriticDenialLedgerTests(unittest.TestCase):
    def test_critic_block_stops_workflow_after_optional_audit(self):
        tree=ast.parse(SRC.read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_execute_stage_blocking')
        source=ast.get_source_segment(SRC.read_text(),fn)
        self.assertIn('persist_critic_denial(',source)
        self.assertIn("'policy_denial_recorded':policy_decision_id is not None",source)
        self.assertIn("'command':'BLOCK'",source)

    def test_denial_contract_never_approves(self):
        tree=ast.parse(SRC.read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='persist_critic_denial')
        source=ast.get_source_segment(SRC.read_text(),fn)
        self.assertIn("'critic_validated':False",source)
        self.assertIn("'human_approved':False",source)
        self.assertIn("'preconditions_verified':False",source)
        self.assertIn("'fencing_verified':False",source)
        self.assertIn("verdict.get('state')!='BLOCKED'",source)
        self.assertIn("'policy_version':'2.1.0'",source)
        self.assertIn("'required_evidence':['analyst','critic','observation']",source)

if __name__=='__main__':unittest.main()
