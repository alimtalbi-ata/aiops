import importlib.util
import os
import pathlib
import sys
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
os.environ.setdefault("AIOPS_INTERNAL_TOKEN", "unit-test-only-token")
SPEC = importlib.util.spec_from_file_location("aiops_portal", ROOT / "app" / "portal" / "main.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

class PortalDemoTests(unittest.TestCase):
    def test_demo_launch_supplies_execute_payload_and_unique_idempotency(self):
        responses = [
            {"incident_id": "INC-UNIT-1"},
            {"run_id": "RUN-UNIT-1"},
            {"run_id": "RUN-UNIT-1", "workflow_id": "WF-UNIT-1"},
        ]
        with patch.dict(os.environ,{"AIOPS_DEMO_LAUNCH_ENABLED":"true"}):
            with patch.object(MODULE, "post_json", side_effect=responses) as post:
                result = MODULE.demo("Bearer "+os.environ["AIOPS_INTERNAL_TOKEN"])
        self.assertEqual(result["workflow_id"], "WF-UNIT-1")
        self.assertEqual(post.call_count, 3)
        incident_call = post.call_args_list[0]
        run_call = post.call_args_list[1]
        execute_call = post.call_args_list[2]
        self.assertEqual(incident_call.args[1], "/api/incidents")
        self.assertEqual(run_call.args[1], "/api/runs")
        self.assertEqual(incident_call.args[2]["external_id"], run_call.args[2]["idempotency_key"])
        self.assertTrue(incident_call.args[2]["external_id"].startswith("DEMO-GOLDEN-PAYMENT-"))
        self.assertEqual(execute_call.args[1], "/api/runs/RUN-UNIT-1/execute")
        self.assertEqual(execute_call.args[2], {})

    def test_each_demo_launch_has_a_fresh_identity(self):
        def invoke():
            responses = [{"incident_id": "INC"}, {"run_id": "RUN"}, {"workflow_id": "WF"}]
            with patch.dict(os.environ,{"AIOPS_DEMO_LAUNCH_ENABLED":"true"}):
                with patch.object(MODULE, "post_json", side_effect=responses) as post:
                    MODULE.demo("Bearer "+os.environ["AIOPS_INTERNAL_TOKEN"])
                    return post.call_args_list[0].args[2]["external_id"]
        self.assertNotEqual(invoke(), invoke())

if __name__ == "__main__":
    unittest.main()
