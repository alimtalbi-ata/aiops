#!/usr/bin/env bash
# FS1147: exercise actual Core GLPI client code against isolated mock GLPI.
# No production service mutation, no secret retrieval.
set -euo pipefail
echo "FS1147_MODE=CORE_GLPI_CLIENT_REGRESSION"
python3 - <<'PY'
import ast,importlib.util,json,os,pathlib,sys,threading,types
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
p=pathlib.Path(__file__).resolve() if '__file__' in globals() else pathlib.Path.cwd()
source=pathlib.Path('app/core/glpi_client.py')
if not source.exists():
 print('FS1147_ERROR=RUN_FROM_REPOSITORY_ROOT');sys.exit(2)
calls=[]
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  calls.append((self.command,self.path))
  if self.path.endswith('/initSession'):body={'session_token':'mock-session'}
  else:body={'ok':True}
  self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
  self.wfile.write(json.dumps(body).encode())
 def do_POST(self):
  n=int(self.headers.get('Content-Length','0'));data=json.loads(self.rfile.read(n))
  calls.append((self.command,self.path,data))
  self.send_response(201);self.send_header('Content-Type','application/json');self.end_headers()
  self.wfile.write(b'{"id":"155"}')
server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
try:
 os.environ['AIOPS_GLPI_URL']=f'http://127.0.0.1:{server.server_port}/apirest.php'
 os.environ['AIOPS_GLPI_APP_TOKEN']='test-only-app'
 os.environ['AIOPS_GLPI_USER_TOKEN']='test-only-user'
 spec=importlib.util.spec_from_file_location('fs1147_glpi_client',source)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 with module.Glpi() as client:
  tid=client.create(dict(incident_id='FS1147-CORE-INCIDENT',external_id='FS1147-DEMO',
   title='Mock synthetic incident',severity='P3',source='FS1147',synthetic=True))
 assert tid==155
 assert [x[:2] for x in calls]==[
  ('GET','/apirest.php/initSession'),('POST','/apirest.php/Ticket'),('GET','/apirest.php/killSession')]
 payload=calls[1][2]['input']
 assert payload['name'].startswith('[DEMO] ')
 assert 'FS1147-CORE-INCIDENT' in payload['content']
 assert payload['priority']==3
 print(json.dumps({'type':'regression','result':'PASS','numeric_string_ticket_id_accepted':True,
  'historical_apirest_url_accepted':True,'synthetic_ticket_label':True,
  'incident_correlation':True,'requests':3,'real_glpi_mutation':False}))
finally:server.shutdown();server.server_close()
PY
echo "FS1147_FINAL_STATUS=PASS_ISOLATED"
