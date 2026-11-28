"""Fixture tests; actual SQL and restore execute in the rootless CI job."""
from copy import deepcopy
import hashlib
import json
import unittest
from poc_restore_e17_smoke import binding, bound_snapshot

R1, R2, R3 = ('RUN-000000000000000' + x for x in '123')
ACTION = {'classification': 'SYNTHETIC_LAB_ACTION_RECEIPT', 'status': 'SIMULATED'}
DIGEST = hashlib.sha256(json.dumps(ACTION, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
REFS = {'E1': 'b' * 64, 'E2': 'c' * 64}


class PostE17RestoreTests(unittest.TestCase):
    def setUp(self):
        self.report = {'classification': 'V3_TEMPORAL_E17_LAB_RUNTIME',
                       'result': 'PASS', 'production_authorized': False, 'workflow_id': R1,
                       'action_receipt': deepcopy(ACTION), 'action_receipt_sha256': DIGEST,
                       'verification': {
                           'original_run_id': R1, 'comparison_run_id': R2, 'status': 'RECOVERED',
                           'action_receipt_sha256': DIGEST, 'production_authorized': False,
                           'operational_decision': 'DENY',
                           'original_evidence': [{'evidence_id': 'E1', 'payload_hash': REFS['E1']}],
                           'comparison_evidence': [{'evidence_id': 'E2', 'payload_hash': REFS['E2']}]}}
        self.worker = {'classification': 'V3_E17_WORKER_RECEIPT_READBACK', 'run_id': R1,
                       'action_receipt': deepcopy(ACTION), 'action_receipt_sha256': DIGEST,
                       'production_authorized': False, 'operational_decision': 'DENY'}
        self.gamma = {'classification': 'V3_GAMMA_E17_REAL_READBACK', 'result': 'PASS',
                      'production_authorized': False, 'original_run_id': R1, 'comparison_run_id': R2,
                      'action_receipt_sha256': DIGEST, 'verification': 'RECOVERED'}
        self.boundary = {'classification': 'V3_TEMPORAL_BOUNDARY_RUNTIME', 'result': 'PASS',
                         'production_authorized': False, 'run_id': R3, 'workflow_id': R3,
                         'core_status': 'BLOCKED'}

    def expected(self):
        return binding(self.report, self.worker, self.gamma, self.boundary)

    def test_exact_receipts(self):
        self.assertEqual(self.expected()['runs'], [R1, R2, R3])
        self.assertEqual(self.expected()['evidence'], REFS)

    def test_wrong_receipt_and_live_rejected(self):
        self.worker['action_receipt_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            self.expected()
        self.worker['action_receipt_sha256'] = DIGEST
        self.gamma['production_authorized'] = True
        with self.assertRaises(ValueError):
            self.expected()

    def test_changed_action_receipt_rejected(self):
        self.report['action_receipt']['status'] = 'CHANGED'
        self.worker['action_receipt']['status'] = 'CHANGED'
        with self.assertRaises(ValueError):
            self.expected()

    def test_duplicate_evidence_rejected(self):
        self.report['verification']['comparison_evidence'] = deepcopy(
            self.report['verification']['original_evidence'])
        with self.assertRaises(ValueError):
            self.expected()

    def check_projection(self, replies):
        seq = iter(replies)
        return bound_snapshot(lambda q: next(seq), self.expected(),
                              project=lambda q: {'tables': {}, 'schema_sha256': 'fixture'})

    def test_exact_projection(self):
        receipt = self.check_projection([json.dumps({r: 'DEMO' for r in (R1, R2, R3)}),
                                         json.dumps(REFS), b'1'])
        self.assertEqual(receipt['e17_binding']['evidence_count'], 2)

    def test_missing_evidence_live_and_execution_receipt_rejected(self):
        runs = {r: 'DEMO' for r in (R1, R2, R3)}
        for replies in ([json.dumps({**runs, R2: 'LIVE'}), json.dumps(REFS), b'1'],
                        [json.dumps(runs), json.dumps({'E1': REFS['E1']}), b'1'],
                        [json.dumps(runs), json.dumps(REFS), b'0']):
            with self.subTest(replies=replies), self.assertRaises(ValueError):
                self.check_projection(replies)

    def test_sql_injection_rejected_before_query(self):
        expected = self.expected()
        expected['evidence']["bad'"] = DIGEST
        with self.assertRaises(ValueError):
            bound_snapshot(lambda q: self.fail('unexpected SQL'), expected)


if __name__ == '__main__':
    unittest.main()
