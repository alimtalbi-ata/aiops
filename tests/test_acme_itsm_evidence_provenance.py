"""Mock/snapshot contract tests; NO authenticated Core/GLPI HTTP or Debian runtime."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from shared.acme_itsm_evidence_link import project_itsm_evidence

CORE = {'run': {'run_id': 'RUN-1', 'incident_id': 'INC-1', 'mode': 'DEMO'}}
REF = {'evidence_id': 'EVD-1', 'source': 'core', 'payload_sha256': 'a' * 64,
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
       'source_payload_sha256': 'b' * 64,
       'runtime_attested': False, 'live_remediation_authorized': False}


class EvidenceProvenanceMockTests(unittest.TestCase):
    def project(self, **change):
        ledger = copy.deepcopy(LEDGER)
        ledger['evidence_refs'][0].update(change)
        return project_itsm_evidence(CORE, ledger, NOC)

    def test_exact_read_only_provenance_for_portal(self):
        out = self.project()
        self.assertEqual(out['state'], 'CORRELATED_UNATTESTED')
        self.assertEqual(out['evidence_refs'], [REF])
        self.assertEqual(out['evidence_source_contract'], 'CORE_AI_LEDGER_INTERNAL_READ')
        self.assertEqual(out['classification'], 'SYNTHETIC_ONLY')
        self.assertEqual((out['incident_id'], out['run_id']), ('INC-1', 'RUN-1'))
        self.assertEqual(out['glpi_ticket_claim'], '12345')
        self.assertIsNone(out['ticket_id'])
        self.assertEqual(out['ticket_verification'], 'NOT_TESTED_NO_GLPI_API_READ')
        self.assertFalse(out['runtime_attested'])
        self.assertFalse(out['tenant_acl_qualified'])

    def test_reject_naive_timestamp(self):
        self.assertEqual(self.project(known_at='2026-10-29T16:00:00')['state'], 'UNKNOWN')

    def test_reject_future_timestamp(self):
        self.assertEqual(self.project(known_at='2099-01-01T00:00:00+00:00')['state'], 'UNKNOWN')

    def test_reject_unparseable_timestamp(self):
        self.assertEqual(self.project(known_at='not-a-time')['state'], 'UNKNOWN')

    def test_reject_unqualified_source(self):
        for source in ('', '<script>alert(1)</script>', 'bad source', 'a' * 129):
            with self.subTest(source=source):
                self.assertEqual(self.project(source=source)['state'], 'UNKNOWN')

    def test_reject_extra_evidence_fields(self):
        out = self.project(observed_at='2026-10-29T16:00:00+00:00')
        self.assertEqual(out['state'], 'UNKNOWN')
        self.assertEqual(out['evidence_refs'], [])

    def test_reject_cross_run_reference(self):
        self.assertEqual(self.project(evidence_id='EVD-OTHER')['state'], 'UNKNOWN')

    def test_reject_bad_digest(self):
        self.assertEqual(self.project(payload_sha256='not-sha')['state'], 'UNKNOWN')

    def test_unknown_never_exposes_refs_or_ticket(self):
        out = project_itsm_evidence(CORE, None, NOC)
        self.assertEqual(out['state'], 'UNKNOWN')
        self.assertEqual(out['evidence_refs'], [])
        self.assertIsNone(out['ticket_id'])
        self.assertIsNone(out['evidence_source_contract'])

    def test_unqualified_tenant_scope_denied(self):
        out = self.project(tenant_id='tenant-A')
        self.assertEqual(out['state'], 'UNKNOWN')
        self.assertIsNone(out['ticket_id'])

    def test_live_mode_denied(self):
        core = {'run': {**CORE['run'], 'mode': 'LIVE'}}
        self.assertEqual(project_itsm_evidence(core, LEDGER, NOC)['state'], 'UNKNOWN')

    def test_no_claim_becomes_verified_ticket(self):
        out = project_itsm_evidence(CORE, LEDGER, {**NOC, 'ticket_id': 'SIM-GLPI-1'})
        self.assertEqual(out['state'], 'CORRELATED_UNATTESTED')
        self.assertIsNone(out['glpi_ticket_claim'])
        self.assertIsNone(out['ticket_id'])


if __name__ == '__main__':
    unittest.main()
