import unittest
from datetime import datetime, timezone
from app.shared.remediation_lab import load_catalog, validate_proposal, evaluate_simulation

NOW = datetime(2026, 10, 27, 19, 24, tzinfo=timezone.utc)

def fixture(mode='DEMO'):
    p = {'proposal_id':'P-1','recipe_id':'ansible-service-restart','recipe_version':'1.0.0',
         'target_ci':'ACME-LNX-01','parameters':{'service':'erp','credential_ref':'vault://acme/erp'},
         'mode':mode,'requested_by':'analyst-1'}
    _, digest = validate_proposal(p)
    d = {'state':'APPROVED','proposal_digest':digest,'actor_id':'operator-2',
         'actor_role':'approver','authenticated':True,'expires_at':'2026-10-27T20:00:00Z',
         'requested_by':'analyst-1'}
    checks = {'ci_fresh':True,'owner_fenced':True,'service_exists':True,'maintenance_window':True}
    return p,d,checks

class RemediationLabTests(unittest.TestCase):
    def test_catalog_has_all_requested_adapter_families(self):
        self.assertEqual(len(load_catalog()),8)
        self.assertEqual({r['kind'] for r in load_catalog().values()},
                         {'bash','python','ansible','linux_cli','network_cli','db_cli','api'})
        self.assertTrue(all(r['implementation']=='SIMULATOR_ONLY' for r in load_catalog().values()))

    def test_simulation_no_effect_and_redacted_secret(self):
        p,d,c = fixture()
        result = evaluate_simulation(p,d,c,now=NOW)
        self.assertEqual(result['status'],'SIMULATED')
        self.assertFalse(result['effect_applied'])
        self.assertEqual(result['parameters']['credential_ref'],'[REDACTED]')
        self.assertNotIn('vault://',str(result))
        self.assertEqual(result['postchecks'],'NOT_RUN')

    def test_live_always_blocked_even_with_approval(self):
        p,d,c = fixture(mode='LIVE')
        self.assertEqual(evaluate_simulation(p,d,c,now=NOW)['reason'],'LIVE_NOT_QUALIFIED')

    def test_rejected_and_expired(self):
        p,d,c = fixture()
        d['state']='REJECTED'
        self.assertEqual(evaluate_simulation(p,d,c,now=NOW)['status'],'BLOCKED')
        d['state']='APPROVED';d['expires_at']='2026-10-27T19:00:00Z'
        self.assertEqual(evaluate_simulation(p,d,c,now=NOW)['reason'],'APPROVAL_EXPIRED')

    def test_changed_proposal_invalidates_approval(self):
        p,d,c = fixture();p['parameters']['service']='other'
        self.assertEqual(evaluate_simulation(p,d,c,now=NOW)['reason'],'APPROVAL_BINDING_MISMATCH')

    def test_unauthenticated_and_self_approval(self):
        p,d,c = fixture();d['authenticated']=False
        self.assertEqual(evaluate_simulation(p,d,c,now=NOW)['reason'],'APPROVER_NOT_VERIFIED')
        d['authenticated']=True;d['actor_id']='analyst-1'
        self.assertEqual(evaluate_simulation(p,d,c,now=NOW)['reason'],'SEPARATION_OF_DUTIES_FAILED')

    def test_preconditions_missing_or_false(self):
        p,d,c = fixture();del c['owner_fenced']
        self.assertEqual(evaluate_simulation(p,d,c,now=NOW)['reason'],'PRECONDITIONS_MISSING')
        c['owner_fenced']=False
        self.assertEqual(evaluate_simulation(p,d,c,now=NOW)['reason'],'PRECONDITIONS_FAILED')

    def test_no_arbitrary_recipe_target_or_parameter(self):
        p,d,c = fixture();p['recipe_id']='shell-anything'
        with self.assertRaisesRegex(ValueError,'recipe_not_allowlisted'):validate_proposal(p)
        p,d,c=fixture();p['target_ci']='ACME-DB-01'
        with self.assertRaisesRegex(ValueError,'target_out_of_scope'):validate_proposal(p)
        p,d,c=fixture();p['parameters']['service']='erp;rm -rf /'
        with self.assertRaisesRegex(ValueError,'parameter_service_invalid'):validate_proposal(p)

    def test_secret_value_rejected_and_boolean_integer_rejected(self):
        p,d,c=fixture();p['parameters']['credential_ref']='plaintext-password'
        with self.assertRaises(ValueError):validate_proposal(p)
        p,d,c=fixture();p['recipe_id']='glpi-api-ticket-note';p['target_ci']='ACME-GLPI-1';p['parameters']={'ticket_id':True,'credential_ref':'vault://x'}
        with self.assertRaises(ValueError):validate_proposal(p)

    def test_deterministic_idempotency_receipt(self):
        p,d,c=fixture()
        a=evaluate_simulation(p,d,c,now=NOW);b=evaluate_simulation(p,d,c,now=NOW)
        self.assertEqual(a['idempotency_key'],b['idempotency_key'])
        self.assertFalse(a['effect_applied'])

if __name__ == '__main__':
    unittest.main()
