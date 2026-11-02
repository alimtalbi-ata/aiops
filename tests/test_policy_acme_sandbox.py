"""Source-only Policy sandbox security tests; not host E2E."""
import os
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from policy import acme_sandbox as p

TOKEN = 'acme-sandbox-test-internal-token-not-human'
ATTEMPT = 'ACME-SIM-POLICY-0001'
def docs():
    core = {'attempt_id': ATTEMPT, 'tenant_id': 'ACME-TEST',
            'incident_id': 'INC-SIM-1', 'run_id': 'RUN-SIM-1',
            'ticket_id': 'SIM-GLPI-1', 'proposal_id': 'PROP-SIM-1',
            'incident_status': 'PREPARED', 'run_status': 'PREPARED',
            'ticket_status': 'PREPARED', 'ticket_authority': 'SIMULATED_ONLY',
            'glpi_mode': 'SIMULATED_ONLY', 'source_event_count': 7,
            'source_hashes_qualified': True, 'analysis_validated': True,
            'critic_validated': True, 'evidence_count': 2,
            'request_sha256': 'a'*64,
            'source_event_ids': ['SYN-EVT-'+str(i) for i in range(7)],
            'human_approved': False, 'execution_allowed': False,
            'effect_allowed': False, 'live_effects_allowed': False,
            'real_glpi_writes_allowed': False}
    twin = {k: core[k] for k in ('attempt_id','tenant_id','incident_id',
                                  'run_id','ticket_id','proposal_id')}
    twin.update({'approval_id': 'SIM-APP-1', 'approval_issuer': 'TWIN_ACME_SIMULATED',
                 'issuer_id': 'twin-acme-test', 'approval_kind': 'SIMULATED',
                 'approval_status': 'SIMULATED', 'approval_phase': 'PRE_RESOLUTION',
                 'core_status_at_issuance': 'PREPARED',
                 'core_request_sha256': 'a'*64,
                 'core_source_event_ids': core['source_event_ids'],
                 'human_approved': False, 'execution_allowed': False,
                 'effect_allowed': False, 'live_effects_allowed': False,
                 'real_glpi_writes_allowed': False})
    return core,twin

class PolicySandboxTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            'AIOPS_ACME_SANDBOX_ENABLED': 'true', 'AIOPS_INTERNAL_TOKEN': TOKEN})
        self.env.start()
        app = FastAPI()
        app.include_router(p.router)
        self.client = TestClient(app)
    def tearDown(self):
        self.env.stop()
    def test_01_no_auth_and_disabled(self):
        self.assertEqual(self.client.get('/api/sandbox/acme/e2e/'+ATTEMPT).status_code,401)
        with patch.dict(os.environ, {'AIOPS_ACME_SANDBOX_ENABLED':'false'}):
            self.assertEqual(self.client.get('/api/sandbox/acme/capabilities').status_code,503)
    def test_02_strict_prepared_and_simulated_join(self):
        core,twin=docs()
        self.assertEqual(p.qualify(ATTEMPT,core,twin), ('incident_id','run_id','ticket_id','proposal_id'))
        twin['approval_kind']='HUMAN'
        with self.assertRaises(Exception):
            p.qualify(ATTEMPT,core,twin)
    def test_03_resolved_before_worker_denied(self):
        core,twin=docs()
        core['run_status']='RESOLVED'
        with self.assertRaises(Exception):
            p.qualify(ATTEMPT,core,twin)
    def test_04_cross_tenant_or_live_denied(self):
        core,twin=docs()
        twin['tenant_id']='FOREIGN'
        with self.assertRaises(Exception):
            p.qualify(ATTEMPT,core,twin)
        intent={'attempt_id':ATTEMPT,'tenant_id':'ACME-TEST','scenario_id':'ACME-SAN-PAYMENTS',
                'mode':'LIVE','approval_issuer':'TWIN_ACME_SIMULATED',
                'idempotency_key':ATTEMPT,'live_effects_allowed':False,
                'incident_id':'INC-SIM-1','run_id':'RUN-SIM-1',
                'ticket_id':'SIM-GLPI-1','proposal_id':'PROP-SIM-1','approval_id':'SIM-APP-1'}
        self.assertEqual(self.client.post('/api/sandbox/acme/e2e',json=intent,
            headers={'Authorization':'Bearer '+TOKEN}).status_code,403)
    def test_05_policy_fail_closed_on_autonomy_unavailable(self):
        core,twin=docs()
        with patch.object(p,'fetch_component',side_effect=[core,twin]), patch(
                'policy.main.evaluate',return_value={'state':'BLOCKED','decision':'ESCALATE'}):
            self.assertEqual(self.client.get('/api/sandbox/acme/e2e/'+ATTEMPT,
                headers={'Authorization':'Bearer '+TOKEN}).status_code,503)

if __name__ == '__main__':
    unittest.main()
