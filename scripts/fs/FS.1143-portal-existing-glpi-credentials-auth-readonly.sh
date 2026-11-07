#!/usr/bin/env bash
# FS1143 — authenticate from the already allowed Portal source, using existing env.
# Does not change Portal files/config, create GLPI tickets or print credentials.
set -euo pipefail
echo "FS1143_MODE=EXISTING_PORTAL_GLPI_CREDENTIALS_AUTH_AND_READ"
echo "FS1143_PORTAL_RESTART=NONE"
echo "FS1143_TICKETS_CREATED=0"
docker exec -i aiops2-rebuild-portal python - <<'PY'
import json,os,urllib.request,urllib.error,urllib.parse
def emit(**kw): print(json.dumps(kw,ensure_ascii=False,sort_keys=True),flush=True)
base=os.environ.get('GLPI_API_URL','').strip().rstrip('/')
app=os.environ.get('GLPI_APP_TOKEN','').strip()
user=os.environ.get('GLPI_USER_TOKEN','').strip()
emit(type='configuration_presence',url_present=bool(base),app_token_present=bool(app),
     user_token_present=bool(user),secret_values_exposed=False)
if not (base and app and user):
    emit(type='summary',result='MISSING_EXISTING_PORTAL_CONFIG',tickets_created=0)
    raise SystemExit(0)
parsed=urllib.parse.urlsplit(base)
if parsed.scheme!='http' or parsed.hostname not in ('aiops2-glpi','aiops2-rebuild-glpi'):
    emit(type='summary',result='UNEXPECTED_GLPI_URL_HOST_OR_SCHEME',tickets_created=0)
    raise SystemExit(0)
if not base.endswith('/apirest.php'):
    base=base+'/apirest.php'
def call(path,headers):
    req=urllib.request.Request(base+path,headers=headers,method='GET')
    try:
        with urllib.request.urlopen(req,timeout=8) as resp:
            return resp.status,resp.read(65536)
    except urllib.error.HTTPError as exc:
        return exc.code,exc.read(65536)
    except Exception as exc:
        emit(type='transport_failure',path=path,error_type=type(exc).__name__)
        return 0,b''
headers={'Authorization':'user_token '+user,'App-Token':app,'Accept':'application/json'}
status,body=call('/initSession',headers)
try: payload=json.loads(body)
except Exception: payload=None
session=payload.get('session_token') if isinstance(payload,dict) else None
error_code=payload[0] if isinstance(payload,list) and payload and isinstance(payload[0],str) else None
emit(type='authentication',http_status=status,session_established=bool(session),glpi_error_code=error_code)
if not session:
    emit(type='summary',result='AUTHENTICATION_NOT_ESTABLISHED',tickets_created=0)
    raise SystemExit(0)
read_headers={'Session-Token':session,'App-Token':app,'Accept':'application/json'}
try:
    for path in ('/getMyProfiles','/Ticket?range=0-0'):
        code,data=call(path,read_headers)
        emit(type='read_probe',path=path,http_status=code,read_allowed=200<=code<300)
finally:
    code,_=call('/killSession',read_headers)
    emit(type='session_close',http_status=code)
emit(type='summary',result='AUTHENTICATED_READ_ONLY',tickets_created=0,portal_files_changed=False)
PY
echo "FS1143_FINAL_STATUS=READ_ONLY_COMPLETE"
