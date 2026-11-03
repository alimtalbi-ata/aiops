"""RG-UX-07: strict route+image gate; no simulated browser or human ALLOW."""
import importlib.util
import json
import io
from pathlib import Path
import subprocess
import unittest

p=Path(__file__).resolve().parents[1]/'deploy/debian-portal-ux-contracts.py'
spec=importlib.util.spec_from_file_location('ux',p)
ux=importlib.util.module_from_spec(spec)
spec.loader.exec_module(ux)
PIN='a'*40
IMAGE='sha256:'+'b'*64

class Response:
    def __init__(self,case,tamper=None):
        self.status=200
        self.headers={'Cache-Control':'public' if tamper=='headers' else 'no-store',
            'X-Content-Type-Options':'nosniff',
            'Content-Type':'text/html' if case[2]=='text/html' else 'application/javascript',
            'Content-Security-Policy':"default-src 'none'; frame-ancestors 'none'"}
        values=case[3][:-1] if tamper==case[0] else case[3]
        if case[0]=='twin_read_model':
            model={'schema':'aiops.synthetic-impact-read-model.v1',
                'entrypoint':'/demo-center','provenance':'SIMULATED_TARGET',
                'run_id_provenance':'DERIVED_FROM_FIXTURE_SHA256_NOT_RUNTIME_RUN',
                'ticket_id':None,'runtime_evidence_present':False,
                'runtime_attested':False,'live_remediation_authorized':False,
                'production_qualified':False}
            if tamper=='twin_read_model':
                model['live_remediation_authorized']=True
            self.headers['Content-Type']='application/json'
            self.body=io.BytesIO(json.dumps(model).encode())
        else:
            self.body=io.BytesIO(' '.join(values).encode())
    def __enter__(self):return self
    def __exit__(self,*args):self.body.close()
    def read(self,n):return self.body.read(n)
class Opener:
    def __init__(self,tamper=None):self.tamper=tamper
    def open(self,req,timeout=5):
        return Response(next(c for c in ux.CASES if req.full_url=='http://127.0.0.1:7777'+c[1]),self.tamper)
def runner(args,**kw):
    if args[:2]==['docker','inspect']:
        out=IMAGE+'|'+'c'*64+'|healthy|aiops2-portal:pinned-'+PIN[:12]+'\n'
    else:out=IMAGE+'\n'
    return subprocess.CompletedProcess(args,0,stdout=out)
