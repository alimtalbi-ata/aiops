import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from core_read import read_run

class CoreReadTests(unittest.TestCase):
    def test_http_contract(self):
        payload = {"run":{"run_id":"RUN-01","incident_id":"INC-01","mode":"DEMO","status":"CREATED"},
                   "data_classification":"SYNTHETIC_CANONICAL_RUN","runtime_authenticated":False,
                   "tenant_acl_qualified":False,"live_remediation_authorized":False}
        calls = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                calls.append((self.path,self.headers.get("Authorization")))
                raw=json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Length",str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
        with ThreadingHTTPServer(("127.0.0.1",0),Handler) as server:
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            try:
                result=read_run(server.server_port,"x"*32,"RUN-01")
                self.assertEqual(result["policy"],"DENY")
                self.assertEqual(result["run"]["incident_id"],"INC-01")
                self.assertEqual(calls[0],("/api/noc/runs/RUN-01","Bearer "+"x"*32))
                for key,value in [("mode","LIVE"),("run_id","RUN-02")]:
                    old=payload["run"][key]
                    payload["run"][key]=value
                    with self.assertRaises(ValueError):
                        read_run(server.server_port,"x"*32,"RUN-01")
                    payload["run"][key]=old
                with self.assertRaises(ValueError):
                    read_run(7770,"x"*32,"RUN-01")
            finally:
                server.shutdown()
                thread.join(5)
