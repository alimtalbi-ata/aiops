"""Offline: python -m unittest discover -s tests -p 'test_fs_real_readiness.py'."""
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / 'app/portal/fs_real_readiness.py'
spec = importlib.util.spec_from_file_location('fs_real_readiness', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class ReadinessTests(unittest.TestCase):
    def test_rejects_untrusted_payload(self):
        with self.assertRaises(ValueError): module.summarize_lineage({'stages': {}})
    def test_empty_projection_not_ready(self):
        result = module.summarize_lineage({'read_only': True})
        self.assertEqual(result['coverage_percent'], 0)
        self.assertEqual(len(result['human_questions']), 8)
        self.assertFalse(result['ready'])
    def test_missing_evidence_never_counts_as_pass(self):
        result = module.summarize_lineage({'read_only': True, 'stages': {'core': {'status': 'PASS'}}})
        self.assertEqual(result['verified_pass_count'], 0)
    def test_complete_receipts_do_not_approve_or_resolve(self):
        stages = {s: {'status': 'PASS', 'evidence_ref': 'receipt:'+s} for s in module.REQUIRED}
        result = module.summarize_lineage({'read_only': True, 'stages': stages, 'approval': 'APPROVED', 'resolution': 'RESOLVED'})
        self.assertEqual(result['status'], 'EVIDENCE_COMPLETE_NOT_APPROVED')
        self.assertEqual(result['approval'], 'UNVERIFIED')
        self.assertEqual(result['resolution'], 'UNVERIFIED')
        self.assertFalse(result['ready'])
