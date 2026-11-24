"""Synthetic-only rootless kit smoke HTTP service. No production auth or client data."""
import hashlib
import json
import os
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DIGEST = hashlib.sha256(b"fixture:synthetic-acme:event-1").hexdigest()

def decide(db, request):
    deny = {"decision": "DENY", "accepted": False, "evidence": None}
    if not isinstance(request, dict) or set(request) != {"nonce"}:
        return deny
    nonce = request["nonce"]
    if not isinstance(nonce, str) or not 1 <= len(nonce) <= 128 or not nonce.isascii() or not all(c.isalnum() or c in "._-" for c in nonce):
        return deny
    try:
        db.execute("BEGIN IMMEDIATE")
        db.execute("INSERT INTO consumed_nonce(tenant,nonce) VALUES (?,?)", ("synthetic-acme", nonce))
        db.commit()
    except sqlite3.Error:
        if db.in_transaction:
            db.rollback()
        return deny
    return {"decision": "DENY", "accepted": True, "evidence": {
        "tenant_id": "synthetic-acme", "resource_id": "opaque:synthetic-host-1",
        "event_id": "synthetic-event-1", "digest": DIGEST}}

def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result

def handler(db_path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass
        def reply(self, status, value):
            payload = json.dumps(value, sort_keys=True).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        def do_GET(self):
            if self.path != "/health":
                return self.reply(404, {"error": "not_found"})
            try:
                with sqlite3.connect(db_path) as db:
                    db.execute("SELECT 1 FROM consumed_nonce LIMIT 1")
            except sqlite3.Error:
                return self.reply(503, {"status": "unhealthy"})
            return self.reply(200, {"status": "ok", "mode": "synthetic-only"})
        def do_POST(self):
            if self.path != "/v1/synthetic/deny":
                return self.reply(404, {"error": "not_found"})
            # Reject ambiguous framing before reading or mutating SQLite.
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) != 1 or self.headers.get_all("Transfer-Encoding", []):
                return self.reply(400, {"error": "ambiguous_framing"})
            length = lengths[0]
            if not length.isascii() or not length.isdecimal() or len(length) > 4 or int(length) > 2048:
                return self.reply(413, {"error": "invalid_size"})
            try:
                request = json.loads(self.rfile.read(int(length)), object_pairs_hook=reject_duplicate_keys)
            except (ValueError, UnicodeError):
                return self.reply(400, {"error": "invalid_json"})
            with sqlite3.connect(db_path, timeout=0.2, isolation_level=None) as db:
                result = decide(db, request)
            self.reply(200, result)
    return Handler

def serve(root, host="127.0.0.1", port=8088):
    root = Path(root).resolve(strict=True)
    db_path = root / "synthetic-evidence.sqlite3"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE IF NOT EXISTS consumed_nonce(tenant TEXT NOT NULL, nonce TEXT NOT NULL, PRIMARY KEY(tenant,nonce))")
    ThreadingHTTPServer((host, port), handler(db_path)).serve_forever()

if __name__ == "__main__":
    serve(os.environ["AIOPS_V3_SYNTHETIC_DATA_ROOT"],
          os.environ.get("AIOPS_V3_SYNTHETIC_HOST", "127.0.0.1"),
          int(os.environ.get("AIOPS_V3_SYNTHETIC_PORT", "8088")))