class UXGateTests(unittest.TestCase):
    def test_rg_ux_07_positive_readonly_not_browser(self):
        r=ux.make_receipt(PIN,Opener(),runner)
        self.assertEqual((r['passed'],r['total']),(8,8))
        self.assertEqual(r['verdict'],'PASS_READONLY_ROUTE_ONLY')
        self.assertEqual(r['browser_ux'],'NOT_VERIFIED')
        self.assertEqual(r['glpi_human_acl'],'NOT_VERIFIED')
    def test_rg_ux_07_missing_route_rejected(self):
        r=ux.make_receipt(PIN,Opener('demo_center'),runner)
        self.assertEqual(r['passed'],7)
        self.assertEqual(r['verdict'],'FAIL')
    def test_rg_ux_13_recorder_station_required_and_fail_closed(self):
        station=next(c for c in ux.CASES if c[0]=='recorder_station')
        self.assertEqual(station[1],'/demo-center/recorder')
        self.assertIn('LOCAL_ONLY / NO LIVE EFFECT',station[3])
        receipt=ux.make_receipt(PIN,Opener('recorder_station'),runner)
        self.assertEqual((receipt['passed'],receipt['total']),(7,8))
        self.assertEqual(receipt['verdict'],'FAIL')

    def test_rg_ux_13_demo_center_links_to_station(self):
        center=next(c for c in ux.CASES if c[0]=='demo_center')
        self.assertIn('href="/demo-center/recorder"',center[3])
        receipt=ux.make_receipt(PIN,Opener('demo_center'),runner)
        self.assertEqual((receipt['passed'],receipt['total']),(7,8))
        self.assertEqual(receipt['verdict'],'FAIL')

    def test_rg_ux_12_historical_studio_route_required(self):
        case=next(c for c in ux.CASES if c[0]=='historical_demo_studio')
        self.assertEqual(case[1],'/demo-studio')
        self.assertIn('SYNTHETIC_REFERENCE_ONLY',case[3])
        self.assertIn('UNKNOWN',case[3])
        receipt=ux.make_receipt(PIN,Opener('historical_demo_studio'),runner)
        self.assertEqual((receipt['passed'],receipt['total']),(7,8))
        self.assertEqual(receipt['verdict'],'FAIL')

    def test_rg_ux_12_demo_center_must_link_historical_studio(self):
        case=next(c for c in ux.CASES if c[0]=='demo_center')
        self.assertIn('href="/demo-studio"',case[3])
        receipt=ux.make_receipt(PIN,Opener('demo_center'),runner)
        self.assertEqual((receipt['passed'],receipt['total']),(7,8))
        self.assertEqual(receipt['verdict'],'FAIL')

    def test_rg_ux_11_noc_synthetic_provenance_required(self):
        case=next(c for c in ux.CASES if c[0]=='noc_operator')
        self.assertIn('SYNTHETIC_REFERENCE_ONLY',case[3])
        self.assertIn('LOCAL_SYNTHETIC_FIXTURE',case[3])
        self.assertIn('PG16 ACME-TEST migration 019',case[3])
        receipt=ux.make_receipt(PIN,Opener('noc_operator'),runner)
        self.assertEqual((receipt['passed'],receipt['total']),(7,8))
        self.assertEqual(receipt['verdict'],'FAIL')

    def test_rg_ux_10_twin_model_cannot_claim_live_authority(self):
        r=ux.make_receipt(PIN,Opener('twin_read_model'),runner)
        self.assertEqual(r['passed'],7)
        self.assertEqual(r['verdict'],'FAIL')
        self.assertEqual(next(c for c in r['checks'] if c['name']=='twin_read_model')['reason'],
                         'TWIN_MODEL_CONTRACT_MISMATCH')

    def test_rg_ux_10_twin_nav_missing_link_rejected(self):
        r=ux.make_receipt(PIN,Opener('twin_navigation'),runner)
        self.assertEqual(r['passed'],7)
        self.assertEqual(r['verdict'],'FAIL')

    def test_rg_ux_07_missing_security_header_rejected(self):
        self.assertEqual(ux.make_receipt(PIN,Opener('headers'),runner)['verdict'],'FAIL')
    def test_rg_ux_07_image_drift_and_invalid_pin_rejected(self):
        def bad(args,**kw):
            p=runner(args,**kw)
            if args[:2]==['docker','inspect']:p.stdout=p.stdout.replace('healthy','unhealthy')
            return p
        self.assertEqual(ux.make_receipt(PIN,Opener(),bad)['verdict'],'FAIL')
        self.assertEqual(ux.make_receipt('invalid',Opener(),runner)['verdict'],'FAIL')
    def test_rg_ux_07_portal_only_release_no_acme_rebuild(self):
        import json
        root=Path(__file__).resolve().parents[1]
        portal=json.loads((root/'deploy/debian-portal-release.json').read_text())
        acme=json.loads((root/'deploy/debian-acme-sandbox-release.json').read_text())
        self.assertIs(portal['enabled'],True)
        self.assertEqual(portal['candidate_sha'],'f8921bf2c46534022fc3ac0aa0be02bf4d1880cb')
        self.assertIs(acme['enabled'],False)
        self.assertEqual(acme['candidate_sha'],'e9a21e3e13f9c13bff461325426f12f171285b22')

    def test_rg_ux_07_no_redirect_and_only_get(self):
        self.assertIsNone(ux.NoRedirect().redirect_request(None,None,302,None,{},'https://elsewhere'))
        self.assertTrue(all(c[1].startswith('/') for c in ux.CASES))
if __name__=='__main__':unittest.main()
