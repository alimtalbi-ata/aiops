"""Offline HTTP mocks only; no real GLPI/Core API, credentials or Debian test."""
import io
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from shared.acme_glpi_ticket_read import read_verified_glpi_link

REF = {'evidence_id': 'EVD-1', 'source': 'CORE', 'payload_sha256': 'a'*64,
       'known_at': '2026-10-29T23:00:00+00:00'}
BASE = {'schema': 'aiops.acme-itsm-evidence-link.v1', 'state': 'CORRELATED_UNATTESTED',
        'run_id': 'RUN-1', 'incident_id': 'INC-1', 'glpi_ticket_claim': '12345',
        'ticket_id': None, 'ticket_verification': 'NOT_TESTED_NO_GLPI_API_READ',
        'classification': 'SYNTHETIC_ONLY', 'runtime_attested': False,
        'tenant_acl_qualified': False, 'effect_applied': False,
        'live_remediation_authorized': False,
        'evidence_source_contract': 'CORE_AI_LEDGER_INTERNAL_READ',
        'evidence_refs': [REF], 'evidence_ids': ['EVD-1']}
GOOD = {'id': 12345, 'run_id': 'RUN-1', 'incident_id': 'INC-1', 'is_deleted': 0}


class Response:
    def __init__(self, body, status=200, content_type='application/json'):
        self.body = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.status = status
        self.headers = {'Content-Type': content_type}
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, size): return self.body[:size]


class MockOpener:
    def __init__(self, response=None, error=None):
        self.response = response or Response(GOOD)
        self.error = error
        self.calls = []
    def open(self, request, timeout):
        self.calls.append((request, timeout))
        if self.error: raise self.error
        return self.response


def verify(correlation=BASE, opener=None, **changes):
    return read_verified_glpi_link(correlation, base_url='https://glpi.example.test',
        session_token='s' * 32, app_token='a' * 32,
        opener=opener or MockOpener(), **changes)


