#!/usr/bin/env bash
# FS1145: authenticate to GLPI using existing Portal env, with strict literal-IP target.
set -euo pipefail
echo "FS1145_MODE=AUTHENTICATED_GLPI_EXISTING_PORTAL_ENV_READ_ONLY"
echo "FS1145_TICKETS_CREATED=0"
echo "FS1145_PORTAL_MUTATION=NONE"
docker exec -i aiops2-rebuild-portal python - <<'PY'
import os,json,urllib.parse,urllib.request,urllib.error
def emit(**kw): print(json.dumps(kw,sort_keys=True),flush=True)
url=os.environ.get('GLPI_API_URL','').strip().rstrip('/')
app=os.environ.get('GLPI_APP_TOKEN','').strip()
user=os.environ.get('GLPI_USER_TOKEN','').strip()
p=urllib.parse.urlsplit(url)
if not (p.scheme=='http' and p.hostname=='172.21.0.6' and p.port in (None,80)
        and p.path in ('/apirest.php','/apirest.php/')
        and not p.query and not p.fragment and not p.username and not p.password
        and app and user):
    emit(type='preflight',result='UNEXPECTED_CONFIGURATION',token_values_exposed=False)
    raise SystemExit(0)
base='http://172.21.0.6/apirest.php'
def call(path,headers):
    req=urllib.request.Request(base+path,headers=headers,method='GET')
    try:
        with urllib.request.urlopen(req,timeout=10) as r: return r.status,r.read(32768)
    except urllib.error.HTTPError as e: return e.code,e.read(32768)
    except Exception as e:
        emit(type='transport_error',path=path,error_type=type(e).__name__)
        return 0,b''
def errcode(body):
    try:
        x=json.loads(body)
        return x[0] if isinstance(x,list) and x and isinstance(x[0],str) else None
    except (ValueError,TypeError): return None
code,body=call('/initSession',{'Authorization':'user_token '+user,'App-Token':app,'Accept':'application/json'})
try: data=json.loads(body)
except (ValueError,TypeError): data=None
session=data.get('session_token') if isinstance(data,dict) else None
emit(type='authentication',http_status=code,session_established=bool(session),glpi_error_code=errcode(body),secret_values_exposed=False)
if not session:
    emit(type='summary',result='AUTHENTICATION_NOT_ESTABLISHED',tickets_created=0)
    raise SystemExit(0)
headers={'Session-Token':session,'App-Token':app,'Accept':'application/json'}
try:
    for path in ('/getMyProfiles','/Ticket?range=0-0'):
        status,payload=call(path,headers)
        emit(type='read_probe',path=path,http_status=status,read_allowed=200<=status<300,glpi_error_code=errcode(payload))
finally:
    status,_=call('/killSession',headers)
    emit(type='session_close',http_status=status)
emit(type='summary',result='AUTHENTICATED_READ_ONLY',tickets_created=0,portal_files_changed=False)
PY
echo "FS1145_FINAL_STATUS=READ_ONLY_COMPLETE"
