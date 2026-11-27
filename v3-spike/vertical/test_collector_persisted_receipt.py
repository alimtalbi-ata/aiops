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

class DynamicReadbackTests(unittest.TestCase):
    def exercise(self, *, fault=None, legacy=False):
        import json
        import threading
        from contextlib import ExitStack
        from http.server import BaseHTTPRequestHandler, HTTPServer
        from lab_context import context, dynamic_context

        c, r, core, _ = fixture()
        incident = c['incidents'][0]
        run = core['run']
        run_id = 'RUN-CI-LEGACY' if legacy else run['run_id']
        root = incident['resource']
        items = []
        for ref, signal in zip(r['publication']['stored_evidence'], incident['evidence']):
            payload = {'run_id': run_id, 'incident_id': run['incident_id'],
                       'signal': signal, 'correlation_id': incident['id'], 'resource': root}
            items.append({'evidence_id': ref['evidence_id'], 'payload_hash': digest(payload),
                          'payload': payload, 'source': 'v3-synthetic-ingestion',
                          'provenance': {'run_id': run_id, 'synthetic': True}})
        if fault == 'duplicate':
            items.append(deepcopy(items[0]))
        elif fault == 'foreign':
            items[0]['provenance']['run_id'] = 'RUN-FOREIGN'
        elif fault == 'conflict':
            items.append(dict(deepcopy(items[0]), source='other'))
        calls = []

        def handler(path, data, token=None):
            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    calls.append((self.path, self.headers.get('Authorization')))
                    if self.path != path or self.headers.get('Authorization') != token:
                        self.send_error(403)
                        return
                    raw = json.dumps(data).encode()
                    self.send_response(200)
                    self.send_header('Content-Length', str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                def log_message(self, *args):
                    pass
            return Handler

        with ExitStack() as stack:
            def serve(path, data, token=None):
                server = stack.enter_context(HTTPServer(('127.0.0.1', 0), handler(path, data, token)))
                thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01})
                thread.start()
                stack.callback(thread.join)
                stack.callback(server.shutdown)
                return server.server_port
            cp = serve('/api/noc/runs/'+run_id, {'data_classification': 'SYNTHETIC_CANONICAL_RUN',
                'live_remediation_authorized': False, 'tenant_acl_qualified': False,
                'runtime_authenticated': False, 'run': run}, 'Bearer '+'x'*32)
            tp = serve('/api/twin/impact/'+root, {'root': root, 'affected': [{'node_id': root, 'depth': 0}]})
            ep = serve('/api/evidence?run_id='+run_id+'&limit=20', {'items': items})
            if legacy:
                self.assertEqual(len(context(tp, ep, run_id, root)['evidence']), 3)
            else:
                def readback(selected):
                    return dynamic_context(cp, 'x'*32, selected, tp, ep, root, include_signals=True)
                if fault:
                    with self.assertRaises(ValueError):
                        verify_persisted_receipt(c, r, read_context=readback)
                else:
                    self.assertEqual(verify_persisted_receipt(c, r, read_context=readback), run_id)
        expected = [('/api/twin/impact/'+root, None), ('/api/evidence?run_id='+run_id+'&limit=20', None)]
        if not legacy:
            expected.insert(0, ('/api/noc/runs/'+run_id, 'Bearer '+'x'*32))
        self.assertEqual(calls, expected)

    def test_dynamic_readback_exact(self):
        self.exercise()

    def test_dynamic_readback_duplicate_rejected(self):
        self.exercise(fault='duplicate')

    def test_dynamic_readback_foreign_or_conflicting_rejected(self):
        for fault in ('foreign', 'conflict'):
            with self.subTest(fault=fault):
                self.exercise(fault=fault)

    def test_legacy_identical_duplicate_preserved(self):
        self.exercise(fault='duplicate', legacy=True)


class ConvergedReceiptTests(unittest.TestCase):
    def sized(self, count):
        c, r, core, context = fixture()
        incident = c['incidents'][0]
        signals = [{'event_id': 'synthetic-' + str(i), 'sha256': digest(i)} for i in range(count)]
        incident['evidence'] = signals
        run = core['run']
        run['incident_id'] = 'INC-CI-INGEST-' + digest(incident)[:32]
        refs = [{'evidence_id': 'EVID-' + str(i), 'payload_hash': digest({
            'run_id': run['run_id'], 'incident_id': run['incident_id'], 'signal': s,
            'correlation_id': incident['id'], 'resource': incident['resource']})}
            for i, s in enumerate(signals)]
        r['admission'].update(batch_sha256=digest(incident), references=deepcopy(signals))
        r['publication'].update(correlation=deepcopy(c), core=deepcopy(core), stored_evidence=deepcopy(refs))
        context.update(evidence=deepcopy(refs), verified_signals=[dict(ref, signal=deepcopy(s)) for ref, s in zip(refs, signals)])
        return c, r, core, context

    def test_supported_cardinality(self):
        for count in range(3, 21):
            with self.subTest(count=count):
                c, r, core, context = self.sized(count)
                self.assertEqual(verify_persisted_receipt(c, r, read_context=lambda _: (core, context)), core['run']['run_id'])

    def test_reject_outside_cardinality(self):
        for count in (0, 1, 2, 21, 30):
            with self.subTest(count=count):
                c, r, _, _ = self.sized(count)
                with self.assertRaises(ValueError):
                    validate_receipt(c, r)

    def test_five_receipts_exact(self):
        for fault in ('missing', 'extra', 'duplicate', 'invalid_id'):
            with self.subTest(fault=fault):
                c, r, _, _ = self.sized(5)
                refs = r['publication']['stored_evidence']
                if fault == 'missing': refs.pop()
                elif fault == 'extra': refs.append({'evidence_id': 'EXTRA', 'payload_hash': '0' * 64})
                elif fault == 'duplicate': refs[1]['evidence_id'] = refs[0]['evidence_id']
                else: refs[0]['evidence_id'] = 'bad/id'
                with self.assertRaises(ValueError):
                    validate_receipt(c, r)

    def test_json_type_alias_rejected_before_readback(self):
        c, r, core, context = self.sized(5)
        r['publication']['correlation']['incidents'][0]['production_authorized'] = 0
        self.assertEqual(c, r['publication']['correlation'])
        self.assertNotEqual(digest(c), digest(r['publication']['correlation']))
        calls = []
        with self.assertRaises(ValueError):
            verify_persisted_receipt(c, r, read_context=lambda run: (calls.append(run) or core, context))
        self.assertEqual(calls, [])

    def test_five_readback_requires_complete_reference_set(self):
        for fault in ('missing', 'duplicate'):
            with self.subTest(fault=fault):
                c, r, core, context = self.sized(5)
                if fault == 'missing': context['verified_signals'].pop()
                else: context['verified_signals'].append(deepcopy(context['verified_signals'][0]))
                with self.assertRaises(ValueError):
                    verify_persisted_receipt(c, r, read_context=lambda _: (core, context))


if __name__ == '__main__':
    unittest.main()
