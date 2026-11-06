#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.980 | ISOLATED WORKER HTTP E2E CONTRACT ====='
IMAGE=aiops2-worker:fs001d-guard-validated-20261106
SOURCE_SHA=7bca86f061b371fc1b03f1a8f7c693364a6155355be4de8eaa928561e2a4fc3b
docker image inspect "$IMAGE" >/dev/null
echo '===== ASGI TESTS: NO NETWORK, NO STARTUP, MOCKED CORE AND TEMPORAL ====='
docker run --rm --network none --entrypoint python -i "$IMAGE" - <<'PY'
import asyncio,hashlib,json,pathlib
from unittest.mock import patch,AsyncMock
from requests.exceptions import HTTPError
import requests
import worker.main as m
p=pathlib.Path('/app/worker/main.py')
assert hashlib.sha256(p.read_bytes()).hexdigest()=='7bca86f061b371fc1b03f1a8f7c693364a6155355be4de8eaa928561e2a4fc3b'
m.ADMIN='fs980-isolated-token'
class FakeHandle:
 id='FS980-TEST'
class FakeClient:
 def __init__(self): self.calls=0
 async def start_workflow(self,*args,**kwargs):
  self.calls+=1
  return FakeHandle()
client=FakeClient()
connect=AsyncMock(return_value=client)
async def call(body,token=True):
 raw=json.dumps(body).encode()
 headers=[(b'content-type',b'application/json')]
 if token: headers.append((b'authorization',b'Bearer fs980-isolated-token'))
 scope={'type':'http','asgi':{'version':'3.0'},'http_version':'1.1','method':'POST','scheme':'http','path':'/api/execution/start','raw_path':b'/api/execution/start','query_string':b'','root_path':'','headers':headers,'client':('127.0.0.1',12345),'server':('127.0.0.1',815)}
 events=[]
 async def receive(): return {'type':'http.request','body':raw,'more_body':False}
 async def send(event): events.append(event)
 await m.app(scope,receive,send)
 status=next(e['status'] for e in events if e['type']=='http.response.start')
 return status
def http404(*a,**k):
 r=requests.Response();r.status_code=404
 raise HTTPError('missing',response=r)
def unavailable(*a,**k): raise ConnectionError('core offline')
def blocked(*a,**k): return {'run':{'status':'BLOCKED'}}
def created(*a,**k): return {'run':{'status':'CREATED'}}
def check(name,expected,body,token=True,core=None,expected_connect=0):
 connect.reset_mock();client.calls=0
 with patch.object(m.Client,'connect',connect):
  with patch.object(m,'get_json',core or created):
   actual=asyncio.run(call(body,token))
 assert actual==expected,(name,actual,expected)
 assert connect.await_count==expected_connect,(name,connect.await_count,expected_connect)
 assert client.calls==expected_connect,(name,client.calls,expected_connect)
 print(name+'=PASS HTTP='+str(actual)+' TEMPORAL_STARTS='+str(client.calls))
check('UNAUTHORIZED',401,{'run_id':'FS980-TEST'},token=False)
check('MISSING_RUN_ID',422,{})
check('CORE_404',404,{'run_id':'FS980-MISSING'},core=http404)
check('CORE_503',503,{'run_id':'FS980-TEST'},core=unavailable)
check('BLOCKED_RUN',409,{'run_id':'FS980-TEST'},core=blocked)
check('CREATED_RUN_MOCK',200,{'run_id':'FS980-TEST'},core=created,expected_connect=1)
print('HTTP_CONTRACT_RESULT=PASS')
print('REAL_TEMPORAL_WORKFLOWS_STARTED=0')
PY
echo '===== PRODUCTION INTEGRITY ====='
echo 'ecfd599486aaa32b0f3ea446d192aa9c634635a601b7271b785d2fdaf517dfda  /home/aiops/aiops2-patches/fs-portal-v30/build/app/worker/main.py' | sha256sum -c -
docker inspect aiops2-rebuild-worker --format 'PRODUCTION_RUNNING={{.State.Running}} PRODUCTION_IMAGE={{.Config.Image}}'
echo 'PRODUCTION_RESTARTED=NO'
echo '===== END FS.980 ====='
