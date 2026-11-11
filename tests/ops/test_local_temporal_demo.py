import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

PATH=Path(__file__).resolve().parents[2]/'scripts/ops/run_local_temporal_demo.py'
spec=importlib.util.spec_from_file_location('local_temporal_demo',PATH)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class LocalDemoTests(unittest.TestCase):
    def test_missing_model_blocks_before_docker(self):
        with patch('sys.argv',['demo','--image','test']), \
             patch.dict(os.environ,{'LLM_BASE_URL':'','LLM_MODEL':'','LLM_API_KEY':''}), \
             patch.object(m.shutil,'disk_usage') as disk, \
             patch.object(m.subprocess,'run') as run, \
             patch('sys.stderr',new_callable=io.StringIO) as err:
            self.assertEqual(m.main(),2)
            self.assertIn('INTELLIGENCE_MODEL_NOT_CONFIGURED',err.getvalue())
            self.assertIn('no containers started',err.getvalue())
            disk.assert_not_called()
            run.assert_not_called()

    def test_insecure_model_endpoint_blocks_before_docker(self):
        with patch('sys.argv',['demo','--image','test']), \
             patch.dict(os.environ,{'LLM_BASE_URL':'http://model.invalid/v1','LLM_MODEL':'model','LLM_API_KEY':'test-only'}), \
             patch.object(m.subprocess,'run') as run, \
             patch('sys.stderr',new_callable=io.StringIO) as err:
            self.assertEqual(m.main(),2)
            self.assertIn('LLM_BASE_URL_REQUIRES_HTTPS',err.getvalue())
            run.assert_not_called()

    def test_low_disk_starts_nothing_and_reports_blocked(self):
        with patch('sys.argv',['demo','--image','test']), \
             patch.dict(os.environ,{'LLM_BASE_URL':'https://model.invalid/v1','LLM_MODEL':'test-model','LLM_API_KEY':'test-only'},clear=False), \
             patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=0)), \
             patch.object(m.subprocess,'run') as run, patch('sys.stderr',new_callable=io.StringIO) as err:
            self.assertEqual(m.main(),2)
            run.assert_not_called()
            self.assertIn('nothing started',err.getvalue())

    def test_partial_docker_start_cleans_only_its_generated_project(self):
        commands=[]
        def run(command,**kwargs):
            commands.append(command)
            if 'create' in command:
                raise subprocess.CalledProcessError(1,command)
            return subprocess.CompletedProcess(command,0,stdout='')
        with tempfile.TemporaryDirectory() as td, \
             patch('sys.argv',['demo','--image','test','--keep']), \
             patch.dict(os.environ,{'LLM_BASE_URL':'https://model.invalid/v1','LLM_MODEL':'test-model','LLM_API_KEY':'test-only'},clear=False), \
             patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=3*1024**3)), \
             patch.object(m.tempfile,'mkdtemp',return_value=td), \
             patch.object(m.subprocess,'check_output',return_value='a'*40), \
             patch.object(m.subprocess,'run',side_effect=run), \
             patch('sys.stderr',new_callable=io.StringIO):
            self.assertEqual(m.main(),1)
            self.assertEqual(commands[-1][-2:],['down','--remove-orphans'])
            self.assertIn(str(Path(td)/'compose.json'),commands[-1])
            self.assertFalse((Path(td)/'receipt.json').exists())

    def test_fresh_run_requires_stage_evidence_and_temporal_replay(self):
        client=m.CLIENT
        for marker in ("STAGE_EVIDENCE_LINK_MISSING", "EVIDENCE_COVERAGE_INCOMPLETE",
                       "TEMPORAL_NOT_COMPLETED", "replay_workflow(history)",
                       "IMAGE_SOURCE_MISMATCH", "SIMULATE_GATE_MISSING"):
            with self.subTest(marker=marker):
                self.assertIn(marker,client)

    def test_manifest_detects_source_change_but_ignores_python_cache(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/'main.py').write_text('version = 1\n')
            original=m.source_manifest(root)
            cache=root/'__pycache__';cache.mkdir()
            (cache/'main.pyc').write_bytes(b'generated cache')
            self.assertEqual(m.source_manifest(root),original)
            (root/'main.py').write_text('version = 2\n')
            self.assertNotEqual(m.source_manifest(root),original)

if __name__=='__main__':
    unittest.main()
