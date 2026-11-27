"""E17 Verify contract: real adapter, synthetic trusted-reader fixtures only."""
from copy import deepcopy
import unittest
from recovery_verify import digest, verify_recovery

ORIGINAL = 'RUN-0000000000000001'
COMPARISON = 'RUN-0000000000000002'
SCOPE = ['NODE-CI-ROOT', 'NODE-CI-ENT-ASSET-PAR', 'NODE-CI-ENT-APP-PAY']


def fixture(recovery=10):
    incident = 'INC-CI-INGEST-' + 'a' * 32
    def signal(name, second, value=None, message=None):
        ent = {'asset_id': SCOPE[1], 'application_id': SCOPE[2],
               'occurred_at': '2026-11-27T00:00:%02dZ' % second}
        result = {'event_id': name, 'source': 'metric:fixture' if value is not None else 'event:fixture',
                  'sha256': digest(name), 'enterprise': ent}
        if value is not None:
            ent['measurement'] = {'classification': 'MEASURED_SYNTHETIC_LAB',
                                  'method': 'HTTP_MONOTONIC_MEDIAN_5', 'samples_ms': [value] * 5}
            result['observation'] = {'metric': 'latency_ms', 'phase': name, 'value': value}
        else:
            ent['message'] = message
        return result
    def context(rid, iid, prefix, signals):
        rows = [{'evidence_id': prefix + s['event_id'], 'payload_hash': digest([rid, s]), 'signal': deepcopy(s)}
                for s in signals]
        refs = [{k: row[k] for k in ('evidence_id', 'payload_hash')} for row in rows]
        return ({'run': {'run_id': rid, 'incident_id': iid, 'mode': 'DEMO'}, 'production_authorized': False},
                {'run_id': rid, 'classification': 'SYNTHETIC_LAB_CONTEXT', 'production_authorized': False,
                 'policy': 'DENY', 'root': SCOPE[0], 'evidence': refs, 'verified_signals': rows})
    old = [signal('baseline', 1, 10), signal('incident', 2, 100), signal('log', 2, message='fixture')]
    before = context(ORIGINAL, incident, 'old-', old)
    refs = before[1]['evidence']
    receipt = {'receipt_id': 'ACT-' + 'b' * 32, 'classification': 'SYNTHETIC_LAB_ACTION_RECEIPT',
               'status': 'SIMULATED', 'executed_on_host': False, 'production_authorized': False,
               'operational_decision': 'DENY', 'completed_at': '2026-11-27T00:00:03Z',
               'binding': {'run_id': ORIGINAL, 'workflow_id': ORIGINAL, 'incident_id': incident,
                           'context_sha256': digest([incident, ORIGINAL, sorted(refs, key=lambda r: r['evidence_id'])]),
                           'receipt_id': 'HITL-' + 'c' * 32, 'receipt_sha256': 'd' * 64,
                           'lab_action': {'action': 'RESET_LAB_HTTP_DELAY', 'resource': SCOPE[0], 'target_id': 'e' * 32}}}
    receipt_hash = digest(receipt)
    event = signal('action', 4, message='Temporal lab action receipt ' + receipt_hash + '; original run ' + ORIGINAL)
    after = context(COMPARISON, 'INC-CI-INGEST-' + 'f' * 32, 'new-', old + [signal('recovery', 5, recovery), event])
    contexts = {ORIGINAL: before, COMPARISON: after}
    args = dict(read_context=lambda rid: deepcopy(contexts[rid]), read_action_receipt=lambda rid: deepcopy(receipt),
                original_run_id=ORIGINAL, comparison_run_id=COMPARISON, scope=SCOPE.copy(),
                original_refs=deepcopy(refs), comparison_refs=deepcopy(after[1]['evidence']),
                action_receipt_id=receipt['receipt_id'], action_receipt_sha256=receipt_hash)
    return args, contexts, receipt


class VerifyContractTests(unittest.TestCase):
    def test_outcomes(self):
        for value, expected in ((10, 'RECOVERED'), (15, 'RECOVERED'), (16, 'NOT_RECOVERED'),
                                (100, 'NOT_RECOVERED'), (120, 'NOT_RECOVERED')):
            with self.subTest(value=value):
                args, _, _ = fixture(value)
                result = verify_recovery(**args)
                self.assertEqual(result['status'], expected)
                self.assertEqual(result['measurements']['recovery_ms'], value)
                self.assertIs(result['production_authorized'], False)
                self.assertIs(result['causality_established'], False)
                self.assertEqual(result['operational_decision'], 'DENY')

    def test_reject_mutations(self):
        for name in ('median', 'scope', 'chronology', 'old_signal', 'action_message',
                     'receipt_digest', 'receipt_workflow', 'duplicate_ref', 'same_run', 'missing_evidence'):
            with self.subTest(name=name):
                args, contexts, receipt = fixture()
                rows = contexts[COMPARISON][1]['verified_signals']
                rec = rows[3]['signal']
                if name == 'median':
                    rec['observation']['value'] = 1
                elif name == 'scope':
                    rec['enterprise']['application_id'] = 'NODE-CI-ENT-APP-OTHER'
                elif name == 'chronology':
                    rec['enterprise']['occurred_at'] = '2026-11-27T00:00:04Z'
                elif name == 'old_signal':
                    rows[0]['signal']['observation']['value'] = 11
                elif name == 'action_message':
                    rows[4]['signal']['enterprise']['message'] = 'unbound action'
                elif name == 'receipt_digest':
                    args['action_receipt_sha256'] = '0' * 64
                elif name == 'receipt_workflow':
                    receipt['binding']['workflow_id'] = COMPARISON
                    args['action_receipt_sha256'] = digest(receipt)
                elif name == 'duplicate_ref':
                    args['comparison_refs'].append(args['comparison_refs'][0])
                elif name == 'same_run':
                    args['comparison_run_id'] = ORIGINAL
                else:
                    rows.pop()
                with self.assertRaises(ValueError):
                    verify_recovery(**args)

    def test_reader_outage_and_changed_original(self):
        args, contexts, _ = fixture()
        def unavailable(_):
            raise OSError('synthetic reader unavailable')
        with self.assertRaises(OSError):
            verify_recovery(**(args | {'read_action_receipt': unavailable}))
        reads = 0
        def changed(rid):
            nonlocal reads
            result = deepcopy(contexts[rid])
            if rid == ORIGINAL:
                reads += 1
                if reads == 2:
                    result[0]['run']['status'] = 'CHANGED'
            return result
        with self.assertRaises(ValueError):
            verify_recovery(**(args | {'read_context': changed}))


if __name__ == '__main__':
    unittest.main()
