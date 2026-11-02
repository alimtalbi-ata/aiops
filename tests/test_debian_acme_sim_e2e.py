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

    def test_all_caps_then_independent_resolved(self):
        calls=[]
        ids={'incident_id':'INC-123','run_id':'RUN-123','ticket_id':'SIM-GLPI-123',
             'proposal_id':'PROP-123','approval_id':'SIM-APP-123'}
        def p(component,path,method='GET',payload=None,auth=False):
            calls.append((component,path,method))
            if path.endswith('/capabilities'):return capability(component)
            if method=='POST':return dict(ids,attempt_id='ACME-SIM-TEST0001',tenant_id='ACME-TEST',glpi_mode='SIMULATED_ONLY')
            x=dict(attempt_id='ACME-SIM-TEST0001',tenant_id='ACME-TEST',incident_id='INC-123',run_id='RUN-123')
            if component=='core':return dict(x,incident_status='RESOLVED',run_status='RESOLVED',ticket_id='SIM-GLPI-123',ticket_authority='SIMULATED_ONLY',ticket_status='RESOLVED',source='SYNTHETIC_SIMULATOR',analysis_validated=True,critic_validated=True,evidence_count=2)
            if component=='twin':return dict(x,impact_root='ACME-SAN-FABRIC-A',approval_id='SIM-APP-123',approval_issuer='TWIN_ACME_SIMULATED',approval_kind='SIMULATED',approval_actor='TWIN_ACME_SIMULATED',impacted_cis=['ACME-SVC-PAYMENTS'])
            if component=='policy':return dict(x,decision='SIMULATE',approval_kind='SIMULATED',human_approved=False,live_effects_allowed=False)
            return dict(x,action='SIMULATE',receipt_status='SIMULATED_NO_EFFECT',effect_receipts=0,execution_allowed=False)
        r=m.execute(p,'ACME-SIM-TEST0001')
        self.assertEqual(r['status'],'PASS')
        self.assertEqual(len(calls),10)
        self.assertEqual(calls[5][2],'POST')
        self.assertFalse(r['human_approval_claimed'])

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
               'twin':dict(base,impact_root='ACME-SAN-FABRIC-A',approval_id='SIM-APP-1',approval_issuer='HUMAN',approval_kind='SIMULATED'),
               'policy':dict(base,decision='SIMULATE',approval_kind='SIMULATED',human_approved=False,live_effects_allowed=False),
               'worker':dict(base,action='SIMULATE',receipt_status='SIMULATED_NO_EFFECT',effect_receipts=0,execution_allowed=False)}
        self.assertFalse(m.validate_final('A',ids,reads))

    def test_receipt_private_and_redacted(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'receipt.json';r=m.receipt('A','BLOCKED','SANDBOX_CAPABILITY_MISSING_CORE')
            m.save(r,path)
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
            self.assertNotIn('token',path.read_text())

if __name__=='__main__':unittest.main()
