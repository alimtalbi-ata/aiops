"""Loopback-only synthetic HTTP adapter for the existing vertical demo."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from vertical_demo import execute
from correlation_demo import correlate
from core_read import read_run
from lab_context import context
from policy_demo import simulation_decision
from copilot_context import answer
import os
from hitl_demo import ApprovalGate
from ingestion_demo import ingest
from ingestion_store import persist
from core_ingest import create_and_persist
from mattermost_demo import command, authenticate

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

    def do_POST(self):
        if self.path == '/api/v1/mattermost/command':
            try:
                if self.headers.get('Content-Type','').split(';')[0] != 'application/x-www-form-urlencoded':
                    raise ValueError('form required')
                length=int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 4096:
                    raise ValueError('invalid length')
                token,channel=self.server.mattermost_config
                body=self.rfile.read(length)
                authenticate(body,token,channel)
                core=read_run(*self.server.core_config)
                twin,evidence,node,expected=self.server.context_config
                run=core['run']
                if run['incident_id']!=expected or run['mode']!='DEMO':
                    raise ValueError('binding mismatch')
                details=context(twin,evidence,run['run_id'],node)
                self.reply(200,json.dumps(command(body,token,channel,core,details)).encode())
            except Exception:
                self.reply(403,b'{"error":"CHATOPS_UNVERIFIED","policy":"DENY"}')
            return
        if self.path not in ("/api/v1/hitl/request","/api/v1/hitl/decide","/api/v1/ingest","/api/v1/ingest/persist","/api/v1/ingest/create"):
            self.reply(404,b'{"error":"NOT_FOUND"}')
            return
        try:
            if self.headers.get("Origin") != "http://127.0.0.1:%d" % self.server.server_port:
                raise ValueError("Origin mismatch")
            if self.headers.get("Content-Type") != "application/json":
                raise ValueError("JSON required")
            length=int(self.headers.get("Content-Length","0"))
            if not 0 < length <= 4096:
                raise ValueError("Invalid length")
            data=json.loads(self.rfile.read(length))
            if self.path=="/api/v1/ingest":
                self.reply(200,json.dumps(ingest(data)).encode())
                return
            if self.path=="/api/v1/ingest/create":
                port,token,_=self.server.core_config
                _,evidence,_,_=self.server.context_config
                self.reply(200,json.dumps(create_and_persist(data,port,token,evidence)).encode())
                return
            core=read_run(*self.server.core_config)
            twin,evidence,node,expected=self.server.context_config
            run=core["run"]
            if run["incident_id"]!=expected:
                raise ValueError("Incident mismatch")
            if self.path=="/api/v1/ingest/persist":
                if run["mode"]!="DEMO":
                    raise ValueError("DEMO required")
                self.reply(200,json.dumps(persist(data,evidence,run["run_id"])).encode())
                return
            details=context(twin,evidence,run["run_id"],node)
            args=(expected,run["run_id"],details["evidence"])
            if self.path.endswith("/request"):
                result=self.server.approval_gate.request(*args)
            else:
                result=self.server.approval_gate.decide(data["request_id"],*args,data.get("approved"))
            self.reply(200,json.dumps(result).encode())
        except Exception:
            self.reply(503,b'{"error":"REQUEST_UNVERIFIED","policy":"DENY"}')

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
        elif self.path in ("/api/v1/incident-context", "/api/v1/incident-context?decision=simulate"):
            try:
                core = read_run(*self.server.core_config)
                twin_port, evidence_port, node_id, expected_incident = self.server.context_config
                run = core["run"]
                if run["incident_id"] != expected_incident:
                    raise ValueError("incident binding mismatch")
                details = context(twin_port, evidence_port, run["run_id"], node_id)
                result={"core":core,"context":details,
                    "binding":"EXPLICIT_SYNTHETIC_LAB_CONFIG","production_authorized":False}
                result["copilot"]=answer(core,details)
                if self.path.endswith("?decision=simulate"):
                    result["simulation"]=simulation_decision(self.server.policy_port,len(details["evidence"]))
                self.reply(200,json.dumps(result).encode())
            except Exception:
                self.reply(503, b'{"error":"CONTEXT_UNVERIFIED","policy":"DENY"}')
        else:
            self.reply(404, b'{"error":"NOT_FOUND"}')

def server(port=0, core_config=None, context_config=None, policy_port=None, mattermost_config=None):
    http = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    http.core_config = core_config
    http.context_config = context_config
    http.policy_port = policy_port
    http.mattermost_config = mattermost_config
    http.approval_gate = ApprovalGate()
    return http

if __name__ == "__main__":
    config = None
    if os.environ.get("V3_LAB_CORE_PORT"):
        config = (int(os.environ["V3_LAB_CORE_PORT"]),
                  os.environ["V3_LAB_CORE_TOKEN"], os.environ["V3_LAB_RUN_ID"])
    with server(core_config=config) as http:
        print("Synthetic demo: http://127.0.0.1:%d" % http.server_port, flush=True)
        http.serve_forever()
