import copy
import unittest
from portal.acme_runtime_context import qualify_context, read_context, digest, AUTHORITIES

class RuntimeContextTests(unittest.TestCase):
    def setUp(self):
        self.e = dict(tenant_id='ACME-TEST', incident_id='INC-001', impact_incident_id='INC-002', run_id='RUN-001', attempt_id='ACME-SIM-001', snapshot_id='SNAP-001')
        self.i = {k:v for k,v in self.e.items() if k not in ('snapshot_id','impact_incident_id')}
        self.i.update(proposal_id='PROP-001', ticket_id='SIM-GLPI-001', approval_id='SIM-APP-001', idempotency_key='ACME-SIM-001', scenario_id='ACME-SAN-PAYMENTS', mode='SIMULATION', approval_issuer='TWIN_ACME_SIMULATED', human_approved=False, execution_allowed=False, effect_allowed=False)
        content = dict(self.e, **self.i)
        self.rows = {a:dict(authority=a, scope='RUNTIME_SANDBOX', source_id=a+'-001', source_ref='fixture:'+a, observed_at='2026-10-25T09:00:00Z', snapshot_id='SNAP-001', content_sha256=digest(content), content=copy.deepcopy(content)) for a in AUTHORITIES}
        self.p = {a+'-001':60 for a in AUTHORITIES}
    def qualify(self):
        return qualify_context(self.e,self.i,self.rows,self.p,as_of_utc='2026-10-25T09:00:30Z')
    def test_nominal_never_attests(self):
        r=self.qualify(); self.assertEqual(r['reason'],'INJECTED_READBACKS_NOT_ATTESTED'); self.assertEqual(len(r['evidence']),3); self.assertFalse(r['runtime_attested']); self.assertEqual(r['runtime_freshness'],'UNKNOWN'); self.assertEqual(r['qualification'],'BLOCK')
    def test_adverse(self):
        cases=[('scope','STORY_OFFLINE','AUTHORITY_INVALID:twin'),('snapshot_id','OTHER','SNAPSHOT_MISMATCH'),('content_sha256','0'*64,'DIGEST_MISMATCH'),('source_ref','','PROVENANCE_INVALID'),('observed_at','2026-10-25T08:00:00Z','STALE_OBSERVATION'),('observed_at','2026-10-25T10:00:00Z','FUTURE_OBSERVATION'),('source_id','core-001','PROVENANCE_INVALID')]
        for k,v,reason in cases:
            with self.subTest(k=k,v=v):
                self.setUp(); self.rows['twin'][k]=v; self.assertEqual(self.qualify()['reason'],reason)
    def test_identity_mutations(self):
        for k in ('tenant_id','incident_id','impact_incident_id','run_id','attempt_id','proposal_id','ticket_id','approval_id','idempotency_key'):
            with self.subTest(k=k):
                self.setUp(); c=self.rows['twin']['content']; c[k]='FOREIGN'; self.rows['twin']['content_sha256']=digest(c); self.assertEqual(self.qualify()['reason'],'IDENTITY_MISMATCH:twin')
    def test_missing_authority_policy(self):
        del self.rows['twin']; self.assertEqual(self.qualify()['reason'],'AUTHORITY_MISSING:twin'); self.setUp(); self.p={}; self.assertEqual(self.qualify()['reason'],'FRESHNESS_POLICY_MISSING')
    def test_story_run(self):
        self.e['run_id']='SIM-ACME-123'; self.assertEqual(self.qualify()['qualification'],'REJECT')
    def test_reader_timeout(self):
        def fail(): raise TimeoutError()
        r=read_context(self.e,self.i,{'core':lambda:self.rows['core'],'twin':fail},self.p,as_of_utc='2026-10-25T09:00:30Z'); self.assertEqual(r['reason'],'AUTHORITY_MISSING:twin')
