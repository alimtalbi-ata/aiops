"""Offline fixtures reuse the real INT-06A qualification function."""
import unittest
from copy import deepcopy
from portal.acme_runtime_context import digest
from portal.acme_authority_readers import collect_prepared


class AuthorityReadersTests(unittest.TestCase):
    def setUp(self):
        self.e = dict(tenant_id='ACME-TEST', incident_id='INC-001',
                      impact_incident_id='INC-002', run_id='RUN-001',
                      attempt_id='ACME-SIM-001', snapshot_id='SNAP-001')
        self.i = {k: self.e[k] for k in ('tenant_id','incident_id','run_id','attempt_id')}
        self.i.update(proposal_id='PROP-001', ticket_id='SIM-GLPI-001',
                      approval_id='SIM-APP-001', idempotency_key=self.e['attempt_id'],
                      scenario_id='ACME-SAN-PAYMENTS', mode='SIMULATION',
                      approval_issuer='TWIN_ACME_SIMULATED', human_approved=False,
                      execution_allowed=False, effect_allowed=False)
        self.rows = {}
        self.calls = []
        for a in ('core','twin','policy'):
            content = dict(self.e, **self.i)
            self.rows[a] = dict(authority=a, scope='RUNTIME_SANDBOX',
                                source_id=a+'-001', source_ref='fixture:'+a,
                                observed_at='2026-11-18T09:00:00.123456Z',
                                snapshot_id=self.e['snapshot_id'], content=content,
                                content_sha256=digest(content))
        self.rows['core']['content'].update(run_status='PREPARED', incident_status='PREPARED',
            version=1, authority_manifest={a:digest(self.rows[a]) for a in ('twin','policy')})
        self.rehash()
        self.readers = {a: lambda a=a: self.read(a) for a in self.rows}

    def rehash(self):
        self.rows['core']['content_sha256'] = digest(self.rows['core']['content'])

    def read(self, a):
        self.calls.append(a)
        return self.rows[a]

    def run_adapter(self):
        r = collect_prepared(self.e,self.i,self.readers,{a+'-001':30 for a in self.rows},
            as_of_utc='2026-11-18T09:00:30.123456Z',
            source_registry={a:a+'-001' for a in self.rows})
        self.assertFalse(r['runtime_attested'])
        self.assertFalse(r['live_remediation_authorized'])
        self.assertEqual(r['binding_status'],'UNBOUND')
        self.assertEqual(r['runtime_freshness'],'UNKNOWN')
        return r

    def test_order(self):
        self.assertEqual(self.run_adapter()['reason'],'INJECTED_READBACKS_NOT_ATTESTED')
        self.assertEqual(self.calls,['core','twin','policy','core'])

    def test_manifest_metadata(self):
        self.rows['twin']['source_ref']='fixture:changed'
        self.assertEqual(self.run_adapter()['reason'],'MANIFEST_MISMATCH')

    def test_core_changed(self):
        def core():
            row=deepcopy(self.read('core'))
            if self.calls.count('core')==2:
                row['content']['version']=2
                row['content_sha256']=digest(row['content'])
            return row
        self.readers['core']=core
        self.assertEqual(self.run_adapter()['reason'],'CORE_CHANGED')

    def test_pre_resolved(self):
        self.rows['core']['content']['run_status']='RESOLVED'
        self.rehash()
        self.assertEqual(self.run_adapter()['reason'],'CORE_NOT_PREPARED')

    def test_missing(self):
        self.readers['twin']=lambda: None
        self.assertEqual(self.run_adapter()['reason'],'AUTHORITY_MISSING:twin')

    def test_stale(self):
        self.rows['policy']['observed_at']='2026-11-18T09:00:00.123455Z'
        self.assertEqual(self.run_adapter()['reason'],'STALE_OBSERVATION')

    def test_invalid_inputs_never_read(self):
        for case in ('identity','intent','clock','registry','duplicate_source',
                     'missing_registry','missing_policy','bool_policy','readers','policies'):
            with self.subTest(case=case):
                self.setUp()
                registry={a:a+'-001' for a in self.rows}
                policies={v:30 for v in registry.values()}
                clock='2026-11-18T09:00:30.123456Z'
                if case=='identity': self.e['tenant_id']='OTHER'
                if case=='intent': self.i['effect_allowed']=True
                if case=='clock': clock='2026-02-30T09:00:00Z'
                if case=='registry': registry['core']=None
                if case=='duplicate_source': registry['core']=registry['twin']
                if case=='missing_registry': registry=None
                if case=='missing_policy': policies.pop('core-001')
                if case=='bool_policy': policies['core-001']=True
                if case=='readers': self.readers['core']=None
                if case=='policies': policies=None
                result=collect_prepared(self.e,self.i,self.readers,policies,
                    as_of_utc=clock,source_registry=registry)
                self.assertIn(result['qualification'],('BLOCK','REJECT'))
                self.assertIsNone(result['context'])
                self.assertFalse(result['runtime_attested'])
                self.assertEqual(self.calls,[])
