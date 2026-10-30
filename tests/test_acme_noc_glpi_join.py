"""Offline integration of real projectors with mocked GLPI HTTP; no live APIs."""
import copy
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from shared.acme_noc_glpi_join import join_incident_run_ticket_evidence

CORE = {'run': {'run_id': 'RUN-1', 'incident_id': 'INC-1', 'mode': 'DEMO'}}
REF = {'evidence_id': 'EVD-1', 'source': 'core', 'payload_sha256': 'a'*64,
       'known_at': '2026-10-29T16:00:00+00:00'}
LEDGER = {
    'schema': 'aiops.demo-ledger-read.v1', 'run_id': 'RUN-1', 'mode': 'DEMO',
    'classification': 'DEMO_CORE_RECORDED_NOT_LIVE',
    'source': 'CORE_AI_LEDGER_INTERNAL_READ',
    'tenant_acl_qualified': False, 'runtime_attested': False,
    'event_link_verified': True, 'evidence_classification': 'SYNTHETIC_ONLY',
    'evidence_refs': [REF],
    'analyses': [{'analysis_id': 'AN-1', 'evidence_ids': ['EVD-1']}],
    'critiques': [{'critique_id': 'CR-1', 'analysis_id': 'AN-1',
                   'evidence_ids': ['EVD-1']}],
    'policy_decisions': [{'policy_decision_id': 'POL-1', 'analysis_id': 'AN-1',
                          'critique_id': 'CR-1'}],
}
NOC = {'schema': 'aiops.noc-runtime-envelope.v1',
       'source_mode': 'ALLOWLISTED_HMAC_SIGNED_READ_MODEL',
       'provenance': 'AUTHENTICATED_SOURCE_PAYLOAD_NOT_RUNTIME_ATTESTATION',
       'production_qualified': False, 'ticket_provenance': 'UPSTREAM_SIGNED_CLAIM',
       'run_id': 'RUN-1', 'incident_id': 'INC-1', 'ticket_id': '12345',
       'source_payload_authenticated': True,
       'source_authentication': 'HMAC_SHA256_VERIFIED',
       'source_payload_sha256': 'b'*64,
       'runtime_attested': False, 'live_remediation_authorized': False}
GOOD_TICKET = {'id': 12345, 'run_id': 'RUN-1', 'incident_id': 'INC-1', 'is_deleted': 0}


class Response:
    status = 200
    headers = {'Content-Type': 'application/json'}
    def __init__(self, ticket):
        self.body = json.dumps(ticket).encode()
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, limit): return self.body[:limit]


class MockGLPI:
    def __init__(self, ticket=None):
        self.ticket = GOOD_TICKET if ticket is None else ticket
        self.calls = []
    def open(self, request, timeout):
        self.calls.append((request, timeout))
        return Response(self.ticket)


def join(core=None, ledger=None, noc=None, client=None, **kw):
    return join_incident_run_ticket_evidence(
        copy.deepcopy(CORE if core is None else core),
        copy.deepcopy(LEDGER if ledger is None else ledger),
        copy.deepcopy(NOC if noc is None else noc),
        glpi_base_url='https://glpi.example.test',
        glpi_session_token='s'*32, glpi_app_token='a'*32,
        glpi_opener=client, **kw)


