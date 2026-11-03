#!/usr/bin/env python3
"""P0 #385/#386: read-only host route+image gate, NOT browser/ACL/n8n/GLPI E2E."""
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

STATE = Path('/home/aiops/.local/state/aiops-debian-agent')
ROOT = Path(__file__).resolve().parents[1]
CASES = (
 ('demo_center','/demo-center','text/html',('SIMULATION_ONLY','CATALOG_ONLY','recording-consent','/demo/acme-impact')),
 ('noc_operator','/noc','text/html',('UNKNOWN','tenant','/assets/noc-operator.js','NOC opérateur')),
 ('recorder_asset','/assets/demo-center-recorder.js','javascript',('getDisplayMedia','MediaRecorder','isSecureContext','CONSENT_WITHDRAWN')),
 ('noc_asset','/assets/noc-operator.js','javascript',('tenant_acl_qualified','actor_identity_server_derived','UNKNOWN')),
)
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def qualify_route(case, opener):
    name,path,kind,markers=case
    result={'name':name,'path':path,'status':'FAIL','http_status':None,'reason':'NO_RESPONSE'}
    req=urllib.request.Request('http://127.0.0.1:7777'+path,method='GET',
        headers={'Accept':'text/html, application/javascript','Cache-Control':'no-store'})
    try:
        try: response=opener.open(req,timeout=5)
        except urllib.error.HTTPError as exc: response=exc
        with response:
            code=response.status
            headers=response.headers
            raw=response.read(32769)
        result['http_status']=code
        if code!=200 or len(raw)>32768: reason='HTTP_OR_SIZE_UNQUALIFIED'
        elif 'no-store' not in headers.get('Cache-Control','').lower() or headers.get('X-Content-Type-Options','').lower()!='nosniff': reason='SECURITY_HEADERS_MISSING'
        elif kind not in headers.get('Content-Type','').lower(): reason='CONTENT_TYPE_MISMATCH'
        elif kind=='text/html' and ("default-src 'none'" not in headers.get('Content-Security-Policy','') or "frame-ancestors 'none'" not in headers.get('Content-Security-Policy','')): reason='HTML_CSP_MISSING'
        elif not all(m in raw.decode('utf-8') for m in markers): reason='ROUTE_MARKERS_MISSING'
        else:
            result.update(status='PASS',reason='READONLY_ROUTE_PRESENT_NOT_UX_ATTESTED')
            return result
        result['reason']=reason
    except (OSError,ValueError,TimeoutError,UnicodeError): result['reason']='NETWORK_OR_INVALID_RESPONSE'
    return result

def inspect_portal(pin,runner=subprocess.run):
    result={'status':'NOT_VERIFIED','image_id':None,'container_id':None}
    if not isinstance(pin,str) or re.fullmatch(r'[0-9a-f]{40}',pin) is None: return result
    try:
        p=runner(['docker','inspect','aiops2-rebuild-portal','--format',
            '{{.Image}}|{{.Id}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}|{{.Config.Image}}'],
            capture_output=True,text=True,timeout=8,check=False)
        if p.returncode or len(p.stdout)>512: return result
        image,cid,health,tag=p.stdout.strip().split('|')
        expected='aiops2-portal:pinned-'+pin[:12]
        if not (re.fullmatch(r'sha256:[0-9a-f]{64}',image) and re.fullmatch(r'[0-9a-f]{64}',cid)
                and health=='healthy' and tag==expected): return result
        p=runner(['docker','image','inspect',expected,'--format','{{.Id}}'],
            capture_output=True,text=True,timeout=8,check=False)
        if p.returncode or p.stdout.strip()!=image: return result
        result.update(status='PASS',image_id=image,container_id=cid)
    except (OSError,ValueError,subprocess.TimeoutExpired): pass
    return result

def make_receipt(pin,opener=None,runner=subprocess.run):
    opener=opener or urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    checks=[qualify_route(c,opener) for c in CASES]
    image=inspect_portal(pin,runner)
    passed=sum(c['status']=='PASS' for c in checks)
    return {'schema':'aiops.debian-portal-ux-routes.v1',
        'collected_at':dt.datetime.now(dt.timezone.utc).isoformat(),
        'candidate_sha':pin if isinstance(pin,str) and re.fullmatch(r'[0-9a-f]{40}',pin) else None,
        'scope':'127.0.0.1:7777','checks':checks,'passed':passed,'total':len(CASES),'image':image,
        'verdict':'PASS_READONLY_ROUTE_ONLY' if passed==len(CASES) and image['status']=='PASS' else 'FAIL',
        'browser_ux':'NOT_VERIFIED','real_screen_capture':'NOT_VERIFIED',
        'n8n_login':'NOT_VERIFIED','glpi_human_acl':'NOT_VERIFIED',
        'acme_sandbox_e2e':'NOT_RUN_BY_THIS_GATE','live_effects':0}

def main():
    try:
        m=json.loads((ROOT/'deploy/debian-portal-release.json').read_text())
        pin=m.get('candidate_sha') if m.get('enabled') is True else None
    except (OSError,ValueError,TypeError): pin=None
    result=make_receipt(pin)
    STATE.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd,temp=tempfile.mkstemp(prefix='.portal-ux-',dir=str(STATE))
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,'w') as f: json.dump(result,f,sort_keys=True);f.write('\n')
        os.replace(temp,STATE/'portal-ux-routes.json')
    finally:
        if os.path.exists(temp): os.unlink(temp)
    print('PORTAL_UX_ROUTES=%d/%d verdict=%s'%(result['passed'],result['total'],result['verdict']))
    return 0 if result['verdict']=='PASS_READONLY_ROUTE_ONLY' else 78
if __name__=='__main__': sys.exit(main())
