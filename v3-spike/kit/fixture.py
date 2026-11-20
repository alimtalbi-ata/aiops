"""Original synthetic V3 fixture; no business writes or external calls."""
import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROLE = os.environ.get("FIXTURE_ROLE", "core")
class Handler(BaseHTTPRequestHandler):
    def reply(self, status, payload):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    def do_GET(self):
        if self.path != "/health":
            return self.reply(404, {"error": "not_found"})
        if ROLE == "gamma":
            try:
                with urllib.request.urlopen("http://core:8080/health", timeout=2) as response:
                    if json.load(response) != {"status": "ok", "mode": "SYNTHETIC", "role": "core"}:
                        raise ValueError("unexpected core response")
            except (OSError, ValueError):
                return self.reply(503, {"status": "core_unavailable", "mode": "SYNTHETIC"})
        return self.reply(200, {"status": "ok", "mode": "SYNTHETIC", "role": ROLE})
    def deny(self):
        self.reply(403, {"error": "writes_disabled", "mode": "SYNTHETIC"})
    do_POST = do_PUT = do_PATCH = do_DELETE = deny

if __name__ == "__main__":
    if ROLE not in {"core", "gamma", "demo"}:
        raise SystemExit("invalid fixture role")
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
