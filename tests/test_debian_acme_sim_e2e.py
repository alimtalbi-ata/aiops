import importlib.util
from pathlib import Path
import tempfile
import unittest

P = Path(__file__).resolve().parents[1] / 'deploy/debian-acme-sim-e2e.py'
spec = importlib.util.spec_from_file_location('debian_acme_sim', P)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def capability(component):
    return {'schema':'aiops.acme-sandbox-capabilities.v1','component':component,
            'tenant_id':'ACME-TEST','mode':'SIMULATION','isolated':True,
            'live_effects_allowed':False,'real_glpi_writes_allowed':False,
            'human_approval_claimed':False,'approval_issuer':'TWIN_ACME_SIMULATED'}

class TestSimulation(unittest.TestCase):
    def test_current_services_without_contract_block_before_post(self):
        calls=[]
        def p(component, path, method='GET', payload=None, auth=False):
            calls.append((component, method)); return {'error':'HTTP_404'}
        r=m.execute(p, 'ACME-SIM-TEST0001')
        self.assertEqual(r['status'],'BLOCKED')
        self.assertEqual(calls,[('simulator','GET')])

    def test_all_caps_then_worker_no_effect_core_resolved(self):
        calls=[]
        ids={'incident_id':'INC-123','run_id':'RUN-123','ticket_id':'SIM-GLPI-123',
             'proposal_id':'PROP-123','approval_id':'SIM-APP-123'}
        resolved=False
        source_ids=['SRC-%d' % i for i in range(7)]
        request_sha='a'*64
        worker_receipt=dict(
            attempt_id='ACME-SIM-TEST0001',tenant_id='ACME-TEST',
            incident_id=ids['incident_id'],run_id=ids['run_id'],
            ticket_id=ids['ticket_id'],proposal_id=ids['proposal_id'],
            approval_id=ids['approval_id'],action='SIMULATE',
            receipt_status='SIMULATED_NO_EFFECT',receipt_phase='PRE_RESOLUTION',
            core_status_at_validation='PREPARED',resolution_verified=False,
            post_resolution_readback_required=True,effect_receipts=0,
            human_approved=False,execution_allowed=False,effect_allowed=False,
            live_effects_allowed=False,core_request_sha256=request_sha,
            core_source_event_ids=source_ids)
        worker_receipt['receipt_sha256']=m.hashlib.sha256(m.json.dumps(
            worker_receipt,sort_keys=True,separators=(',', ':'),
            ensure_ascii=True).encode('ascii')).hexdigest()
        ticket_binding=dict(
            schema='aiops.portal.sim-glpi-ticket-digest.v1',
            tenant_id='ACME-TEST',attempt_id='ACME-SIM-TEST0001',
            incident_id=ids['incident_id'],run_id=ids['run_id'],
            ticket_id=ids['ticket_id'],ticket_status='RESOLVED',
            core_request_sha256=request_sha,
            worker_receipt_sha256=worker_receipt['receipt_sha256'])
        ticket_sha=m.hashlib.sha256(m.json.dumps(
            ticket_binding,sort_keys=True,separators=(',', ':'),
            ensure_ascii=True).encode('ascii')).hexdigest()
        def p(component,path,method='GET',payload=None,auth=False):
            nonlocal resolved
            calls.append((component,path,method))
            if path.endswith('/capabilities'):return capability(component)
            x=dict(attempt_id='ACME-SIM-TEST0001',tenant_id='ACME-TEST',
                   incident_id='INC-123',run_id='RUN-123',
                   ticket_id=ids['ticket_id'],proposal_id=ids['proposal_id'],
                   approval_id=ids['approval_id'])
            if component=='simulator' and method=='POST':
                return dict(x,**ids,glpi_mode='SIMULATED_ONLY')
            if component=='core' and method=='POST':
                resolved=True
                return dict(x,incident_status='RESOLVED',run_status='RESOLVED',
                            ticket_status='RESOLVED',human_approved=False,
                            execution_allowed=False,effect_allowed=False)
            if component=='core':
                state='RESOLVED' if resolved else 'PREPARED'
                return dict(x,incident_status=state,run_status=state,
                            ticket_status=state,ticket_id='SIM-GLPI-123',
                            proposal_id='PROP-123',ticket_authority='SIMULATED_ONLY',
                            source='SYNTHETIC_SIMULATOR',source_event_count=7,
                            source_hashes_qualified=True,analysis_validated=True,
                            critic_validated=True,evidence_count=2,
                            source_event_ids=source_ids,request_sha256=request_sha,
                            worker_receipt_sha256=worker_receipt['receipt_sha256'] if resolved else None,
                            worker_receipt_verified=resolved,
                            terminal_ticket_receipt_verified=resolved,
                            terminal_ticket_sha256=ticket_sha if resolved else None,
                            resolution_after_worker_receipt=resolved,
                            human_approved=False,execution_allowed=False,
                            effect_allowed=False,live_effects_allowed=False)
            if component=='twin':
                return dict(x,impact_root='ACME-TEST-SAN-FABRIC-A',approval_id='SIM-APP-123',
                            approval_issuer='TWIN_ACME_SIMULATED',
                            approval_kind='SIMULATED',approval_actor='TWIN_ACME_SIMULATED',
                            approval_phase='PRE_RESOLUTION',core_status_at_issuance='PREPARED',
                            impacted_cis=['ACME-TEST-SVC-PAYMENTS'],
                            human_approved=False,execution_allowed=False,
                            effect_allowed=False,live_effects_allowed=False)
            if component=='policy':
                return dict(x,decision='SIMULATE',approval_id='SIM-APP-123',
                            approval_kind='SIMULATED',human_approved=False,
                            execution_allowed=False,effect_allowed=False,
                            live_effects_allowed=False)
            return dict(worker_receipt)
        result=m.execute(p,'ACME-SIM-TEST0001')
        self.assertEqual(result['status'],'PASS',result)
        self.assertEqual([x[0] for x in calls if x[2]=='POST'],['simulator','core'])
        self.assertEqual(result['stages']['core_finalization'],'PASS')
        self.assertFalse(result['human_approval_claimed'])

    def test_partial_capability_never_posts(self):
        calls=[]
        def p(component,path,method='GET',payload=None,auth=False):
            calls.append((component,method))
            return capability(component) if component=='simulator' else {'error':'NOT_SUPPORTED'}
        result=m.execute(p,'ACME-SIM-TEST0002')
        self.assertEqual(result['status'],'BLOCKED')
        self.assertEqual(result['reason'],'SANDBOX_CAPABILITY_MISSING_CORE')
        self.assertEqual(calls,[('simulator','GET'),('core','GET')])

    def test_real_glpi_ticket_namespace_rejected(self):
        ids={'incident_id':'INC-123','run_id':'RUN-123','ticket_id':'GLPI-REAL-123',
             'proposal_id':'PROP-123','approval_id':'SIM-APP-123'}
        calls=[]
        def p(component,path,method='GET',payload=None,auth=False):
            calls.append(method)
            if path.endswith('/capabilities'):return capability(component)
            return dict(ids,attempt_id='ACME-SIM-TEST0003',tenant_id='ACME-TEST',glpi_mode='SIMULATED_ONLY')
        result=m.execute(p,'ACME-SIM-TEST0003')
        self.assertEqual(result['status'],'FAIL')
        self.assertEqual(result['reason'],'SIMULATOR_START_UNQUALIFIED')
        self.assertEqual(calls.count('POST'),1)
        self.assertEqual(len(calls),6)

    def test_live_and_fake_human_capability_rejected(self):
        for change in ({'live_effects_allowed':True},{'human_approval_claimed':True},
                       {'tenant_id':'FOREIGN'},{'approval_issuer':'HUMAN'},
                       {'isolated':False},{'real_glpi_writes_allowed':True}):
            with self.subTest(change=change):
                c=capability('core');c.update(change)
                self.assertFalse(m.qualified_capability('core',c))

    def test_wrong_issuer_in_independent_readback_rejected(self):
        ids={'incident_id':'INC-1','run_id':'RUN-1','ticket_id':'SIM-GLPI-1','approval_id':'SIM-APP-1'}
        base={'attempt_id':'A','tenant_id':'ACME-TEST','incident_id':'INC-1','run_id':'RUN-1'}
        reads={'core':dict(base,incident_status='RESOLVED',run_status='RESOLVED',ticket_id='SIM-GLPI-1'),
               'twin':dict(base,impact_root='ACME-TEST-SAN-FABRIC-A',approval_id='SIM-APP-1',approval_issuer='HUMAN',approval_kind='SIMULATED'),
               'policy':dict(base,decision='SIMULATE',approval_kind='SIMULATED',human_approved=False,live_effects_allowed=False),
               'worker':dict(base,action='SIMULATE',receipt_status='SIMULATED_NO_EFFECT',effect_receipts=0,execution_allowed=False)}
        self.assertFalse(m.validate_final('A',ids,reads))


    def test_rg_acme_29_worker_and_core_terminal_digest_fail_closed(self):
        ids=dict(incident_id='INC-1',run_id='RUN-1',
                 ticket_id='SIM-GLPI-1',proposal_id='PROP-1',
                 approval_id='SIM-APP-1')
        worker=dict(attempt_id='ACME-SIM-A',tenant_id='ACME-TEST',
                    incident_id='INC-1',run_id='RUN-1',ticket_id='SIM-GLPI-1',
                    proposal_id='PROP-1',approval_id='SIM-APP-1',
                    core_request_sha256='a'*64,
                    core_source_event_ids=['SRC-%d' % i for i in range(7)],
                    effect_receipts=0,action='SIMULATE')
        def sha(payload):
            return m.hashlib.sha256(m.json.dumps(
                payload,sort_keys=True,separators=(',', ':'),
                ensure_ascii=True).encode('ascii')).hexdigest()
        worker['receipt_sha256']=sha(worker)
        core=dict(attempt_id='ACME-SIM-A',request_sha256='a'*64,
                  source_event_ids=list(worker['core_source_event_ids']),
                  worker_receipt_sha256=worker['receipt_sha256'],
                  worker_receipt_verified=True,
                  terminal_ticket_receipt_verified=True,
                  resolution_after_worker_receipt=True,
                  approval_id='SIM-APP-1')
        core['terminal_ticket_sha256']=sha(dict(
            schema='aiops.portal.sim-glpi-ticket-digest.v1',
            tenant_id='ACME-TEST',attempt_id='ACME-SIM-A',
            incident_id='INC-1',run_id='RUN-1',ticket_id='SIM-GLPI-1',
            ticket_status='RESOLVED',core_request_sha256='a'*64,
            worker_receipt_sha256=worker['receipt_sha256']))
        self.assertTrue(m.validate_terminal_receipts(ids,core,worker))
        for key,value in [('receipt_sha256','0'*64),
                          ('ticket_id','SIM-GLPI-FOREIGN'),
                          ('core_request_sha256','b'*64),
                          ('effect_receipts',1)]:
            with self.subTest(worker_tamper=key):
                forged=dict(worker,key=value)
                self.assertFalse(m.validate_terminal_receipts(ids,core,forged))
        for key,value in [('worker_receipt_verified',1),
                          ('terminal_ticket_receipt_verified',False),
                          ('terminal_ticket_sha256','f'*64),
                          ('approval_id','SIM-APP-FOREIGN')]:
            with self.subTest(core_tamper=key):
                self.assertFalse(m.validate_terminal_receipts(
                    ids,dict(core,**{key:value}),worker))
        # A rehashed foreign Worker ticket still cannot match Core's
        # persisted terminal digest or the incident's canonical IDs.
        forged=dict(worker,ticket_id='SIM-GLPI-FOREIGN')
        forged.pop('receipt_sha256')
        forged['receipt_sha256']=sha(forged)
        self.assertFalse(m.validate_terminal_receipts(ids,core,forged))

    def test_rg_acme_30_pre_resolution_requires_signed_twin_identity_and_worker_digest(self):
        attempt = 'ACME-SIM-RG30'
        ids = dict(incident_id='INC-SIM-RG30', run_id='RUN-SIM-RG30',
                   ticket_id='SIM-GLPI-RG30', proposal_id='PROP-SIM-RG30',
                   approval_id='SIM-APP-RG30')
        shared = dict(attempt_id=attempt, tenant_id='ACME-TEST',
                      incident_id=ids['incident_id'], run_id=ids['run_id'],
                      human_approved=False, execution_allowed=False,
                      effect_allowed=False, live_effects_allowed=False)
        sources = ['SRC-%d' % n for n in range(7)]
        core = dict(shared, incident_status='PREPARED', run_status='PREPARED',
                    ticket_status='PREPARED', ticket_id=ids['ticket_id'],
                    proposal_id=ids['proposal_id'], ticket_authority='SIMULATED_ONLY',
                    source_event_count=7, source_hashes_qualified=True,
                    analysis_validated=True, critic_validated=True,
                    request_sha256='a'*64, source_event_ids=sources)
        twin = dict(shared, impact_root='ACME-TEST-SAN-FABRIC-A',
                    approval_id=ids['approval_id'],
                    approval_issuer='TWIN_ACME_SIMULATED',
                    approval_actor='TWIN_ACME_SIMULATED',
                    approval_kind='SIMULATED', approval_phase='PRE_RESOLUTION',
                    core_status_at_issuance='PREPARED')
        policy = dict(shared, approval_id=ids['approval_id'],
                      decision='SIMULATE', approval_kind='SIMULATED')
        worker = dict(shared, approval_id=ids['approval_id'],
                      ticket_id=ids['ticket_id'], proposal_id=ids['proposal_id'],
                      action='SIMULATE', receipt_status='SIMULATED_NO_EFFECT',
                      receipt_phase='PRE_RESOLUTION',
                      core_status_at_validation='PREPARED',
                      resolution_verified=False, post_resolution_readback_required=True,
                      effect_receipts=0, core_request_sha256='a'*64,
                      core_source_event_ids=sources)
        def digest(document):
            return m.hashlib.sha256(m.json.dumps(
                document, sort_keys=True, separators=(',', ':'),
                ensure_ascii=True, allow_nan=False).encode('ascii')).hexdigest()
        worker['receipt_sha256'] = digest(worker)
        reads = dict(core=core, twin=twin, policy=policy, worker=worker)
        self.assertTrue(m.validate_pre(attempt, ids, reads))
        for component, change in (
                ('worker', dict(receipt_sha256='0'*64)),
                ('worker', dict(core_request_sha256='b'*64)),
                ('worker', dict(ticket_id='SIM-GLPI-FOREIGN')),
                ('worker', dict(action='EXECUTE')),
                ('twin', dict(approval_issuer='HUMAN')),
                ('twin', dict(approval_actor='HUMAN')),
                ('twin', dict(impact_root='FOREIGN-FABRIC')),
                ('core', dict(source_event_ids=['FOREIGN']*7))):
            with self.subTest(component=component, change=change):
                tampered = dict(reads)
                tampered[component] = dict(reads[component], **change)
                self.assertFalse(m.validate_pre(attempt, ids, tampered))
        # A rehashed, internally consistent foreign Worker document must
        # still fail the independent Core source/request/ticket binding.
        forged = dict(worker, ticket_id='SIM-GLPI-FOREIGN')
        forged.pop('receipt_sha256')
        forged['receipt_sha256'] = digest(forged)
        self.assertFalse(m.validate_pre(attempt, ids, dict(reads, worker=forged)))
        # Malformed canonical JSON never becomes a trusted pre-resolution receipt.
        nonfinite = dict(worker, source_float=float('nan'))
        nonfinite.pop('receipt_sha256')
        nonfinite['receipt_sha256'] = '0'*64
        self.assertFalse(m.validate_pre(attempt, ids, dict(reads, worker=nonfinite)))

    def test_receipt_private_and_redacted(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'receipt.json';r=m.receipt('A','BLOCKED','SANDBOX_CAPABILITY_MISSING_CORE')
            m.save(r,path)
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
            self.assertNotIn('token',path.read_text())

if __name__=='__main__':unittest.main()
