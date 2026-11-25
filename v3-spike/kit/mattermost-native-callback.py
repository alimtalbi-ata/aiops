"""Native transport smoke with explicitly mocked backend context."""
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
sys.path.insert(0,"/vertical")
from mattermost_demo import command

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            if self.path!="/api/v1/mattermost/command": raise ValueError()
            size=int(self.headers.get("Content-Length","0"))
            if not 0<size<=4096: raise ValueError()
            with open("/binding/binding.json") as f: binding=json.load(f)
            core={"production_authorized":False,"run":{"run_id":"RUN-CI-MOCK","incident_id":"INC-CI-MOCK"}}
            context={"classification":"SYNTHETIC_LAB_CONTEXT","production_authorized":False,"run_id":"RUN-CI-MOCK","policy":"DENY","affected":[],"evidence":[]}
            result=command(self.rfile.read(size),binding["token"],binding["channel_id"],core,context)
            result["text"]+="\nMOCK BACKEND — transport test only"
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
