"""Loopback-only synthetic HTTP adapter for the existing vertical demo."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from vertical_demo import execute
from correlation_demo import correlate

EVENT = {"id": "synthetic-001", "source": "synthetic-monitor",
         "severity": "critical", "resource": "demo-node-01",
         "tenant": "synthetic-demo"}

class Handler(BaseHTTPRequestHandler):
    def reply(self, status, data, mime="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/":
            self.reply(200, Path(__file__).with_name("operator.html").read_bytes(),
                       "text/html; charset=utf-8")
        elif self.path in ("/api/v1/demo", "/api/v1/demo?simulate=1"):
            result = execute(EVENT, approved=self.path.endswith("?simulate=1"))
            self.reply(200, json.dumps(result).encode())
        elif self.path == "/api/v1/incidents":
            second = {**EVENT, "id": "synthetic-002", "source": "synthetic-log",
                      "severity": "warning"}
            self.reply(200, json.dumps(correlate([EVENT, second])).encode())
        else:
            self.reply(404, b'{"error":"NOT_FOUND"}')

def server(port=0):
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)

if __name__ == "__main__":
    with server() as http:
        print("Synthetic demo: http://127.0.0.1:%d" % http.server_port, flush=True)
        http.serve_forever()
