import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('aiops_intelligence', ROOT / 'app' / 'intelligence' / 'main.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

class IntelligenceContractTests(unittest.TestCase):
    def test_unknown_analyst_evidence_reference_is_detected(self):
        output = MODULE.Analyst(contract_version='2.0', classification='storage-path', severity='P1', severity_rationale='fixture', hypotheses=[{'id':'H1','statement':'path down','confidence':0.9,'supporting_evidence_ids':['E1','E-NOT-PRESENT']}], confidence=0.8, confidence_basis='fixture')
        self.assertEqual(MODULE.bad_refs(output, [{'evidence_id':'E1'}]), ['E-NOT-PRESENT'])

    def test_missing_evidence_does_not_create_references(self):
        output = MODULE.Analyst(contract_version='2.0', classification='unknown', severity='UNKNOWN', severity_rationale='no evidence', hypotheses=[{'id':'H1','statement':'unknown','confidence':0.2}], confidence=0.2, confidence_basis='no evidence')
        self.assertEqual(MODULE.bad_refs(output, []), [])

    def test_health_does_not_claim_provider_is_ready(self):
        ready = MODULE.ready()
        self.assertIn(ready['status'], ('ready', 'degraded'))
        self.assertIn('provider_configured', ready)

    def test_extra_fields_are_rejected(self):
        with self.assertRaises(Exception):
            MODULE.Analyst(contract_version='2.0', classification='x', severity='UNKNOWN', severity_rationale='x', hypotheses=[{'id':'H1','statement':'x','confidence':0.1}], confidence=0.1, confidence_basis='x', unexpected='field')

if __name__ == '__main__':
    unittest.main()
