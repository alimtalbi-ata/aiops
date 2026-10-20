import os
import pathlib
import sys
import unittest
import ast
from unittest.mock import patch

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"app"))

class WorkerBootContractTests(unittest.TestCase):
    def test_worker_module_imports_with_installed_temporal_sdk(self):
        with patch.dict(os.environ,{"AIOPS_INTERNAL_TOKEN":"test-token","TEMPORAL_ADDRESS":"127.0.0.1:7233"}):
            import importlib
            module=importlib.import_module("worker.main")
        self.assertEqual(module.RETRY.maximum_attempts,3)
        self.assertEqual(int(module.RETRY.maximum_interval.total_seconds()),10)
        self.assertIn("DGX_ANALYST",module.STAGES)
        self.assertIn("DGX_CRITIC",module.STAGES)
        self.assertIn("POLICY",module.STAGES)
        self.assertFalse(module.worker_state["polling"])
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as error:
            module.health()
        self.assertEqual(error.exception.status_code,503)
        module.worker_state["polling"]=True
        self.assertEqual(module.health()["status"],"ok")
        module.worker_state["polling"]=False

    def test_workflow_is_sandbox_safe_and_activity_only(self):
        source=(ROOT/'app'/'worker'/'workflow.py').read_text(encoding='utf-8')
        parsed=ast.parse(source)
        imported=set()
        for node in ast.walk(parsed):
            if isinstance(node,ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node,ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertFalse(any(name.startswith(('fastapi','requests','http','urllib3','shared','worker.main')) for name in imported))
        self.assertNotIn('post_json(',source)
        self.assertNotIn('get_json(',source)
        self.assertIn('"execute_stage"',source)
        self.assertIn('result_type=dict',source)

    def test_external_io_is_not_executed_on_event_loop(self):
        import inspect
        from worker import main
        self.assertTrue(inspect.iscoroutinefunction(main.start_run))
        self.assertTrue(inspect.iscoroutinefunction(main.execute_stage))
        self.assertTrue(inspect.iscoroutinefunction(main.finish_run))
        source=(ROOT/'app'/'worker'/'main.py').read_text(encoding='utf-8')
        self.assertIn("asyncio.to_thread(_execute_stage_blocking",source)
        self.assertNotIn("activity.info().attempt,'executor'",source)

    def test_worker_activity_calls_use_absolute_core_urls(self):
        source=(ROOT/'app'/'worker'/'main.py').read_text(encoding='utf-8')
        self.assertNotIn("call('POST',f'/api",source)
        self.assertIn('from worker.workflow import IncidentWorkflow',source)
if __name__=="__main__":
    unittest.main()
