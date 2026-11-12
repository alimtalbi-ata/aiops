"""Disposable TLS/TCP process running the *actual* Core negative ASGI route.

Test-only: the explicit client bypasses Portal's dispatch-disabled preflight.
No real IdP, GLPI, DB query, host access, LIVE or positive authorization.
The independent process imports core.main:app unchanged; an ASGI wrapper logs
only HTTP method/path, never bearer, delegation or response bodies.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

ROOT = Path(__file__).resolve().parents[1]
PINNED_ORIGIN = "https://core.example.test:8443"


class _RequestRecorder:
    def __init__(self, core_app):
        self.core_app = core_app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # No credentials or sensitive headers are ever written to disk.
            with open(os.environ["AIOPS_TEST_CORE_TCP_REQUEST_LOG"],
                      "a", encoding="utf-8") as output:
                output.write(json.dumps({
                    "method": scope["method"], "path": scope["path"],
                }, sort_keys=True) + "\n")
        await self.core_app(scope, receive, send)


# Only the disposable child process imports Core; Portal remains a separate
# HTTPS server with no Core authorization transport or positive ACL enabled.
if os.getenv("AIOPS_TEST_CORE_TCP_PROCESS") == "1":
    from core.main import app as _actual_core_app
    real_core_app = _RequestRecorder(_actual_core_app)
else:
    real_core_app = None


class DisposableRealCoreTCP:
    """Real Core v1 negative endpoint over independently served pinned TLS."""

    def __init__(self, service_bearer: str):
        self.service_bearer = service_bearer
        self.process = None

    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory(prefix="real-core-negative-")
        root = Path(self.temp.name)
        self.request_log = root / "requests.jsonl"
        self.request_log.write_text("", encoding="utf-8")
        self.server_log = open(root / "core.log", "w+b")
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,
                                            "core.example.test")])
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                .public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=1))
                .not_valid_after(datetime.now(timezone.utc) + timedelta(hours=1))
                .add_extension(x509.SubjectAlternativeName([
                    x509.DNSName("core.example.test")]), critical=False)
                .sign(key, hashes.SHA256()))
        certfile, keyfile = root / "core.pem", root / "core.key"
        certfile.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        keyfile.write_bytes(key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption()))
        self.certfile = certfile
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        token_digest = hashlib.sha256(self.service_bearer.encode("ascii")).hexdigest()
        env = os.environ.copy()
        env.update({
            "PYTHONPATH": str(ROOT / "app") + os.pathsep + str(ROOT / "tests"),
            "AIOPS_INTERNAL_TOKEN": "disposable-core-" + "i" * 48,
            "AIOPS_TEST_CORE_TCP_PROCESS": "1",
            "AIOPS_TEST_CORE_TCP_REQUEST_LOG": str(self.request_log),
            "AIOPS_XREF_READ_AUTHZ_JSON": json.dumps([{
                "token_sha256": token_digest, "actor_id": "portal-service",
                "tenant_ids": ["ACME"],
                "permissions": ["actor:resource:authorize"],
            }]),
            # No delegated actor token, IdP introspection or GLPI adapter.
            "AIOPS_XREF_ACTOR_INTROSPECTION_JSON": "",
            "AIOPS_XREF_GLPI_READBACK_JSON": "",
            "AIOPS_XREF_ATTESTATION_KEY": "",
        })
        try:
            self.process = subprocess.Popen([
                sys.executable, "-m", "uvicorn",
                "portal_core_real_tcp_fixture:real_core_app",
                "--app-dir", str(ROOT / "tests"), "--host", "127.0.0.1",
                "--port", str(self.port), "--ssl-keyfile", str(keyfile),
                "--ssl-certfile", str(certfile), "--lifespan", "off",
                "--no-access-log", "--log-level", "error",
            ], cwd=ROOT, env=env, stdout=self.server_log,
                stderr=subprocess.STDOUT)
            context = ssl.create_default_context(cafile=str(certfile))
            for _ in range(100):
                if self.process.poll() is not None:
                    raise RuntimeError("disposable real Core exited before ready")
                try:
                    with socket.create_connection(("127.0.0.1", self.port),
                                                  timeout=0.2) as raw:
                        with context.wrap_socket(
                                raw, server_hostname="core.example.test"):
                            break
                except (OSError, ssl.SSLError):
                    time.sleep(0.1)
            else:
                raise RuntimeError("disposable real Core TLS startup timeout")
            return self
        except Exception:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *_args):
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        if hasattr(self, "server_log") and not self.server_log.closed:
            self.server_log.close()
        if hasattr(self, "temp"):
            self.temp.cleanup()

    def observations(self):
        return [json.loads(line) for line in self.request_log.read_text(
            encoding="utf-8").splitlines() if line]

    def send(self, plan):
        """Explicit *test-only* request; never used by the Portal runtime."""
        if plan.origin != PINNED_ORIGIN or plan.dispatch_allowed is not False:
            raise ValueError("pinned disabled-dispatch plan required")
        context = ssl.create_default_context(cafile=str(self.certfile))
        port = self.port

        class PinnedLoopbackConnection(http.client.HTTPSConnection):
            def connect(self):
                raw = socket.create_connection(("127.0.0.1", port), timeout=3)
                self.sock = context.wrap_socket(raw, server_hostname="core.example.test")

        conn = PinnedLoopbackConnection("core.example.test", 8443,
                                        context=context, timeout=3)
        try:
            conn.request(plan.method, plan.path, body=plan.body,
                         headers=plan.headers)
            response = conn.getresponse()
            body = response.read()
            return response.status, json.loads(body), dict(response.getheaders())
        finally:
            conn.close()
