"""Offline contract tests only; no Core/GLPI HTTP or Debian attestation."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from shared.acme_itsm_evidence_link import project_itsm_evidence

RUN = {'run': {'run_id': 'RUN-1', 'incident_id': 'INC-1', 'mode': 'DEMO'}}
LEDGER = {
    'schema': 'aiops.demo-ledger-read.v1', 'run_id': 'RUN-1', 'mode': 'DEMO',
    'classification': 'DEMO_CORE_RECORDED_NOT_LIVE', 'source': 'CORE_AI_LEDGER_INTERNAL_READ',
    'tenant_acl_qualified': False, 'runtime_attested': False,
    'event_link_verified': True, 'evidence_classification': 'SYNTHETIC_ONLY',
    'evidence_refs': [{'evidence_id': 'EVD-1', 'source': 'core', 'payload_sha256': 'a'*64,
                       'known_at': '2026-10-29T16:00:00+00:00'}],
    'analyses': [{'analysis_id': 'AN-1', 'evidence_ids': ['EVD-1']}],
    'critiques': [{'critique_id': 'CR-1', 'analysis_id': 'AN-1', 'evidence_ids': ['EVD-1']}],
    'policy_decisions': [{'policy_decision_id': 'POL-1', 'analysis_id': 'AN-1', 'critique_id': 'CR-1'}],
}
NOC = {'run_id': 'RUN-1', 'incident_id': 'INC-1', 'ticket_id': '12345',
       'source_payload_authenticated': True, 'source_authentication': 'HMAC_SHA256_VERIFIED',
       'source_payload_sha256': 'b'*64, 'runtime_attested': False,
       'live_remediation_authorized': False}

class LinkTests(unittest.TestCase):
    def test_synthetic_correlation_no_glpi_attestation(self):
        out = project_itsm_evidence(RUN, LEDGER, NOC)
        self.assertEqual(out['state'], 'CORRELATED_UNATTESTED')
        self.assertEqual((out['incident_id'], out['run_id']), ('INC-1', 'RUN-1'))
        self.assertEqual(out['evidence_ids'], ['EVD-1'])
        self.assertEqual(out['glpi_ticket_claim'], '12345')
        self.assertIsNone(out['ticket_id'])
        self.assertFalse(out['tenant_acl_qualified'])
        self.assertFalse(out['runtime_attested'])
    def test_missing_sources_unknown(self):
        for core, ledger in ((None, LEDGER), (RUN, None), ({}, LEDGER)):
            self.assertEqual(project_itsm_evidence(core, ledger)['state'], 'UNKNOWN')
    def test_cross_run_unknown(self):
        self.assertEqual(project_itsm_evidence({'run': {**RUN['run'], 'run_id': 'RUN-2'}}, LEDGER)['state'], 'UNKNOWN')
    def test_live_rejected(self):
        self.assertEqual(project_itsm_evidence({'run': {**RUN['run'], 'mode': 'LIVE'}}, LEDGER)['state'], 'UNKNOWN')
    def test_unqualified_tenant_claim_rejected(self):
        self.assertEqual(project_itsm_evidence(RUN, {**LEDGER, 'tenant_acl_qualified': True})['state'], 'UNKNOWN')
    def test_runtime_attestation_claim_rejected(self):
        self.assertEqual(project_itsm_evidence(RUN, {**LEDGER, 'runtime_attested': True})['state'], 'UNKNOWN')
    def test_evidence_missing_rejected(self):
        self.assertEqual(project_itsm_evidence(RUN, {**LEDGER, 'evidence_refs': []})['state'], 'UNKNOWN')
    def test_evidence_hash_invalid_rejected(self):
        bad = [{**LEDGER['evidence_refs'][0], 'payload_sha256': 'fake'}]
        self.assertEqual(project_itsm_evidence(RUN, {**LEDGER, 'evidence_refs': bad})['state'], 'UNKNOWN')
    def test_cross_analysis_critique_rejected(self):
        bad = [{**LEDGER['critiques'][0], 'analysis_id': 'AN-OTHER'}]
        self.assertEqual(project_itsm_evidence(RUN, {**LEDGER, 'critiques': bad})['state'], 'UNKNOWN')
    def test_cross_analysis_policy_rejected(self):
        bad = [{**LEDGER['policy_decisions'][0], 'analysis_id': 'AN-OTHER'}]
        self.assertEqual(project_itsm_evidence(RUN, {**LEDGER, 'policy_decisions': bad})['state'], 'UNKNOWN')
    def test_unverified_noc_ticket_is_never_connected(self):
        for noc in (None, {**NOC, 'source_payload_authenticated': False},
                    {**NOC, 'run_id': 'RUN-OTHER'}, {**NOC, 'ticket_id': 'SIM-GLPI-1'}):
            out = project_itsm_evidence(RUN, LEDGER, noc)
            self.assertEqual(out['state'], 'CORRELATED_UNATTESTED')
            self.assertIsNone(out['glpi_ticket_claim'])
            self.assertIsNone(out['ticket_id'])
    def test_no_network_or_auth_bypass_surface(self):
        out = project_itsm_evidence(RUN, LEDGER)
        self.assertNotIn('token', str(out).lower())
        self.assertFalse(out['live_remediation_authorized'])
        self.assertFalse(out['effect_applied'])

if __name__ == '__main__':
    unittest.main()