class ReadOnlyJoinMockIntegrationTests(unittest.TestCase):
    def test_full_path_glpi_get_with_matching_ids_only(self):
        client = MockGLPI()
        out = join(client=client)
        self.assertEqual((out['incident_id'], out['run_id'], out['ticket_id']),
                         ('INC-1', 'RUN-1', '12345'))
        self.assertEqual(out['evidence_ids'], ['EVD-1'])
        self.assertEqual(out['evidence_refs'], [REF])
        self.assertEqual(out['classification'], 'SYNTHETIC_ONLY')
        self.assertEqual(out['state'], 'CORRELATED_UNATTESTED')
        self.assertFalse(out['runtime_attested'])
        self.assertFalse(out['tenant_acl_qualified'])
        self.assertEqual(out['ticket_verification'],
                         'GLPI_GET_200_EXPLICIT_LINK_MATCH_NO_TENANT_ATTESTATION')
        self.assertEqual(len(client.calls), 1)
        request, timeout = client.calls[0]
        self.assertEqual(request.get_method(), 'GET')
        self.assertEqual(timeout, 4)
        self.assertEqual(request.full_url,
                         'https://glpi.example.test/apirest.php/Ticket/12345')

    def test_cross_run_ticket_never_verified(self):
        client = MockGLPI({**GOOD_TICKET, 'run_id': 'RUN-2'})
        out = join(client=client)
        self.assertIsNone(out['ticket_id'])
        self.assertIn('UNKNOWN', out['ticket_verification'])
        self.assertEqual(len(client.calls), 1)

    def test_no_noc_claim_no_get(self):
        client = MockGLPI()
        out = join(noc={}, client=client)
        self.assertIsNone(out['ticket_id'])
        self.assertIsNone(out['glpi_ticket_claim'])
        self.assertEqual(client.calls, [])

    def test_synthetic_noc_ticket_no_get(self):
        client = MockGLPI()
        out = join(noc={**NOC, 'ticket_id': 'SIM-123'}, client=client)
        self.assertIsNone(out['ticket_id'])
        self.assertEqual(client.calls, [])

    def test_unqualified_evidence_no_get_and_no_ids(self):
        client = MockGLPI()
        bad = copy.deepcopy(LEDGER)
        bad['evidence_refs'][0]['payload_sha256'] = 'unverified'
        out = join(ledger=bad, client=client)
        self.assertEqual(out['state'], 'UNKNOWN')
        self.assertEqual(out['evidence_ids'], [])
        self.assertEqual(out['evidence_refs'], [])
        self.assertIsNone(out['ticket_id'])
        self.assertIsNone(out['incident_id'])
        self.assertIsNone(out['run_id'])
        self.assertEqual(client.calls, [])

    def test_cross_run_core_no_get(self):
        client = MockGLPI()
        out = join(core={'run': {'run_id': 'RUN-2', 'incident_id': 'INC-1',
                                'mode': 'DEMO'}}, client=client)
        self.assertEqual(out['state'], 'UNKNOWN')
        self.assertIsNone(out['ticket_id'])
        self.assertEqual(client.calls, [])

    def test_missing_credentials_no_get(self):
        client = MockGLPI()
        out = join_incident_run_ticket_evidence(
            CORE, LEDGER, NOC, glpi_base_url='https://glpi.example.test',
            glpi_opener=client)
        self.assertIsNone(out['ticket_id'])
        self.assertEqual(out['evidence_ids'], ['EVD-1'])
        self.assertEqual(client.calls, [])

    def test_extreme_ledger_timezone_never_triggers_glpi_or_core_get(self):
        # Integration of the actual projector and join; HTTP clients mocked.
        # The projector previously raised OverflowError before either reader.
        for known_at in ('0001-01-01T00:00:00+14:00',
                         '9999-12-31T23:59:59-14:00'):
            with self.subTest(known_at=known_at):
                ledger = copy.deepcopy(LEDGER)
                ledger['evidence_refs'][0]['known_at'] = known_at
                glpi, core = MockGLPI(), MockGLPI()
                out = join(ledger=ledger, client=glpi,
                           core_evidence_base_url='http://aiops2-core:810',
                           core_evidence_token='c' * 32,
                           core_evidence_opener=core)
                self.assertEqual(out['state'], 'UNKNOWN')
                self.assertIsNone(out['incident_id'])
                self.assertIsNone(out['run_id'])
                self.assertIsNone(out['ticket_id'])
                self.assertEqual(out['evidence_ids'], [])
                self.assertEqual(out['core_evidence_ref_ids_verified'], [])
                self.assertEqual(out['verified_evidence_ids'], [])
                self.assertEqual(glpi.calls, [])
                self.assertEqual(core.calls, [])

    def test_input_snapshots_not_mutated(self):
        core, ledger, noc = copy.deepcopy(CORE), copy.deepcopy(LEDGER), copy.deepcopy(NOC)
        before = copy.deepcopy((core, ledger, noc))
        join_incident_run_ticket_evidence(core, ledger, noc)
        self.assertEqual((core, ledger, noc), before)


    def test_glpi_confirmation_never_authenticates_ledger_evidence(self):
        # HTTP transport is mocked; no independent Evidence API read occurs.
        client = MockGLPI()
        out = join(client=client)
        self.assertEqual(out['ticket_id'], '12345')
        self.assertEqual(out['evidence_ids'], ['EVD-1'])
        self.assertIsNone(out['verified_evidence_id'])
        self.assertEqual(out['verified_evidence_ids'], [])
        self.assertEqual(out['evidence_verification'],
                         'UNKNOWN_NO_AUTHENTICATED_EVIDENCE_API_READ')
        self.assertEqual(len(client.calls), 1)

    def test_unavailable_glpi_cannot_promote_evidence_reference(self):
        client = MockGLPI()
        out = join_incident_run_ticket_evidence(CORE, LEDGER, NOC,
                                                 glpi_opener=client)
        self.assertIsNone(out['ticket_id'])
        self.assertEqual(out['evidence_ids'], ['EVD-1'])
        self.assertIsNone(out['verified_evidence_id'])
        self.assertEqual(out['verified_evidence_ids'], [])
        self.assertEqual(out['evidence_verification'],
                         'UNKNOWN_NO_AUTHENTICATED_EVIDENCE_API_READ')
        self.assertEqual(client.calls, [])

    def test_invalid_core_has_no_verified_evidence(self):
        client = MockGLPI()
        out = join(core={'run': {'run_id': 'RUN-2', 'incident_id': 'INC-1',
                                'mode': 'DEMO'}}, client=client)
        self.assertEqual(out['state'], 'UNKNOWN')
        self.assertEqual(out['evidence_ids'], [])
        self.assertIsNone(out['verified_evidence_id'])
        self.assertEqual(out['verified_evidence_ids'], [])
        self.assertEqual(out['evidence_verification'],
                         'UNKNOWN_NO_AUTHENTICATED_EVIDENCE_API_READ')
        self.assertEqual(client.calls, [])


if __name__ == '__main__': unittest.main()
