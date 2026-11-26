"""Native callback: explicit mock or private Unix-socket relay to lab GAMMA."""
import json
import os
import socket
import http.client
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
sys.path.insert(0,"/vertical")
from mattermost_demo import command, authenticate

class UnixConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        self.sock.settimeout(20)
        self.sock.connect("/binding/gamma.sock")

def real_backend(body):
    conn=UnixConnection("localhost",timeout=20)
    try:
        conn.request("POST","/api/v1/mattermost/command",body,{"Content-Type":"application/x-www-form-urlencoded"})
        response=conn.getresponse()
        raw=response.read(65537)
        if response.status!=200 or len(raw)>65536: raise ValueError("backend unavailable")
        result=json.loads(raw)
        if result.get("response_type")!="ephemeral": raise ValueError("invalid backend response")
        return result
    finally:
        conn.close()

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            if self.path!="/api/v1/mattermost/command": raise ValueError()
            size=int(self.headers.get("Content-Length","0"))
            if not 0<size<=4096: raise ValueError()
            with open("/binding/binding.json") as f: binding=json.load(f)
            core={"production_authorized":False,"run":{"run_id":"RUN-CI-MOCK","incident_id":"INC-CI-MOCK"}}
            context={"classification":"SYNTHETIC_LAB_CONTEXT","production_authorized":False,"run_id":"RUN-CI-MOCK","policy":"DENY","affected":[],"evidence":[]}
            body=self.rfile.read(size)
            authenticate(body,binding["token"],binding["channel_id"])
            mode=os.environ.get("MM_LAB_BACKEND_MODE","mock")
            if mode=="real":
                result=real_backend(body)
            elif mode=="mock":
                result=command(body,binding["token"],binding["channel_id"],core,context)
                result["text"]+="\nMOCK BACKEND — transport test only"
            else:
                raise ValueError("invalid backend mode")
            status=200
        except Exception as exc:
            print("Callback rejected:",type(exc).__name__,flush=True)
            result={"error":"UNVERIFIED","policy":"DENY"}
            status=403
        body=json.dumps(result).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)
HTTPServer(("0.0.0.0",8080),Handler).serve_forever()
