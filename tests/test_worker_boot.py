import os
import pathlib
import sys
import unittest
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
        self.assertEqual(module.health()["status"],"ok")

if __name__=="__main__":
    unittest.main()
