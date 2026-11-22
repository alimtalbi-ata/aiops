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
        self.registry = {a:a+'-001' for a in AUTHORITIES}
    def qualify(self):
        return qualify_context(self.e,self.i,self.rows,self.p,as_of_utc='2026-10-25T09:00:30Z',source_registry=self.registry)
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

    def test_registry_missing(self):
        self.registry=None
        self.assertEqual(self.qualify()['reason'],'SOURCE_REGISTRY_MISSING')
    def test_registry_mismatch(self):
        self.registry['twin']='OTHER'
        self.assertEqual(self.qualify()['reason'],'SOURCE_NOT_REGISTERED:twin')
    def test_ref_collision(self):
        self.rows['twin']['source_ref']=self.rows['core']['source_ref']
        self.assertEqual(self.qualify()['reason'],'SOURCE_REF_COLLISION')
    def test_nested_story_and_positive_claims(self):
        for k,v in [('scope','STORY_OFFLINE'),('runtime_attested',True),('human_approved',True),('live_remediation_authorized',True)]:
            with self.subTest(k=k):
                self.setUp()
                c=self.rows['twin']['content']; c[k]=v
                self.rows['twin']['content_sha256']=digest(c)
                self.assertEqual(self.qualify()['reason'],'UNQUALIFIED_CONTENT_CLAIM')
    def test_invalid_reader(self):
        r=read_context(self.e,self.i,{'core':42},self.p,as_of_utc='2026-10-25T09:00:30Z',source_registry=self.registry)
        self.assertEqual(r['qualification'],'REJECT')
    def test_freshness_boundary(self):
        self.p={a+'-001':30 for a in AUTHORITIES}
        self.assertEqual(self.qualify()['reason'],'INJECTED_READBACKS_NOT_ATTESTED')
        self.p['twin-001']=29
        self.assertEqual(self.qualify()['reason'],'STALE_OBSERVATION')

    def test_utc_precision_preserved(self):
        for fraction in ('', '.1', '.12', '.123', '.1234', '.12345', '.123456'):
            with self.subTest(fraction=fraction):
                self.setUp()
                stamp='2026-10-25T09:00:00'+fraction+'Z'
                self.rows['twin']['observed_at']=stamp
                r=self.qualify()
                self.assertEqual(r['reason'],'INJECTED_READBACKS_NOT_ATTESTED')
                self.assertEqual(r['evidence'][1]['observed_at'],stamp)
                self.assertFalse(r['runtime_attested'])
                self.assertEqual(r['binding_status'],'UNBOUND')
                self.assertEqual(r['runtime_freshness'],'UNKNOWN')

    def test_fractional_freshness_and_future(self):
        for stamp,reason in [
            ('2026-10-25T09:00:00.123456Z','INJECTED_READBACKS_NOT_ATTESTED'),
            ('2026-10-25T09:00:00.123455Z','STALE_OBSERVATION'),
            ('2026-10-25T09:00:00.123457Z','INJECTED_READBACKS_NOT_ATTESTED'),
            ('2026-10-25T09:00:30.123457Z','FUTURE_OBSERVATION')]:
            with self.subTest(stamp=stamp):
                self.setUp()
                self.p['twin-001']=30
                self.rows['twin']['observed_at']=stamp
                r=qualify_context(self.e,self.i,self.rows,self.p,as_of_utc='2026-10-25T09:00:30.123456Z',source_registry=self.registry)
                self.assertEqual(r['reason'],reason)
                self.assertEqual(r['qualification'],'REJECT' if reason=='FUTURE_OBSERVATION' else 'BLOCK')
                self.assertEqual(r['runtime_freshness'],'UNKNOWN')

    def test_utc_invalid_observation_and_clock(self):
        for stamp in ('2026-02-29T09:00:00Z','2026-04-31T09:00:00Z','2026-10-25T24:00:00Z','2026-10-25T09:00:60Z','2026-10-25T09:00:00.1234567Z','2026-10-25T09:00:00.Z','2026-10-25T09:00:00+00:00','2026-10-25T09:00:00z','2026-10-25T09:00:00Z '):
            with self.subTest(stamp=stamp):
                self.setUp()
                self.rows['twin']['observed_at']=stamp
                self.assertEqual(self.qualify()['reason'],'PROVENANCE_INVALID')
                r=qualify_context(self.e,self.i,self.rows,self.p,as_of_utc=stamp,source_registry=self.registry)
                self.assertEqual(r['reason'],'CLOCK_INVALID')
                self.assertEqual(r['qualification'],'REJECT')
