import json
import re
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TARGETS = {
    "core": "http://aiops2-core:810/metrics",
    "worker": "http://aiops2-worker:815/metrics",
    "policy": "http://aiops2-policy:813/metrics",
    "twin": "http://aiops2-twin:811/metrics",
}

SAMPLE = re.compile(
    r'^[a-zA-Z_:][a-zA-Z0-9_:]*(?:\{[^}]*\})?\s+'
    r'(?:[+-]?(?:\d+(?:\.\d*)?|\.\d+)|[+-]?Inf|NaN)'
    r'(?:\s+\d+)?$'
)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        service = self.path.removeprefix("/metrics/")
        if self.path != "/metrics/" + service or service not in TARGETS:
            self.send_error(404)
            return

        try:
            with urllib.request.urlopen(TARGETS[service], timeout=4) as response:
                raw = response.read(65536)
                value = json.loads(raw)

            if not isinstance(value, str):
                raise ValueError("Unexpected metrics representation")

            lines = [line.strip() for line in value.splitlines() if line.strip()]
            if not lines or not all(SAMPLE.fullmatch(line) for line in lines):
                raise ValueError("Invalid metrics samples")

            content = (value.rstrip("\n") + "\n").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception:
            self.send_error(503, "Upstream metrics unavailable")

    def do_POST(self):
        self.send_error(405)

ThreadingHTTPServer(("0.0.0.0", 9198), Handler).serve_forever()
