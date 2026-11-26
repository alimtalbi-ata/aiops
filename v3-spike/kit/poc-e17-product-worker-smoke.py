"""Disposable target-owned E17 campaign using the actual containerized Worker.

The existing vertical lab adapters require loopback. Four local HTTP relays
expose only their enumerated routes to fixed isolated Compose service names.
No caller-supplied destination, shell execution, host port, or production target.
"""
import asyncio
from contextlib import ExitStack,contextmanager
import hmac
import http.client
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import sys
import threading
from temporalio.api.enums.v1 import EventType
from temporalio.exceptions import WorkflowAlreadyStartedError

from poc_temporal_e17_smoke import execute
TOKEN=os.environ["AIOPS_INTERNAL_TOKEN"]
PORTS={
    18110:("core",810,{"GET":r"/api/noc/runs/RUN-[A-F0-9]{16}","POST":r"/api/(?:incidents|runs)"}),
    18111:("twin",811,{"GET":r"/api/twin/(?:graph|impact/NODE-CI-ROOT)"}),
    18112:("evidence",812,{"GET":r"/api/evidence\?run_id=RUN-[A-F0-9]{16}&limit=20","POST":r"/api/evidence"}),
    18113:("policy",813,{"POST":r"/api/policy/check"}),
}
def require(ok,msg):
    if not ok: raise AssertionError(msg)

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def reply(self,status,data):
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    def body(self):
        size=int(self.headers.get("Content-Length","0"))
        if not 0<size<=65536: raise ValueError("bounded body required")
        return self.rfile.read(size)

class Relay(Handler):
    def do_GET(self): self.forward("GET")
    def do_POST(self): self.forward("POST")
    def forward(self,method):
        try:
            host,port,routes=PORTS[self.server.server_port]
            if not re.fullmatch(routes.get(method,r"(?!)"),self.path):
                raise ValueError("unsupported route")
            headers={"Accept":"application/json","Content-Type":"application/json"}
            auth=self.headers.get("Authorization")
            if host=="core":
                if not hmac.compare_digest(auth or "","Bearer "+TOKEN):
                    raise ValueError("internal token required")
                headers["Authorization"]=auth
            conn=http.client.HTTPConnection(host,port,timeout=5)
            try:
                conn.request(method,self.path,body=self.body() if method=="POST" else None,headers=headers)
                response=conn.getresponse()
                raw=response.read(65537)
                if len(raw)>65536 or 300<=response.status<400:
                    raise ValueError("unverified upstream")
                self.reply(response.status,raw)
            finally: conn.close()
        except Exception:
            self.reply(503,b'{"policy":"DENY"}')

class Reset(Handler):
    def do_POST(self):
        if not hmac.compare_digest(self.headers.get("Authorization",""),"Bearer "+TOKEN):
            self.reply(401,b'{"policy":"DENY"}')
            return
        try:
            if self.path!="/internal/e17/reset": raise ValueError("unsupported route")
            args=json.loads(self.body())
            if set(args)!={"workflow_id","receipt_id","receipt_sha256"} or args["workflow_id"]!=self.server.rid:
                raise ValueError("wrong workflow")
            result=self.server.target.simulate(args["receipt_id"],args["receipt_sha256"],workflow_id=args["workflow_id"])
            if result.get("status")!="SIMULATED": raise ValueError("blocked replay")
            self.reply(200,json.dumps(result,sort_keys=True).encode())
        except Exception:
            self.reply(409,b'{"policy":"DENY"}')

@contextmanager
def serve(address,handler,**attributes):
    with ThreadingHTTPServer(address,handler) as server:
        for name,value in attributes.items(): setattr(server,name,value)
        thread=threading.Thread(target=server.serve_forever)
        thread.start()
        try: yield server
        finally:
            server.shutdown()
            thread.join(5)
            require(not thread.is_alive(),"server leaked")

