"""Offline join integration: real adapters, mocked Core/GLPI HTTP; no live APIs."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from shared.acme_noc_glpi_join import join_incident_run_ticket_evidence
from test_acme_noc_glpi_join import CORE, LEDGER, NOC, REF, MockGLPI

CORE_RESPONSE = {
    'schema': 'aiops.core-demo-evidence-refs.v1', 'run_id': 'RUN-1',
    'classification': 'SYNTHETIC_ONLY', 'tenant_acl_qualified': False,
    'runtime_attested': False, 'event_link_verified': True,
    'items': [REF],
}


class Response:
    def __init__(self, payload, status=200, content_type='application/json', raw=None):
        self.status = status
        self.headers = {'Content-Type': content_type}
        self.body = json.dumps(payload).encode() if raw is None else raw
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, size): return self.body[:size]


class MockCore:
    def __init__(self, payload=None, **response_kw):
        self.payload = copy.deepcopy(CORE_RESPONSE if payload is None else payload)
        self.kw = response_kw
        self.calls = []
    def open(self, request, timeout):
        self.calls.append((request, timeout))
        return Response(self.payload, **self.kw)


def join(core_client=None, **kwargs):
    return join_incident_run_ticket_evidence(
        copy.deepcopy(CORE), copy.deepcopy(LEDGER), copy.deepcopy(NOC),
        core_evidence_base_url='http://aiops2-core:810',
        core_evidence_token='c' * 32, core_evidence_opener=core_client, **kwargs)


class AuthenticatedCoreRefsMockIntegrationTests(unittest.TestCase):
    def test_authenticated_core_get_matches_synthetic_refs_not_real_evidence(self):
        client = MockCore()
        out = join(client)
        self.assertEqual(out['core_evidence_ref_ids_verified'], ['EVD-1'])
        self.assertEqual(out['core_evidence_ref_verification'],
                         'CORE_GET_200_SYNTHETIC_REFS_MATCH_NO_TENANT_ATTESTATION')
        self.assertEqual(out['evidence_ids'], ['EVD-1'])
        self.assertEqual(out['verified_evidence_ids'], [])
        self.assertIsNone(out['verified_evidence_id'])
        self.assertEqual(out['evidence_verification'],
                         'UNKNOWN_NO_AUTHENTICATED_EVIDENCE_API_READ')
        self.assertIsNone(out['ticket_id'])
        self.assertEqual(len(client.calls), 1)
        request, timeout = client.calls[0]
        self.assertEqual(request.get_method(), 'GET')
        self.assertEqual(timeout, 4)
        self.assertEqual(request.full_url,
                         'http://aiops2-core:810/api/noc/runs/RUN-1/evidence-refs')
        self.assertEqual(request.get_header('Authorization'), 'Bearer ' + 'c'*32)

    def test_core_and_glpi_gets_independent_no_effects(self):
        core, glpi = MockCore(), MockGLPI()
        out = join(core, glpi_base_url='https://glpi.example.test',
                   glpi_session_token='s'*32, glpi_app_token='a'*32,
                   glpi_opener=glpi)
        self.assertEqual(out['ticket_id'], '12345')
        self.assertEqual(out['core_evidence_ref_ids_verified'], ['EVD-1'])
        self.assertEqual(out['verified_evidence_ids'], [])
        self.assertEqual(len(core.calls), 1)
        self.assertEqual(len(glpi.calls), 1)
        self.assertEqual(glpi.calls[0][0].get_method(), 'GET')

    def test_core_response_cross_run_unknown(self):
        client = MockCore({**CORE_RESPONSE, 'run_id': 'RUN-2'})
        out = join(client)
        self.assertEqual(out['core_evidence_ref_ids_verified'], [])
        self.assertIn('UNKNOWN', out['core_evidence_ref_verification'])

    def test_core_ref_digest_mismatch_unknown(self):
        bad = copy.deepcopy(CORE_RESPONSE)
        bad['items'][0]['payload_sha256'] = 'b'*64
        out = join(MockCore(bad))
        self.assertEqual(out['core_evidence_ref_ids_verified'], [])

    def test_core_ref_timestamp_mismatch_unknown(self):
        bad = copy.deepcopy(CORE_RESPONSE)
        bad['items'][0]['known_at'] = '2026-10-28T16:00:00+00:00'
        out = join(MockCore(bad))
        self.assertEqual(out['core_evidence_ref_ids_verified'], [])

    def test_extra_or_duplicate_refs_unknown(self):
        for items in ([REF, REF], [], [{**REF, 'evidence_id': 'EVD-2'}]):
            with self.subTest(items=items):
                bad = {**CORE_RESPONSE, 'items': items}
                self.assertEqual(join(MockCore(bad))['core_evidence_ref_ids_verified'], [])

    def test_core_unauthorized_or_bad_content_unknown(self):
        for kw in ({'status': 401}, {'content_type': 'text/html'},
                   {'raw': b'{"schema":1,"schema":2}'},
                   {'raw': b'{' + b' ' * 65537 + b'}'}):
            with self.subTest(kw=kw):
                self.assertEqual(join(MockCore(**kw))['core_evidence_ref_ids_verified'], [])

    def test_core_content_type_requires_exact_json_media_type(self):
        # HTTP is mocked. A JSON-shaped body with JSONP MIME must never
        # confirm even synthetic Core refs; a JSON charset is permitted.
        for media_type, accepted in (
            ('application/json', True),
            ('application/json; charset=utf-8', True),
            ('APPLICATION/JSON; charset=utf-8', True),
            ('application/jsonp', False),
            ('application/json-malformed', False),
            ('application/json-seq', False),
            ('text/html', False),
            ('', False),
        ):
            with self.subTest(media_type=media_type):
                client = MockCore(content_type=media_type)
                out = join(client)
                self.assertEqual(len(client.calls), 1)
                self.assertEqual(out['core_evidence_ref_ids_verified'],
                                 ['EVD-1'] if accepted else [])
                self.assertEqual(out['verified_evidence_ids'], [])
                self.assertIsNone(out['verified_evidence_id'])
                self.assertIsNone(out['ticket_id'])
                if not accepted:
                    self.assertIn('UNKNOWN', out['core_evidence_ref_verification'])

    def test_core_tenant_claim_unknown(self):
        bad = {**CORE_RESPONSE, 'organization_id': 'unqualified'}
        self.assertEqual(join(MockCore(bad))['core_evidence_ref_ids_verified'], [])

    def test_missing_credentials_no_get(self):
        client = MockCore()
        out = join_incident_run_ticket_evidence(CORE, LEDGER, NOC,
            core_evidence_base_url='http://aiops2-core:810', core_evidence_opener=client)
        self.assertEqual(client.calls, [])
        self.assertEqual(out['core_evidence_ref_ids_verified'], [])

    def test_untrusted_http_origin_no_get(self):
        client = MockCore()
        out = join_incident_run_ticket_evidence(CORE, LEDGER, NOC,
            core_evidence_base_url='http://untrusted.example:810',
            core_evidence_token='c'*32, core_evidence_opener=client)
        self.assertEqual(client.calls, [])
        self.assertEqual(out['core_evidence_ref_ids_verified'], [])

    def test_invalid_projection_no_core_get(self):
        client = MockCore()
        bad_core = {'run': {'run_id': 'RUN-2', 'incident_id': 'INC-1', 'mode': 'DEMO'}}
        out = join_incident_run_ticket_evidence(bad_core, LEDGER, NOC,
            core_evidence_base_url='http://aiops2-core:810',
            core_evidence_token='c'*32, core_evidence_opener=client)
        self.assertEqual(client.calls, [])
        self.assertEqual(out['core_evidence_ref_ids_verified'], [])
        self.assertEqual(out['core_evidence_ref_verification'], 'UNKNOWN_INVALID_CORE_PROJECTION')


if __name__ == '__main__': unittest.main()