class GLPIReadOnlyHTTPMockTests(unittest.TestCase):
    def test_explicit_link_200_and_auth_headers_only(self):
        client = MockOpener()
        out = verify(opener=client)
        self.assertEqual(out['ticket_id'], '12345')
        self.assertEqual(out['ticket_verification'], 'GLPI_GET_200_EXPLICIT_LINK_MATCH_NO_TENANT_ATTESTATION')
        self.assertEqual(out['evidence_ids'], ['EVD-1'])
        self.assertFalse(out['runtime_attested'])
        self.assertFalse(out['tenant_acl_qualified'])
        request, timeout = client.calls[0]
        self.assertEqual(request.get_method(), 'GET')
        self.assertEqual(request.full_url, 'https://glpi.example.test/apirest.php/Ticket/12345')
        self.assertEqual(request.get_header('Session-token'), 's' * 32)
        self.assertEqual(request.get_header('App-token'), 'a' * 32)
        self.assertEqual(timeout, 4)
        self.assertNotIn('s' * 32, str(out))

    def test_missing_link_fields_stays_unknown(self):
        for key in ('incident_id', 'run_id', 'is_deleted'):
            with self.subTest(key=key):
                ticket = {k: v for k, v in GOOD.items() if k != key}
                self.assertIsNone(verify(opener=MockOpener(Response(ticket)))['ticket_id'])

    def test_cross_run_or_incident_stays_unknown(self):
        for key, value in (('run_id', 'RUN-2'), ('incident_id', 'INC-2'), ('id', 12346)):
            with self.subTest(key=key):
                self.assertIsNone(verify(opener=MockOpener(Response({**GOOD, key: value})))['ticket_id'])

    def test_deleted_and_boolean_id_rejected(self):
        for change in ({'is_deleted': 1}, {'is_deleted': False}, {'id': True}):
            self.assertIsNone(verify(opener=MockOpener(Response({**GOOD, **change})))['ticket_id'])

    def test_auth_failure_and_unavailable_stay_unknown(self):
        for status in (301, 401, 403, 404, 429, 500, 503):
            with self.subTest(status=status):
                out = verify(opener=MockOpener(Response(GOOD, status=status)))
                self.assertIsNone(out['ticket_id'])
                self.assertIn('UNKNOWN', out['ticket_verification'])
        self.assertIsNone(verify(opener=MockOpener(error=OSError('no network')))['ticket_id'])

    def test_non_json_duplicate_keys_and_oversized_rejected(self):
        responses = [Response(GOOD, content_type='text/html'),
                     Response(b'{"id":12345,"id":12345,"run_id":"RUN-1","incident_id":"INC-1","is_deleted":0}'),
                     Response(b'{' + b'x' * 65536 + b'}')]
        for response in responses:
            self.assertIsNone(verify(opener=MockOpener(response))['ticket_id'])

    def test_no_claim_no_request(self):
        for claim in (None, 'SIM-1', '0', '123/../1', '00123', '12?3'):
            client = MockOpener()
            self.assertIsNone(verify({**BASE, 'glpi_ticket_claim': claim}, opener=client)['ticket_id'])
            self.assertEqual(client.calls, [])

    def test_unqualified_correlation_no_request(self):
        client = MockOpener()
        self.assertIsNone(verify({**BASE, 'state': 'UNKNOWN'}, opener=client)['ticket_id'])
        self.assertEqual(client.calls, [])

    def test_http_origin_and_missing_credentials_fail_closed(self):
        for changes in ({'base_url': 'http://glpi.example.test'},
                        {'base_url': 'https://glpi.example.test/other'},
                        {'base_url': 'https://u:p@glpi.example.test'},
                        {'base_url': 'https://glpi.example.test?x=1'},
                        {'session_token': ''}, {'app_token': ''}):
            client = MockOpener()
            args = {'base_url': 'https://glpi.example.test', 'session_token': 's'*32,
                    'app_token': 'a'*32, 'opener': client}
            args.update(changes)
            out = read_verified_glpi_link(BASE, **args)
            self.assertIsNone(out['ticket_id'])
            self.assertEqual(client.calls, [])

    def test_unknown_projection_cannot_be_upgraded(self):
        out = read_verified_glpi_link(None)
        self.assertEqual(out['state'], 'UNKNOWN')
        self.assertIsNone(out['ticket_id'])

    def test_unqualified_provenance_cannot_trigger_glpi_get(self):
        for field, value in (('schema', 'other'), ('classification', 'REAL'),
                             ('evidence_source_contract', 'UNVERIFIED'),
                             ('tenant_acl_qualified', True), ('runtime_attested', True),
                             ('effect_applied', True), ('live_remediation_authorized', True)):
            with self.subTest(field=field):
                client = MockOpener()
                result = verify({**BASE, field: value}, opener=client)
                self.assertIsNone(result['ticket_id'])
                self.assertEqual(client.calls, [])

    def test_unlinked_evidence_cannot_trigger_glpi_get(self):
        for refs, ids in (([], ['EVD-1']), ([REF], ['EVD-2']),
                          ([REF, REF], ['EVD-1', 'EVD-2']),
                          ([{**REF, 'payload_sha256': 'bad'}], ['EVD-1']),
                          ([{**REF, 'source': 'x/y'}], ['EVD-1']),
                          ([{**REF, 'known_at': ''}], ['EVD-1'])):
            with self.subTest(refs=refs, ids=ids):
                client = MockOpener()
                result = verify({**BASE, 'evidence_refs': refs, 'evidence_ids': ids}, opener=client)
                self.assertIsNone(result['ticket_id'])
                self.assertEqual(client.calls, [])

    def test_invalid_projection_cannot_keep_correlated_state(self):
        client = MockOpener()
        result = verify({**BASE, 'evidence_refs': [{**REF, 'payload_sha256': 'bad'}]},
                        opener=client)
        self.assertEqual(result['state'], 'UNKNOWN')
        self.assertEqual(result['classification'], 'UNKNOWN')
        self.assertEqual(result['ticket_verification'],
                         'UNKNOWN_INVALID_CORE_EVIDENCE_PROJECTION')
        self.assertIsNone(result['run_id'])
        self.assertIsNone(result['incident_id'])
        self.assertEqual(result['evidence_ids'], [])
        self.assertEqual(result['evidence_refs'], [])
        self.assertIsNone(result['ticket_id'])
        self.assertEqual(client.calls, [])

    def test_untrusted_evidence_timestamps_rejected_before_glpi_get(self):
        for known_at in ('not-a-date', '2026-10-29T23:00:00',
                         '2999-01-01T00:00:00+00:00', '2026-10-29'):
            with self.subTest(known_at=known_at):
                client = MockOpener()
                result = verify({**BASE, 'evidence_refs': [{**REF, 'known_at': known_at}]},
                                opener=client)
                self.assertEqual(result['state'], 'UNKNOWN')
                self.assertIsNone(result['ticket_id'])
                self.assertEqual(client.calls, [])

    def test_forged_legacy_ids_only_cannot_trigger_glpi_get(self):
        client = MockOpener()
        result = verify({key: BASE[key] for key in ('state', 'run_id', 'incident_id',
                         'glpi_ticket_claim', 'evidence_ids')}, opener=client)
        self.assertIsNone(result['ticket_id'])
        self.assertEqual(client.calls, [])


if __name__ == '__main__': unittest.main()
