"""Independent readback fixtures; no real Core/Evidence/ACL qualification."""
from copy import deepcopy
import unittest
from collector_receipt import digest, validate_receipt
from collector_persisted_receipt import verify_persisted_receipt


def fixture():
    signals = [{'event_id': 'synthetic-' + str(i), 'sha256': digest(i)} for i in range(3)]
    incident = {'id': 'inc-synthetic', 'tenant': 'synthetic-demo', 'resource': 'NODE-CI-ROOT',
                'policy': 'DENY', 'production_authorized': False, 'evidence': signals}
    correlation = {'classification': 'EXPERIMENTAL_SYNTHETIC', 'incidents': [incident]}
    run = {'run_id': 'RUN-0000000000000001', 'incident_id': 'INC-CI-INGEST-' + digest(incident)[:32],
           'mode': 'DEMO', 'status': 'CREATED'}
    receipts = [{'evidence_id': 'EVID-' + str(i), 'payload_hash': digest({'run_id': run['run_id'],
                 'incident_id': run['incident_id'], 'signal': s, 'correlation_id': incident['id'],
                 'resource': incident['resource']})} for i, s in enumerate(signals)]
    core = {'classification': 'SYNTHETIC_CANONICAL_RUN', 'production_authorized': False,
            'policy': 'DENY', 'run': run}
    response = {'production_authorized': False, 'admission': {'production_authorized': False,
                'admitted': True, 'classification': 'SYNTHETIC_MEASURED_INCIDENT_ADMISSION_V1',
                'operational_decision': 'DENY', 'batch_sha256': digest(incident), 'resource': incident['resource'],
                'references': deepcopy(signals)}, 'publication': {'production_authorized': False,
                'correlation': deepcopy(correlation), 'core': deepcopy(core), 'stored_evidence': deepcopy(receipts)}}
    context = {'classification': 'SYNTHETIC_LAB_CONTEXT', 'policy': 'DENY', 'production_authorized': False,
               'run_id': run['run_id'], 'root': incident['resource'], 'evidence': deepcopy(receipts),
               'verified_signals': [dict(ref, signal=deepcopy(s)) for ref, s in zip(receipts, signals)]}
    return correlation, response, core, context


class PersistedReceiptTests(unittest.TestCase):
    def test_order_independent_positive(self):
        c, r, core, context = fixture()
        for reverse in (False, True):
            if reverse:
                r['publication']['stored_evidence'].reverse()
                context['verified_signals'].reverse()
            self.assertEqual(verify_persisted_receipt(c, r, read_context=lambda _: (core, context)),
                             core['run']['run_id'])

    def test_central_mutations(self):
        for kind in ('swap_ids', 'foreign_ids', 'rehashed_run'):
            with self.subTest(kind=kind):
                c, r, core, context = fixture()
                pub = r['publication']
                refs = pub['stored_evidence']
                if kind == 'swap_ids':
                    refs[0]['evidence_id'], refs[1]['evidence_id'] = refs[1]['evidence_id'], refs[0]['evidence_id']
                elif kind == 'foreign_ids':
                    for i, ref in enumerate(refs):
                        ref['evidence_id'] = 'FOREIGN-' + str(i)
                else:
                    run = pub['core']['run']
                    run['run_id'] = 'RUN-0000000000000002'
                    incident = c['incidents'][0]
                    for ref, signal in zip(refs, incident['evidence']):
                        ref['payload_hash'] = digest({'run_id': run['run_id'], 'incident_id': run['incident_id'],
                            'signal': signal, 'correlation_id': incident['id'], 'resource': incident['resource']})
                # Reproduce the old content-only acceptance before the new rejection.
                self.assertEqual(validate_receipt(c, r), pub['core']['run']['run_id'])
                with self.assertRaises(ValueError):
                    verify_persisted_receipt(c, r, read_context=lambda _: (core, context))

    def test_readback_failures(self):
        for kind in ('wrong_root', 'changed_signal', 'missing_ref', 'duplicate_ref', 'wrong_core_policy'):
            with self.subTest(kind=kind):
                c, r, core, context = fixture()
                if kind == 'wrong_root':
                    context['root'] = 'NODE-CI-OTHER'
                elif kind == 'changed_signal':
                    context['verified_signals'][0]['signal']['sha256'] = '0' * 64
                elif kind == 'missing_ref':
                    context['evidence'].pop()
                elif kind == 'duplicate_ref':
                    context['verified_signals'].append(context['verified_signals'][0])
                else:
                    core['policy'] = 'ALLOW'
                with self.assertRaises(ValueError):
                    verify_persisted_receipt(c, r, read_context=lambda _: (core, context))
        c, r, _, _ = fixture()
        def unavailable(_):
            raise OSError('synthetic readback unavailable')
        with self.assertRaises(OSError):
            verify_persisted_receipt(c, r, read_context=unavailable)


    def test_callback_cannot_substitute_references(self):
        c, r, core, context = fixture()
        def readback(_):
            for i, ref in enumerate(r['publication']['stored_evidence']):
                replacement = 'FOREIGN-' + str(i)
                ref['evidence_id'] = replacement
                context['evidence'][i]['evidence_id'] = replacement
                context['verified_signals'][i]['evidence_id'] = replacement
            return core, context
        with self.assertRaises(ValueError):
            verify_persisted_receipt(c, r, read_context=readback)

    def test_callback_cannot_change_validated_run(self):
        c, r, core, context = fixture()
        def readback(_):
            r['publication']['core']['run']['status'] = 'OTHER'
            core['run']['status'] = 'OTHER'
            return core, context
        with self.assertRaises(ValueError):
            verify_persisted_receipt(c, r, read_context=readback)

    def test_callback_cannot_rehash_signal(self):
        c, r, core, context = fixture()
        def readback(run_id):
            incident = c['incidents'][0]
            signal = incident['evidence'][0]
            signal['sha256'] = '0' * 64
            payload_hash = digest({'run_id': run_id, 'incident_id': core['run']['incident_id'],
                'signal': signal, 'correlation_id': incident['id'], 'resource': incident['resource']})
            r['publication']['stored_evidence'][0]['payload_hash'] = payload_hash
            context['evidence'][0]['payload_hash'] = payload_hash
            context['verified_signals'][0].update(signal=deepcopy(signal), payload_hash=payload_hash)
            return core, context
        with self.assertRaises(ValueError):
            verify_persisted_receipt(c, r, read_context=readback)

    def test_callback_cannot_change_returned_admission(self):
        c, r, core, context = fixture()
        def readback(_):
            r['admission']['operational_decision'] = 'ALLOW'
            return core, context
        with self.assertRaises(ValueError):
            verify_persisted_receipt(c, r, read_context=readback)


if __name__ == '__main__':
    unittest.main()
