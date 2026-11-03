"""Test-only independent HTTPS Core TCP UNKNOWN peer. Never a Portal client.

Only loopback sockets are used. A synthetic CA/certificate is trusted for the
pinned core.example.test SNI; no DNS, real Core, IdP or GLPI is contacted.
The explicit send() bypasses dispatch_allowed=False solely inside tests.
"""
from __future__ import annotations

import http.client
import json
from pathlib import Path
import socket
import ssl
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

PINNED_ORIGIN = "https://core.example.test:8443"
SCHEMA = "aiops.core-actor-resource-authorization.v1"


class DisposableCoreUnknownTCP:
    """Independent TLS TCP peer, returning negative Core v1 wire shapes only."""

    def __init__(self):
        self.observations = []
        self.reply = "UNKNOWN"

    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory(prefix="synthetic-core-tcp-")
        root = Path(self.temp.name)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "core.example.test")])
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                .public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=1))
                .not_valid_after(datetime.now(timezone.utc) + timedelta(hours=1))
                .add_extension(x509.SubjectAlternativeName(
                    [x509.DNSName("core.example.test")]), critical=False)
                .sign(key, hashes.SHA256()))
        self.certfile = root / "core.pem"
        keyfile = root / "core.key"
        self.certfile.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        keyfile.write_bytes(key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption()))
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = self.headers.get("Content-Length", "")
                if not length.isdigit() or int(length) > 16384:
                    self.send_error(400)
                    return
                body = self.rfile.read(int(length))
                owner.observations.append({
                    "method": "POST", "path": self.path,
                    "host": self.headers.get("Host"),
                    "authorization": self.headers.get("Authorization"),
                    "headers": dict(self.headers), "body": body,
                })
                payload = json.dumps({
                    "schema": SCHEMA, "decision": owner.reply,
                }, sort_keys=True, separators=(",", ":")).encode("ascii")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Pragma", "no-cache")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self):
                owner.observations.append({"method": "GET", "path": self.path})
                self.send_error(405)

            def log_message(self, *_args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(self.certfile), str(keyfile))
        self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp.cleanup()

    def send(self, plan):
        """Test-only explicit TCP round-trip; production dispatch stays disabled."""
        if plan.origin != PINNED_ORIGIN or plan.dispatch_allowed is not False:
            raise ValueError("test requires exact pinned origin and disabled dispatch")
        context = ssl.create_default_context(cafile=str(self.certfile))
        peer_port = self.server.server_address[1]

        class PinnedLoopbackConnection(http.client.HTTPSConnection):
            def connect(self):
                raw = socket.create_connection(("127.0.0.1", peer_port), timeout=3)
                self.sock = context.wrap_socket(raw, server_hostname="core.example.test")

        conn = PinnedLoopbackConnection("core.example.test", 8443,
                                        context=context, timeout=3)
        try:
            conn.request(plan.method, plan.path, body=plan.body, headers=plan.headers)
            response = conn.getresponse()
            data = response.read()
            return response.status, json.loads(data), dict(response.getheaders())
        finally:
            conn.close()