def post(host,port,path,args,token=TOKEN):
    conn=http.client.HTTPConnection(host,port,timeout=20)
    try:
        conn.request("POST",path,body=json.dumps(args),headers={"Authorization":"Bearer "+token,"Content-Type":"application/json"})
        response=conn.getresponse()
        data=response.read(65537)
        require(len(data)<=65536,"oversized response")
        return response.status,json.loads(data)
    finally: conn.close()

async def submit(client,target,rid,approval):
    path="/api/v3/lab/e17/start/"+rid
    with serve(("0.0.0.0",816),Reset,target=target,rid=rid):
        require(post("worker",815,path,approval,"invalid")[0]==401,"unauthenticated Worker start accepted")
        require(post("worker",815,"/api/v3/lab/e17/start/bad",approval)[0]==422,"invalid run accepted")
        require(post("worker",815,path,{**approval,"command":"OTHER"})[0]==422,"generic action accepted")
        require(post("127.0.0.1",816,"/internal/e17/reset",{"workflow_id":rid,**approval},"invalid")[0]==401,"unauthenticated target accepted")
        require(post("127.0.0.1",816,"/internal/e17/reset",{"workflow_id":"RUN-0000000000000000",**approval})[0]==409,"foreign workflow accepted")
        require(post("127.0.0.1",816,"/internal/e17/reset",{"workflow_id":rid,**approval,"receipt_sha256":"0"*64})[0]==409,"bad receipt accepted")
        require(target.delay==.12,"negative test changed target")
        status,submission=await asyncio.to_thread(post,"worker",815,path,approval)
        require(status==200 and submission=={"classification":"V3_E17_PRODUCT_WORKER_SUBMITTED",
            "workflow_id":rid,"run_id":rid,"executor":"temporal","production_authorized":False},"unverified submission")
        handle=client.get_workflow_handle(rid)
        receipt=await asyncio.wait_for(handle.result(),timeout=80)
        history=await asyncio.wait_for(handle.fetch_history(),timeout=10)
        started=[e.workflow_execution_started_event_attributes for e in history.events if e.event_type==EventType.EVENT_TYPE_WORKFLOW_EXECUTION_STARTED]
        activities=[e.activity_task_started_event_attributes for e in history.events if e.event_type==EventType.EVENT_TYPE_ACTIVITY_TASK_STARTED]
        require(len(started)==len(activities)==1 and started[0].workflow_type.name=="E17ProductRecoveryWorkflow"
                and started[0].task_queue.name=="aiops-v3-boundary" and activities[0].attempt==1
                and re.fullmatch(r"aiops-v3-[a-f0-9]{32}",activities[0].identity),"not the actual product Worker identity")
        require(post("worker",815,path,approval)[0]==409,"workflow replay accepted")
        require(post("127.0.0.1",816,"/internal/e17/reset",{"workflow_id":rid,**approval})[0]==409,"target replay accepted")
        require(target.delay==.01,"target did not recover")
        return receipt

if __name__=="__main__":
    require(os.environ.get("GITHUB_ACTIONS")=="true" and os.getuid()!=0,"disposable nonroot target required")
    require(os.environ.get("AIOPS_V3_E17_TARGET")=="http://e17-target:816"
            and len(TOKEN)>=32,"fixed lab profile required")
    root=Path("/tmp/aiops-v3-e17-target-ci")
    root.mkdir(mode=0o700,exist_ok=False)
    with (root/"poc.env").open("x") as f: f.write("V3_LAB_TOKEN="+TOKEN+"\n")
    (root/"poc.env").chmod(0o600)
    with ExitStack() as stack:
        for port in PORTS: stack.enter_context(serve(("127.0.0.1",port),Relay))
        report=asyncio.run(execute(root,"temporal:7233",*PORTS,product_submit=submit))
    require(report["activity_executor"]=="V3_PRODUCT_WORKER" and report["verification"]["status"]=="RECOVERED","missing product proof")
    print(json.dumps(report,sort_keys=True))
