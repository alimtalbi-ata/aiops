"""Synthetic contract tests; no real Core, Evidence, GAMMA or authentication."""
import copy
import unittest
from collector_receipt import digest, validate_receipt


def fixture():
    signals = [{'event_id': 'synthetic-' + str(i), 'sha256': digest(i)} for i in range(3)]
    incident = {'id': 'inc-synthetic', 'tenant': 'synthetic-demo', 'resource': 'NODE-CI-ROOT',
                'policy': 'DENY', 'production_authorized': False, 'evidence': signals}
    correlation = {'classification': 'EXPERIMENTAL_SYNTHETIC', 'incidents': [incident]}
    batch = digest(incident)
    run = {'run_id': 'RUN-0000000000000001', 'incident_id': 'INC-CI-INGEST-' + batch[:32],
           'mode': 'DEMO', 'status': 'CREATED'}
    receipts = [{'evidence_id': 'EVID-' + str(i), 'payload_hash': digest({'run_id': run['run_id'],
                 'incident_id': run['incident_id'], 'signal': s, 'correlation_id': incident['id'],
                 'resource': incident['resource']})} for i, s in enumerate(signals)]
    response = {'production_authorized': False, 'admission': {'production_authorized': False,
                'admitted': True, 'classification': 'SYNTHETIC_MEASURED_INCIDENT_ADMISSION_V1',
                'operational_decision': 'DENY', 'batch_sha256': batch, 'resource': incident['resource'],
                'references': copy.deepcopy(signals)}, 'publication': {'production_authorized': False,
                'correlation': copy.deepcopy(correlation), 'core': {'classification': 'SYNTHETIC_CANONICAL_RUN',
                'production_authorized': False, 'policy': 'DENY', 'run': run}, 'stored_evidence': receipts}}
    return correlation, response


class ReceiptTests(unittest.TestCase):
    def test_valid(self):
        c, r = fixture()
        self.assertEqual(validate_receipt(c, r), 'RUN-0000000000000001')
        r['publication']['stored_evidence'].reverse()
        self.assertEqual(validate_receipt(c, r), 'RUN-0000000000000001')

    def test_rejections(self):
        changes = [
            lambda r: r['publication'].update(stored_evidence=[{}, {}, {}]),
            lambda r: r['publication']['stored_evidence'][0].update(payload_hash='0' * 64),
            lambda r: r['publication']['stored_evidence'][0].update(evidence_id='EVID-1'),
            lambda r: r['publication']['stored_evidence'].pop(),
            lambda r: r['admission'].update(batch_sha256='0' * 64),
            lambda r: r['admission'].update(resource='OTHER'),
            lambda r: r['admission']['references'][0].update(event_id='foreign'),
            lambda r: r['publication']['core']['run'].update(incident_id='INC-OTHER'),
            lambda r: r['publication']['core']['run'].update(run_id='RUN-0000000000000002'),
            lambda r: r['publication']['correlation']['incidents'][0].update(tenant='other-synthetic'),
            lambda r: r['admission'].update(production_authorized=True),
        ]
        for i, change in enumerate(changes):
            with self.subTest(case=i):
                c, r = fixture()
                change(r)
                with self.assertRaises((ValueError, KeyError, TypeError)):
                    validate_receipt(c, r)


if __name__ == '__main__':
    unittest.main()
