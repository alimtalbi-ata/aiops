import hashlib
import importlib.util
import os
import unittest
from copy import deepcopy
from portal.acme_runtime_context import digest
from portal.acme_authority_continuity import qualify_continuity
from worker.acme_simulated_hitl import canonical_source_ids, SCHEMA, ISSUER
from test_acme_authority_readers import AuthorityReadersTests

spec = importlib.util.spec_from_file_location('pinned_c_contract', os.environ['C_CONTRACT_PATH'])
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


class ContinuityTests(unittest.TestCase):
    def setUp(self):
        fixture = AuthorityReadersTests()
        fixture.setUp()
        self.e,self.i,self.rows = fixture.e,fixture.i,fixture.rows
        self.registry={a:a+'-001' for a in self.rows}
        self.policies={v:30 for v in self.registry.values()}
        core=self.rows['core']['content']
        twin=self.rows['twin']['content']
        twin['approval_nonce']='nonce-001'
        self.rows['twin']['content_sha256']=digest(twin)
        core.update(request_sha256='a'*64,source_event_ids=canonical_source_ids(self.i['attempt_id']))
        core['authority_manifest']={a:digest(self.rows[a]) for a in ('twin','policy')}
        self.rows['core']['content_sha256']=digest(core)
        seven={k:self.i[k] for k in c.IDENTITY}
        self.receipt=dict(seven,schema=SCHEMA,action='SIMULATE',receipt_status='SIMULATED_NO_EFFECT',
            approval_issuer=ISSUER,approval_kind='SIMULATED',human_approved=False,execution_allowed=False,
            effect_allowed=False,live_effects_allowed=False,real_glpi_writes_allowed=False,
            effect_receipts=0,audit_transitions=['CORE_PREPARED_INDEPENDENTLY_VERIFIED',
            'TWIN_SIMULATED_APPROVAL_VALIDATED','POLICY_SIMULATE_INDEPENDENTLY_VERIFIED','WORKER_NO_EFFECT'],
            audit_authority='TEMPORAL_WORKFLOW_HISTORY_ONLY',receipt_phase='PRE_RESOLUTION',
            core_status_at_validation='PREPARED',resolution_verified=False,
            post_resolution_readback_required=True,core_014_015_written=False,glpi_write=False,
            core_request_sha256=core['request_sha256'],core_source_event_ids=core['source_event_ids'],
            twin_approval_nonce_sha256=hashlib.sha256(b'nonce-001').hexdigest())
        self.receipt['receipt_sha256']=digest(self.receipt)
        ident={k:self.e[k] for k in ('tenant_id','incident_id','impact_incident_id','run_id','attempt_id')}
        self.prepared=dict(identity=ident,snapshot_id=self.e['snapshot_id'],parent_snapshot_id=None,
            version=1,phase='PREPARED',observed_at=self.rows['core']['observed_at'],
            collected_at='2026-11-18T09:00:01Z',payload={'core_sha256':digest(self.rows['core']),
            'authority_manifest':core['authority_manifest']})
        self.seal(self.prepared)
        actual=dict(identity=seven,source='CORE',status='RESOLVED',version=20,sequence=20,
            observed_at='2026-11-18T09:00:20Z',snapshot_id='SNAP-002',
            parent_snapshot_id=self.e['snapshot_id'],impact_incident_id=self.e['impact_incident_id'])
        self.terminal=dict(identity=ident,snapshot_id='SNAP-002',parent_snapshot_id=self.e['snapshot_id'],
            version=20,phase='TERMINAL',observed_at=actual['observed_at'],collected_at='2026-11-18T09:00:21Z',
            payload={'terminal_readback_sha256':digest(actual),'prepared_manifest_sha256':self.prepared['manifest_sha256'],
            'receipt_sha256':self.receipt['receipt_sha256']})
        self.seal(self.terminal)
        images={k:'sha256:'+'b'*64 for k in ('core','twin','policy','worker','evidence','postgres','temporal','temporal_postgres')}
        transitions=[dict(identity=seven,stage=stage,status='PASS',version=n,sequence=n,
            observed_at='2026-11-18T09:00:10Z',source='CORE') for n,stage in enumerate(c.STAGES,2)]
        self.sources={k:k+'-001' for k in ('history','postcheck','terminal')}
        self.policies.update({v:30 for v in self.sources.values()})
        common=dict(identity=seven,parent_snapshot_id=self.e['snapshot_id'],
                    impact_incident_id=self.e['impact_incident_id'])
        self.history=dict(common,source_id=self.sources['history'],
            observed_at='2026-11-18T09:00:05Z',receipt_sha256=self.receipt['receipt_sha256'])
        self.postcheck=dict(common,source_id=self.sources['postcheck'],
            observed_at='2026-11-18T09:00:15Z',history_sha256=digest(self.history),verified=True)
        actual.update(source_id=self.sources['terminal'],postcheck_sha256=digest(self.postcheck))
        self.terminal['payload']['terminal_readback_sha256']=digest(actual)
        self.seal(self.terminal)
        self.second=deepcopy(actual)
        self.sha='c'*40
        self.manifest=dict(scope='RUNTIME_SANDBOX',executed_sha=self.sha,runtime_attested=False,
            identity=seven,images=images,worker_receipt=deepcopy(self.receipt),history_sha256=digest(self.history),
            transitions=transitions,terminal=deepcopy(actual))
        self.independent=dict(identity=seven,executed_sha=self.sha,scope='RUNTIME_SANDBOX',images=deepcopy(images),
            worker_receipt_sha256=self.receipt['receipt_sha256'],history_sha256=digest(self.history),
            transitions_sha256=digest(transitions),critic_decision='ALLOW',twin_state='QUALIFIED',
            policy_decision='SIMULATE',hitl_valid=True,external_effect_count=0,postcheck_verified=True,
            terminal=actual,terminal_readback_sha256=digest(actual))

    def seal(self,row):
        row['manifest_sha256']=digest({k:v for k,v in row.items() if k not in ('manifest_sha256','collected_at')})

    def check(self,reason,clock='2026-11-18T09:00:30.123456Z'):
        r=qualify_continuity(self.e,self.i,self.rows,self.policies,as_of_utc=clock,
            source_registry=self.registry,prepared=self.prepared,terminal=self.terminal,
            receipt=self.receipt,c_manifest=self.manifest,independently_read=self.independent,
            expected_sha=self.sha,validate_postcheck=c.validate_postcheck,validate_manifest=c.validate_manifest,
            continuity_sources=self.sources,history=self.history,postcheck=self.postcheck,
            terminal_readback=self.second)
        self.assertEqual(r['reason'],reason)
        self.assertIn(r['qualification'],('BLOCK','REJECT'))
        self.assertEqual((r['binding_status'],r['runtime_freshness']),('UNBOUND','UNKNOWN'))
        self.assertIs(r['runtime_attested'],False)
        self.assertIs(r['live_remediation_authorized'],False)

    def test_nominal(self):
        self.check('OFFLINE_CONTINUITY_CONSISTENT_NOT_ATTESTED')

    def test_adverse(self):
        for case,reason in [('identity','IDENTITY_MISMATCH'),('digest','MANIFEST_DIGEST_MISMATCH'),
            ('manifest','AUTHORITY_MANIFEST_MISMATCH'),('parent','TERMINAL_CONTINUITY_MISMATCH'),
            ('version','TERMINAL_CONTINUITY_MISMATCH'),('collection','OBSERVATION_COLLECTION_ORDER'),
            ('receipt','RECEIPT_INVALID'),('postcheck','CONTINUITY_INVALID'),('history','CONTINUITY_DIGEST_MISMATCH'),
            ('missing','CONTINUITY_EVIDENCE_MISSING')]:
            with self.subTest(case=case):
                self.setUp()
                if case=='identity': self.terminal['identity']=dict(self.terminal['identity'],tenant_id='FOREIGN')
                if case=='digest': self.terminal['payload']={}
                if case=='manifest': self.prepared['payload']={}; self.seal(self.prepared)
                if case=='parent': self.terminal['parent_snapshot_id']='OTHER'
                if case=='version': self.terminal['version']=1
                if case=='collection': self.terminal['collected_at']='2026-11-18T09:00:19Z'
                if case=='receipt': self.receipt['receipt_sha256']='0'*64
                if case=='postcheck': self.independent['postcheck_verified']=False
                if case=='history': self.independent['history_sha256']='e'*64
                if case=='missing': self.independent=None
                if case not in ('digest',): self.seal(self.terminal)
                self.check(reason)

    def test_stale(self):
        self.check('STALE_OBSERVATION','2026-11-18T09:00:30.123457Z')

    def test_collection_not_manifest_digest(self):
        self.prepared['collected_at']='2026-11-18T09:00:02Z'
        self.check('OFFLINE_CONTINUITY_CONSISTENT_NOT_ATTESTED')

    def test_v4_arbitrations(self):
        for case,reason in (
            ('equal_time','TERMINAL_CONTINUITY_MISMATCH'),
            ('nonce_unicode','RECEIPT_PREPARED_MISMATCH'),
            ('nonce_empty','RECEIPT_PREPARED_MISMATCH'),
            ('nonce_changed','RECEIPT_PREPARED_MISMATCH'),
            ('second_changed','TERMINAL_READBACK_CHANGED'),
            ('second_missing','CONTINUITY_EVIDENCE_MISSING'),
            ('policy_missing','FRESHNESS_POLICY_MISSING'),
            ('history_stale','STALE_CONTINUITY_SOURCE'),
            ('postcheck_stale','STALE_CONTINUITY_SOURCE'),
            ('terminal_stale','STALE_MANIFEST'),
            ('history_changed','CONTINUITY_DIGEST_MISMATCH'),
            ('postcheck_changed','CONTINUITY_DIGEST_MISMATCH'),
            ('history_equal_time','CONTINUITY_TIME_ORDER')):
            with self.subTest(case=case):
                self.setUp()
                if case=='equal_time':
                    self.terminal['observed_at']=self.prepared['observed_at']; self.seal(self.terminal)
                if case.startswith('nonce_'):
                    twin=self.rows['twin']['content']
                    twin['approval_nonce']={'nonce_unicode':'é','nonce_empty':'','nonce_changed':' nonce-001'}[case]
                    self.rows['twin']['content_sha256']=digest(twin)
                    core=self.rows['core']['content']
                    core['authority_manifest']={a:digest(self.rows[a]) for a in ('twin','policy')}
                    self.rows['core']['content_sha256']=digest(core)
                    self.prepared['payload']={'core_sha256':digest(self.rows['core']),'authority_manifest':core['authority_manifest']}
                    self.seal(self.prepared)
                if case=='second_changed': self.second['version']+=1
                if case=='second_missing': self.second=None
                if case=='policy_missing': del self.policies[self.sources['history']]
                if case in ('history_stale','postcheck_stale','terminal_stale'):
                    self.policies[self.sources[case.split('_')[0]]]=0
                if case=='history_changed': self.history['extra']='changed'
                if case=='postcheck_changed': self.postcheck['extra']='changed'
                if case=='history_equal_time': self.history['observed_at']=self.prepared['observed_at']
                self.check(reason)
