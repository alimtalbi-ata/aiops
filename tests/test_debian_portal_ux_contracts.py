"""RG-UX-07: strict route+image gate; no simulated browser or human ALLOW."""
import importlib.util
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
        self.body=io.BytesIO(' '.join(values).encode())
    def __enter__(self):return self
    def __exit__(self,*args):self.body.close()
    def read(self,n):return self.body.read(n)
class Opener:
    def __init__(self,tamper=None):self.tamper=tamper
    def open(self,req,timeout=5):
        return Response(next(c for c in ux.CASES if req.full_url.endswith(c[1])),self.tamper)
def runner(args,**kw):
    if args[:2]==['docker','inspect']:
        out=IMAGE+'|'+'c'*64+'|healthy|aiops2-portal:pinned-'+PIN[:12]+'\n'
    else:out=IMAGE+'\n'
    return subprocess.CompletedProcess(args,0,stdout=out)
class UXGateTests(unittest.TestCase):
    def test_rg_ux_07_positive_readonly_not_browser(self):
        r=ux.make_receipt(PIN,Opener(),runner)
        self.assertEqual((r['passed'],r['total']),(4,4))
        self.assertEqual(r['verdict'],'PASS_READONLY_ROUTE_ONLY')
        self.assertEqual(r['browser_ux'],'NOT_VERIFIED')
        self.assertEqual(r['glpi_human_acl'],'NOT_VERIFIED')
    def test_rg_ux_07_missing_route_rejected(self):
        r=ux.make_receipt(PIN,Opener('demo_center'),runner)
        self.assertEqual(r['passed'],3)
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
    def test_rg_ux_07_no_redirect_and_only_get(self):
        self.assertIsNone(ux.NoRedirect().redirect_request(None,None,302,None,{},'https://elsewhere'))
        self.assertTrue(all(c[1].startswith('/') for c in ux.CASES))
if __name__=='__main__':unittest.main()
