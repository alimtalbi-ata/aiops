import json
import unittest
from copy import deepcopy
from portal.acme_runtime_context import digest
from portal.acme_independent_authorities import (
    inspect_authority_batch, ROLES, READ_SEQUENCE, REGISTRY_SCHEMA, ENVELOPE_SCHEMA)


class IndependentAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.identity=dict(tenant_id='ACME-TEST',incident_id='INC-001',
            impact_incident_id='INC-002',run_id='RUN-001',attempt_id='ACME-SIM-001',
            proposal_id='PROP-001',ticket_id='SIM-GLPI-001',approval_id='SIM-APP-001')
        self.expected={k:self.identity[k] for k in ('tenant_id','incident_id','impact_incident_id','run_id','attempt_id')}
        self.expected['snapshot_id']='SNAP-001'
        self.registry=dict(schema=REGISTRY_SCHEMA,authorities={k:dict(source_id=k+'-001',
            principal='fixture:'+k,audience='fixture-audience:'+k,scope='read:'+k,
            tenant_id='ACME-TEST',max_age_seconds=60,revocation_state='ACTIVE') for k in ROLES})
        self.requests=[];self.rows=[];self.meta=[]
        for n,k in enumerate(READ_SEQUENCE):
            e=self.registry['authorities'][k]
            challenge='CHALLENGE-'+str(n)
            self.requests.append(dict(role=k,identity=self.identity,challenge=challenge))
            initial=k in ('core','twin','policy')
            time={'core':'01','twin':'02','policy':'03','history':'10','postcheck':'20','terminal':'30'}[k]
            row=dict(schema=ENVELOPE_SCHEMA,role=k,source_id=e['source_id'],classification='STORY_OFFLINE',
                identity=deepcopy(self.identity),snapshot_id='SNAP-001' if initial else 'SNAP-002',
                parent_snapshot_id=None if initial else 'SNAP-001',version=1 if initial else 2,
                observed_at='2026-11-18T09:00:'+time+'Z',content={'fixture':k})
            row['content_sha256']=digest(row['content'])
            self.rows.append(row)
            self.meta.append(dict(classification='OFFLINE_TEST_METADATA',principal=e['principal'],
                audience=e['audience'],scope=e['scope'],tenant_id='ACME-TEST',challenge=challenge,
                envelope_sha256=digest(row),collected_at='2026-11-18T09:00:40Z'))

    def check(self,reason,verdict='REJECT'):
        obs=[None if row is None else (json.dumps(row).encode(),meta) for row,meta in zip(self.rows,self.meta)]
        out=inspect_authority_batch(self.expected,self.identity,self.registry,self.requests,obs,
            as_of_utc='2026-11-18T09:00:45Z')
        self.assertEqual((out['reason'],out['qualification']),(reason,verdict))
        for k in ('runtime_attested','live_remediation_authorized','transport_authenticated','admitted_to_runtime'):
            self.assertIs(out[k],False)
        self.assertEqual((out['binding_status'],out['runtime_freshness']),('UNBOUND','UNKNOWN'))

    def test_nominal(self):
        self.check('OFFLINE_TRANSPORT_CONSISTENT_NOT_AUTHENTICATED','BLOCK')

    def test_adversarial(self):
        for case,reason,verdict in [
            ('source','SOURCE_MISMATCH','REJECT'),('principal','PRINCIPAL_MISMATCH','REJECT'),
            ('audience','AUDIENCE_MISMATCH','REJECT'),('scope','SCOPE_MISMATCH','REJECT'),
            ('tenant','IDENTITY_MISMATCH','REJECT'),('run','IDENTITY_MISMATCH','REJECT'),
            ('snapshot','SNAPSHOT_MISMATCH','REJECT'),('replay','REPLAY','REJECT'),
            ('digest','DIGEST_MISMATCH','REJECT'),('envelope','ENVELOPE_BINDING_MISMATCH','REJECT'),
            ('unverified','TRANSPORT_EVIDENCE_MISSING','BLOCK'),('missing','SOURCE_MISSING','BLOCK'),
            ('stale','STALE_SOURCE','BLOCK'),('future','CLOCK_ORDER','REJECT'),
            ('version','TERMINAL_CONTINUITY_INVALID','REJECT'),('second','READBACK_CHANGED','REJECT'),
            ('policy','FRESHNESS_POLICY_MISSING','BLOCK'),('synthetic','UNATTESTED_RUNTIME_CLAIM','REJECT'),
            ('revoked','SOURCE_REVOKED_OR_UNKNOWN','BLOCK'),('transport_tenant','TRANSPORT_TENANT_MISMATCH','REJECT'),
            ('collision','PRINCIPAL_COLLISION','REJECT'),('transport_claim','TRANSPORT_CLAIM_UNQUALIFIED','REJECT')]:
            with self.subTest(case=case):
                self.setUp()
                if case=='source': self.rows[0]['source_id']='OTHER'
                if case in ('principal','audience','scope'): self.meta[0][case]='OTHER'
                if case=='tenant': self.rows[0]['identity']['tenant_id']='OTHER'
                if case=='run': self.rows[0]['identity']['run_id']='RUN-OTHER'
                if case=='snapshot': self.rows[0]['snapshot_id']='SNAP-OTHER'
                if case=='replay': self.meta[3]['challenge']=self.meta[0]['challenge']
                if case=='digest': self.rows[0]['content']={}
                if case=='envelope': self.rows[0]['version']=9
                if case=='unverified': self.meta[0]=None
                if case=='missing': self.rows[0]=None
                if case=='stale': self.registry['authorities']['core']['max_age_seconds']=0
                if case=='future': self.rows[0]['observed_at']='2026-11-18T09:00:50Z'
                if case=='version':
                    for i in (6,7): self.rows[i]['version']=1
                if case=='second': self.rows[7]['version']=3
                if case=='policy': del self.registry['authorities']['history']['max_age_seconds']
                if case=='synthetic': self.rows[0]['classification']='RUNTIME_SANDBOX'
                if case=='revoked': self.registry['authorities']['core']['revocation_state']='REVOKED'
                if case=='transport_tenant': self.meta[0]['tenant_id']='OTHER'
                if case=='collision': self.registry['authorities']['twin']['principal']=self.registry['authorities']['core']['principal']
                if case=='transport_claim': self.meta[0]['classification']='AUTHENTICATED'
                if case not in ('envelope','unverified','missing'):
                    for row,meta in zip(self.rows,self.meta): meta['envelope_sha256']=digest(row)
                self.check(reason,verdict)
