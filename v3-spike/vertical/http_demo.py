"""Loopback-only synthetic HTTP adapter for the existing vertical demo."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from vertical_demo import execute
from correlation_demo import correlate
from core_read import read_run
from lab_context import context
import os

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
        elif self.path == "/api/v1/core-run":
            config = self.server.core_config
            if config is None:
                self.reply(503, b'{"error":"CORE_NOT_CONFIGURED","policy":"DENY"}')
                return
            try:
                result = read_run(*config)
                self.reply(200, json.dumps(result).encode())
            except Exception:
                self.reply(503, b'{"error":"CORE_UNVERIFIED","policy":"DENY"}')
        elif self.path == "/api/v1/incident-context":
            try:
                core = read_run(*self.server.core_config)
                twin_port, evidence_port, node_id, expected_incident = self.server.context_config
                run = core["run"]
                if run["incident_id"] != expected_incident:
                    raise ValueError("incident binding mismatch")
                details = context(twin_port, evidence_port, run["run_id"], node_id)
                self.reply(200, json.dumps({"core":core,"context":details,
                    "binding":"EXPLICIT_SYNTHETIC_LAB_CONFIG","production_authorized":False}).encode())
            except Exception:
                self.reply(503, b'{"error":"CONTEXT_UNVERIFIED","policy":"DENY"}')
        else:
            self.reply(404, b'{"error":"NOT_FOUND"}')

def server(port=0, core_config=None, context_config=None):
    http = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    http.core_config = core_config
    http.context_config = context_config
    return http

if __name__ == "__main__":
    config = None
    if os.environ.get("V3_LAB_CORE_PORT"):
        config = (int(os.environ["V3_LAB_CORE_PORT"]),
                  os.environ["V3_LAB_CORE_TOKEN"], os.environ["V3_LAB_RUN_ID"])
    with server(core_config=config) as http:
        print("Synthetic demo: http://127.0.0.1:%d" % http.server_port, flush=True)
        http.serve_forever()
