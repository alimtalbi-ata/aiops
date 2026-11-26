"""CI-only native Mattermost relay: private socket, loopback GAMMA, verified lab context."""
import http.client
import json
import os
from pathlib import Path
import re
import socketserver
import sys
import threading
from http.server import BaseHTTPRequestHandler

sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"vertical"))
from http_demo import server
from mattermost_demo import authenticate

def port(name):
    value=int(os.environ[name])
    if not 1024<=value<=65535 or value in (7770,7777,7790):
        raise ValueError("invalid isolated lab port")
    return value

def main():
    os.umask(0o077)
    root=Path(os.environ["MM_LAB_BINDING_DIR"])
    if not root.is_absolute() or root.resolve()!=root or root.stat().st_uid!=os.getuid() or root.stat().st_mode & 0o077:
        raise ValueError("private binding directory required")
    binding_path=root/"binding.json"
    if binding_path.is_symlink() or binding_path.stat().st_uid!=os.getuid() or binding_path.stat().st_mode & 0o077:
        raise ValueError("private binding file required")
    binding=json.loads(binding_path.read_text())
    token=binding["token"]
    channel=binding["channel_id"]
    if not re.fullmatch(r"[A-Za-z0-9_-]{26,128}",token) or not re.fullmatch(r"[a-z0-9]{26}",channel):
        raise ValueError("invalid command binding")
    path=root/"gamma.sock"
    with server(core_config=(port("CORE_PORT"),os.environ["V3_LAB_TOKEN"],"RUN-CI-CONTEXT"),
                context_config=(port("TWIN_PORT"),port("EVIDENCE_PORT"),"NODE-CI-ROOT","INC-CI-CONTEXT"),
                policy_port=port("POLICY_PORT"),mattermost_config=(token,channel)) as gamma:
        worker=threading.Thread(target=gamma.serve_forever,daemon=True)
        worker.start()
        try:
            conn=http.client.HTTPConnection("127.0.0.1",gamma.server_port,timeout=20)
            try:
                conn.request("GET","/api/v1/incident-context")
                response=conn.getresponse()
                raw=response.read(65537)
                if response.status!=200 or len(raw)>65536: raise ValueError("GAMMA context unavailable")
                expected=json.loads(raw)
            finally:
                conn.close()
            if expected["core"]["run"]["run_id"]!="RUN-CI-CONTEXT" or not expected["context"]["evidence"]:
                raise ValueError("unverified expected context")
            (root/"expected.json").write_text(json.dumps({"run_id":expected["core"]["run"]["run_id"],
                "incident_id":expected["core"]["run"]["incident_id"],"sources":expected["context"]["evidence"]}))
            class Handler(BaseHTTPRequestHandler):
                def log_message(self,*args):
                    pass
                def do_POST(self):
                    try:
                        size=int(self.headers.get("Content-Length","0"))
                        if self.path!="/api/v1/mattermost/command" or not 0<size<=4096:
                            raise ValueError("invalid request")
                        body=self.rfile.read(size)
                        authenticate(body,token,channel)
                        conn=http.client.HTTPConnection("127.0.0.1",gamma.server_port,timeout=20)
                        try:
                            conn.request("POST",self.path,body,{"Content-Type":"application/x-www-form-urlencoded"})
                            response=conn.getresponse()
                            raw=response.read(65537)
                            if response.status!=200 or len(raw)>65536: raise ValueError("unverified backend")
                        finally:
                            conn.close()
                        status=200
                    except Exception:
                        status=403
                        raw=b'{"error":"UNVERIFIED","policy":"DENY"}'
                    self.send_response(status)
                    self.send_header("Content-Type","application/json")
                    self.send_header("Content-Length",str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
            with socketserver.UnixStreamServer(str(path),Handler) as relay:
                path.chmod(0o600)
                print("Private GAMMA relay ready",flush=True)
                relay.serve_forever()
        finally:
            gamma.shutdown()
            worker.join(5)

if __name__=="__main__":
    main()
