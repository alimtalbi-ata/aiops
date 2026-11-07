#!/usr/bin/env bash
# FS1146: ONE real GLPI DEMO ticket; idempotent by stable correlation key in GLPI DB.
# Runs an ephemeral Python process inside the existing Portal; no Portal file changes.
set -euo pipefail
echo "FS1146_MODE=ONE_REAL_GLPI_DEMO_TICKET"
echo "FS1146_PORTAL_FILES_CHANGED=NONE"
echo "FS1146_PORTAL_RESTART=NONE"
echo "FS1146_MAX_NEW_TICKETS=1"
docker exec -i aiops2-rebuild-portal python - <<'PY'
import os,json,urllib.parse,urllib.request,urllib.error,uuid,sys
def emit(**v): print(json.dumps(v,sort_keys=True),flush=True)
base=os.getenv('GLPI_API_URL','').strip().rstrip('/')
p=urllib.parse.urlsplit(base)
app=os.getenv('GLPI_APP_TOKEN','').strip()
user=os.getenv('GLPI_USER_TOKEN','').strip()
if not (p.scheme=='http' and p.hostname=='172.21.0.6' and p.port in (None,80)
        and p.path=='/apirest.php' and not p.query and not p.fragment
        and not p.username and not p.password and app and user):
    emit(type='preflight',result='UNEXPECTED_CONFIGURATION');sys.exit(2)
# Fixed campaign correlation ensures re-running the test does not create a second ticket.
marker='AIOPS-FS1146-GLPI-DEMO-SMOKE-V1'
headers={'Authorization':'user_token '+user,'App-Token':app,'Accept':'application/json'}
def request(path,method='GET',payload=None,extra=None):
    h=dict(headers)
    if extra:h.update(extra)
    data=json.dumps(payload).encode() if payload is not None else None
    if data is not None:h['Content-Type']='application/json'
    req=urllib.request.Request(base+path,data=data,headers=h,method=method)
    try:
        with urllib.request.urlopen(req,timeout=12) as r:return r.status,r.read(65536)
    except urllib.error.HTTPError as e:return e.code,e.read(65536)
def parsed(raw):
    try:return json.loads(raw)
    except (ValueError,TypeError):return None
status,raw=request('/initSession')
session=(parsed(raw) or {}).get('session_token') if isinstance(parsed(raw),dict) else None
emit(type='authentication',http_status=status,session_established=bool(session))
if not session:sys.exit(3)
headers={'Session-Token':session,'App-Token':app,'Accept':'application/json'}
try:
    # GLPI search API with name criterion; search result only advisory, verify each candidate.
    q=urllib.parse.urlencode({'criteria[0][field]':'1','criteria[0][searchtype]':'contains',
                              'criteria[0][value]':marker,'range':'0-49'})
    code,raw=request('/search/Ticket?'+q)
    result=parsed(raw)
    if not (200<=code<300 and isinstance(result,dict)):
        emit(type='precheck',http_status=code,result='SEARCH_UNAVAILABLE_FAIL_CLOSED')
        sys.exit(4)
    total=result.get('totalcount')
    emit(type='precheck',http_status=code,totalcount=total)
    if not isinstance(total,int):
        emit(type='precheck',result='UNEXPECTED_SEARCH_RESPONSE_FAIL_CLOSED');sys.exit(4)
    if total>0:
        emit(type='summary',result='ALREADY_EXISTS_NO_NEW_TICKET',matches=total,new_tickets_created=0)
        sys.exit(0)
    payload={'input':{'name':'[DEMO] '+marker+' — AIOps2 API qualification',
                      'content':'Synthetic AIOps2 integration test; correlation='+marker+
                                '; no production incident and no remediation.',
                      'type':1,'status':1,'priority':3}}
    try:
        code,raw=request('/Ticket','POST',payload)
    except Exception as exc:
        emit(type='creation',result='UNKNOWN_TRANSPORT_RECONCILE_BEFORE_RETRY',error_type=type(exc).__name__)
        sys.exit(5)
    data=parsed(raw)
    tid=data.get('id') if isinstance(data,dict) else None
    if isinstance(tid,str) and tid.isdigit():tid=int(tid)
    if not (200<=code<300 and isinstance(tid,int) and tid>0):
        emit(type='creation',http_status=code,result='UNCONFIRMED_RECONCILE_BEFORE_RETRY')
        sys.exit(5)
    emit(type='creation',http_status=code,ticket_id=tid,result='CREATED')
    code,raw=request('/Ticket/'+str(tid))
    obj=parsed(raw)
    verified=(200<=code<300 and isinstance(obj,dict) and marker in str(obj.get('name',''))
              and int(obj.get('id',0))==tid)
    emit(type='verification',http_status=code,ticket_id=tid,correlation_verified=verified)
    if not verified:sys.exit(6)
    emit(type='summary',result='PASS_ONE_REAL_DEMO_TICKET',ticket_id=tid,new_tickets_created=1)
finally:
    try:
        code,_=request('/killSession')
        emit(type='session_close',http_status=code)
    except Exception as exc:
        emit(type='session_close',error_type=type(exc).__name__)
PY
echo "FS1146_FINAL_STATUS=COMPLETE"
