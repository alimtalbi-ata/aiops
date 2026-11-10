"""Exercise the actual capture CLI boundary, including ambiguous JSON objects."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_fs147_twin_fact_provenance_duplicate_keys import capture


class CaptureJsonAdmissionTests(unittest.TestCase):
    def run_capture(self, raw):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'capture.json'
            path.write_text(raw, encoding='utf-8')
            return subprocess.run([
                sys.executable, str(Path(__file__).resolve().parents[1] /
                                    'scripts/fs/fs147_twin_partition_gate.py'),
                '--capture', str(path), '--fs-namespace', 'lab-fs',
                '--san-namespace', 'lab-san', '--fs-run-id', 'core-fs-run',
                '--san-run-id', 'core-san-run'], capture_output=True, text=True)

    def valid_capture(self):
        graph, fs, san = capture()
        return json.dumps(dict(graph=graph, fs_facts=fs, san_facts=san))

    def test_valid_capture_cli(self):
        result = self.run_capture(self.valid_capture())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'PASS')

    def test_duplicate_capture_keys_hold(self):
        raw = self.valid_capture()
        cases = [
            raw.replace('"namespace": "lab-fs"',
                        '"namespace": "lab-san", "namespace": "lab-fs"', 1),
            raw.replace('"synthetic": true',
                        '"synthetic": false, "synthetic": true', 1),
            raw.replace('"graph":', '"graph": {}, "graph":', 1),
        ]
        for value in cases:
            with self.subTest(raw=value):
                result = self.run_capture(value)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertEqual(json.loads(result.stdout)['status'], 'HOLD')
                self.assertEqual(result.stderr, '')

    def test_malformed_capture_returns_structured_hold(self):
        result = self.run_capture('{')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)['status'], 'HOLD')
        self.assertEqual(result.stderr, '')


if __name__ == '__main__':
    unittest.main()
