import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from demo.star_capture_identity_cli import build_from_manifest, main

class TestCaptureIdentityCli(unittest.TestCase):
    def test_requires_exact_manifest_shape(self):
        with self.assertRaises(ValueError):
            build_from_manifest({'run_id': 'RUN-123', 'identifiers': {}, 'runtime_authenticated': True})

    def test_cli_outputs_parseable_fail_closed_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / 'ids.json'
            output = root / 'plan.json'
            manifest.write_text(json.dumps({'run_id': 'RUN-123', 'identifiers': {
                'alert_id': 'ALERT-01', 'execution_by_cue': {'correlate': 'EXEC-01'}
            }}), encoding='utf-8')
            args = ['program', str(manifest), '--output', str(output)]
            with patch.object(sys, 'argv', args):
                main()
            result = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(result['runtime_proof_count'], 0)
            self.assertEqual(result['capture_attempt_ready_count'], 3)
            self.assertTrue(output.read_text().endswith('\n'))
            with patch.object(sys, 'argv', args), self.assertRaises(FileExistsError):
                main()

    def test_duplicate_stage_identifiers_rejected(self):
        with self.assertRaises(ValueError):
            build_from_manifest({'run_id': 'RUN-123', 'identifiers': {
                'execution_by_cue': {'correlate': 'EXEC-001', 'enrich': 'EXEC-001'}
            }})

if __name__ == '__main__':
    unittest.main()
