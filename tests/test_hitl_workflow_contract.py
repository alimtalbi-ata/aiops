import ast
import pathlib
import unittest


class TemporalHitlWorkflowContractTests(unittest.TestCase):
    def test_workflow_has_signal_and_durable_wait(self):
        source = pathlib.Path("app/worker/workflow.py").read_text()
        tree = ast.parse(source)
        decorators = []
        calls = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                decorators.extend(
                    ast.unparse(item) for item in node.decorator_list
                )
            if isinstance(node, ast.Call):
                calls.append(ast.unparse(node.func))
        self.assertIn("workflow.signal", decorators)
        self.assertIn("workflow.wait_condition", calls)

    def test_workflow_never_turns_approval_into_execution_authority(self):
        source = pathlib.Path("app/worker/workflow.py").read_text()
        self.assertIn('"execution_allowed": False', source)
        self.assertIn("human_decision_recorded_execution_gate_closed", source)
        self.assertIn("proposal_hash", source)
        self.assertIn("proposal_revision", source)


    def test_missing_persisted_proposal_blocks_before_remediation(self):
        source = pathlib.Path("app/worker/workflow.py").read_text()
        self.assertIn("hitl_proposal_not_persisted", source)
        self.assertIn('if stage == "HITL" and not (', source)
        self.assertIn('if stage == "HITL":', source)
        self.assertLess(source.index("hitl_proposal_not_persisted"),
                        source.index('"finish_run"'))
        self.assertIn('"execution_allowed": False', source)


if __name__ == "__main__":
    unittest.main()
