"""Container-only synthetic GAMMA with embedded HITL; no Docker socket."""
from contextlib import ExitStack,contextmanager
import hmac
import http.client
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import os
from pathlib import Path
import re
import stat
import sys
import threading

sys.path.insert(0,"/lab/vertical")
from enterprise_clock import EnterpriseClock
from http_demo import server

TOKEN=os.environ["AIOPS_INTERNAL_TOKEN"]
PORTS={
    18110:("core",810,{"GET":r"/api/noc/runs/(?:RUN-CI-CONTEXT|RUN-[A-F0-9]{16})(?:/e17-receipt)?","POST":r"/api/(?:incidents|runs)"}),
    18111:("twin",811,{"GET":r"/api/twin/(?:graph|impact/NODE-CI-[A-Z0-9-]{1,80})"}),
    18112:("evidence",812,{"GET":r"/api/evidence\?run_id=(?:RUN-CI-CONTEXT|RUN-[A-F0-9]{16})&limit=20","POST":r"/api/evidence"}),
    18113:("policy",813,{"POST":r"/api/policy/check"}),
}
class Relay(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def reply(self,status,data):
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    def do_GET(self): self.forward("GET")
    def do_POST(self): self.forward("POST")
    def forward(self,method):
        try:
            host,port,routes=PORTS[self.server.server_port]
            if not re.fullmatch(routes.get(method,r"(?!)"),self.path): raise ValueError("unsupported route")
            headers={"Accept":"application/json","Content-Type":"application/json"}
            if host=="core":
                auth=self.headers.get("Authorization","")
                if not hmac.compare_digest(auth,"Bearer "+TOKEN): raise ValueError("internal token required")
                headers["Authorization"]=auth
            body=None
            if method=="POST":
                n=int(self.headers.get("Content-Length","0"))
                if not 0<n<=65536: raise ValueError("bounded body required")
                body=self.rfile.read(n)
            conn=http.client.HTTPConnection(host,port,timeout=10)
            try:
                conn.request(method,self.path,body=body,headers=headers)
                response=conn.getresponse()
                raw=response.read(65537)
                if len(raw)>65536 or 300<=response.status<400: raise ValueError("invalid upstream")
                self.reply(response.status,raw)
            finally: conn.close()
        except Exception:
            self.reply(503,b'{"policy":"DENY"}')

@contextmanager
def relay(port):
    with ThreadingHTTPServer(("127.0.0.1",port),Relay) as http:
        t=threading.Thread(target=http.serve_forever)
        t.start()
        try: yield
        finally:
            http.shutdown()
            t.join(5)

if __name__=="__main__":
    root=Path("/audit")
    info=root.lstat()
    if (os.getenv("AIOPS_V3_GAMMA_CONTAINER_LAB")!="1" or os.getuid()!=1000
        or not re.fullmatch(r"[a-f0-9]{64}",TOKEN) or root.resolve()!=root
        or not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077):
        raise SystemExit("private nonroot synthetic GAMMA profile required")
    with ExitStack() as stack:
        for port in PORTS: stack.enter_context(relay(port))
        with server(port=18080,core_config=(18110,TOKEN,"RUN-CI-CONTEXT"),
                    context_config=(18111,18112,"NODE-CI-ROOT","INC-CI-CONTEXT"),
                    policy_port=18113,enterprise_clock=EnterpriseClock(root),container_lab=True) as http:
            http.serve_forever()
