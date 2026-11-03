"""Test-only independent TLS peers: proposed signed Core and native GLPI human reads.

Neither peer is a production Core/GLPI instance. The Core signer is synthetic,
the GLPI User/Profile/Entity/Ticket records are synthetic, and explicit test
sends bypass Portal's permanently disabled dispatch. No write endpoint exists.
"""
from __future__ import annotations

import base64
import copy
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
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

from portal.core_authz_transport import _canonical_signed_bytes

CORE_ORIGIN = "https://core.example.test:8443"
GLPI_ORIGIN = "https://glpi.example.test:8443"
CORE_PATH = "/api/tenants/ACME/runs/RUN-ACME-123/actor-resource-authorization"
_HEADERS = {
    "Cache-Control": "no-store", "Pragma": "no-cache",
    "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
}


def _b64(number):
    raw = number.to_bytes((number.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _cert(root, host):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=1))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(hours=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(host)]),
                           critical=False).sign(key, hashes.SHA256()))
    certfile, keyfile = root / (host + ".pem"), root / (host + ".key")
    certfile.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    keyfile.write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption()))
    return certfile, keyfile


def synthetic_native_glpi_shape_matches(rows, binding, *, glpi_user_id=77):
    """Test-only native shape assertion, NOT a human permission or Portal ACL.

    Mirrors the independent Core contract: active GLPI User, exact Profile
    with native Ticket READ bit (not READMY), active Entity, and exact Ticket.
    Even a matching synthetic snapshot has no authorization significance.
    """
    if not isinstance(rows, dict) or set(rows) != {
            "getFullSession", "User", "Profile", "Entity", "Ticket"}:
        return False
    session = rows["getFullSession"].get("session") if isinstance(
        rows["getFullSession"], dict) else None
    if not isinstance(session, dict) or type(session.get("glpiID")) is not int:
        return False
    profile = session.get("glpiactiveprofile")
    entities = session.get("glpiactiveentities")
    if (session["glpiID"] != glpi_user_id
            or not isinstance(profile, dict)
            or type(profile.get("id")) is not int
            or not isinstance(entities, list)
            or any(type(i) is not int for i in entities)
            or int(binding.glpi_entity_id) not in entities):
        return False
    user, right, entity, ticket = (rows[k] for k in
                                  ("User", "Profile", "Entity", "Ticket"))
    if any(not isinstance(row, dict) for row in (user, right, entity, ticket)):
        return False
    return (type(user.get("id")) is int and user["id"] == glpi_user_id
            and type(user.get("is_active")) is int and user["is_active"] == 1
            and type(right.get("id")) is int and right["id"] == profile["id"]
            and type(right.get("ticket")) is int and (right["ticket"] & 1) == 1
            and type(entity.get("id")) is int
            and entity["id"] == int(binding.glpi_entity_id)
            and type(ticket.get("id")) is int
            and ticket["id"] == int(binding.ticket_id)
            and type(ticket.get("entities_id")) is int
            and ticket["entities_id"] == int(binding.glpi_entity_id))


class DisposableSignedCoreNativeGlpi:
    """Two independent loopback TLS origins; no Portal routing or GLPI writes."""

    def __init__(self, service_bearer):
        self.service_bearer = service_bearer
        self.payload = None
        self.core_observations = []
        self.glpi_observations = []
        self.signing_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048)
        self.signer_kid = "disposable-core-signer"
        self.jwks = {"keys": [self._signer_jwk()]}
        self.native_rows = {
            "getFullSession": {"session": {
                "glpiID": 77, "glpiactiveprofile": {"id": 4},
                "glpiactiveentities": [42]}},
            "User": {"id": 77, "is_active": 1},
            "Profile": {"id": 4, "ticket": 1},
            "Entity": {"id": 42},
            "Ticket": {"id": 123, "entities_id": 42},
        }
        # Test-only GLPI native Ticket_User relation. This does NOT prove
        # effective READMY, since GLPI may impose further profile/entity rules.
        self.ticket_users = [{"id": 9, "tickets_id": 123,
                              "users_id": 77, "type": 1}]

    def _signer_jwk(self):
        numbers = self.signing_key.public_key().public_numbers()
        return {"kid": self.signer_kid, "kty": "RSA", "alg": "RS256",
                "use": "sig", "n": _b64(numbers.n), "e": _b64(numbers.e)}

    def rotate_signer(self, *, kid="disposable-core-signer-next",
                      retain_previous=False):
        """Test-only key rotation; callers must pin the resulting JWKS."""
        if not isinstance(kid, str) or not kid or kid == self.signer_kid:
            raise ValueError("a distinct signer kid is required")
        previous = list(self.jwks["keys"]) if retain_previous else []
        self.signing_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048)
        self.signer_kid = kid
        self.jwks = {"keys": previous + [self._signer_jwk()]}


    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory(prefix="signed-core-native-glpi-")
        root = Path(self.temp.name)
        self.core_cert, core_key = _cert(root, "core.example.test")
        self.glpi_cert, glpi_key = _cert(root, "glpi.example.test")
        owner = self

        class CoreHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                size = self.headers.get("Content-Length", "")
                if (self.path != CORE_PATH or not size.isdigit()
                        or int(size) > 16384
                        or self.headers.get("Authorization") !=
                        "Bearer " + owner.service_bearer):
                    self.send_error(400)
                    return
                body = self.rfile.read(int(size))
                try:
                    request = json.loads(body)
                except (ValueError, UnicodeError):
                    self.send_error(400)
                    return
                owner.core_observations.append({
                    "method": "POST", "path": self.path, "body": request})
                payload = copy.deepcopy(owner.payload)
                if payload is None:
                    self.send_error(503)
                    return
                signed = _canonical_signed_bytes(CORE_ORIGIN, payload)
                signature = base64.urlsafe_b64encode(owner.signing_key.sign(
                    signed, padding.PKCS1v15(), hashes.SHA256()
                )).rstrip(b"=").decode("ascii")
                self._json(200, {"payload": payload, "signature": {
                    "alg": "RS256", "kid": owner.signer_kid,
                    "signature": signature}})

            def do_GET(self):
                owner.core_observations.append({
                    "method": "GET", "path": self.path})
                self.send_error(405)

            def _json(self, code, body):
                raw = json.dumps(body, sort_keys=True).encode("utf-8")
                self.send_response(code)
                for key, value in _HEADERS.items():
                    self.send_header(key, value)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *_args):
                pass

        class GlpiHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                owner.glpi_observations.append({
                    "method": "GET", "path": self.path})
                if (self.headers.get("App-Token") != "synthetic-app-token"
                        or self.headers.get("Session-Token") !=
                        "synthetic-human-session"):
                    self.send_error(401)
                    return
                routes = {
                    "/apirest.php/getFullSession": "getFullSession",
                    "/apirest.php/User/77": "User",
                    "/apirest.php/Profile/4": "Profile",
                    "/apirest.php/Entity/42": "Entity",
                    "/apirest.php/Ticket/123": "Ticket",
                    "/apirest.php/Ticket/123/Ticket_User": "Ticket_User",
                }
                name = routes.get(self.path)
                if name is None:
                    self.send_error(404)
                    return
                row = (owner.ticket_users if name == "Ticket_User"
                       else owner.native_rows[name])
                raw = json.dumps(row).encode("utf-8")
                self.send_response(200)
                for key, value in _HEADERS.items():
                    self.send_header(key, value)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_POST(self):
                owner.glpi_observations.append({
                    "method": "POST", "path": self.path})
                self.send_error(405)

            def log_message(self, *_args):
                pass

        self.servers = []
        self.threads = []
        try:
            for handler, certfile, keyfile in (
                    (CoreHandler, self.core_cert, core_key),
                    (GlpiHandler, self.glpi_cert, glpi_key)):
                server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.load_cert_chain(str(certfile), str(keyfile))
                server.socket = context.wrap_socket(
                    server.socket, server_side=True)
                thread = threading.Thread(target=server.serve_forever,
                                          daemon=True)
                thread.start()
                self.servers.append(server)
                self.threads.append(thread)
            return self
        except Exception:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *_args):
        for server in getattr(self, "servers", []):
            server.shutdown()
            server.server_close()
        for thread in getattr(self, "threads", []):
            thread.join(timeout=5)
        if hasattr(self, "temp"):
            self.temp.cleanup()

    def _request(self, index, host, certfile, method, path, *, body=None,
                 headers=None):
        port = self.servers[index].server_address[1]
        context = ssl.create_default_context(cafile=str(certfile))

        class PinnedConnection(http.client.HTTPSConnection):
            def connect(self):
                raw = socket.create_connection(("127.0.0.1", port), timeout=3)
                self.sock = context.wrap_socket(raw, server_hostname=host)

        connection = PinnedConnection(host, 8443, context=context, timeout=3)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            raw = response.read()
            return response.status, json.loads(raw), dict(response.getheaders())
        finally:
            connection.close()

    def send_core(self, plan):
        """Explicit test-only send; NEVER a Portal dispatch or actor ACL."""
        if plan.origin != CORE_ORIGIN or plan.dispatch_allowed is not False:
            raise ValueError("pinned disabled-dispatch plan required")
        return self._request(0, "core.example.test", self.core_cert,
                             "POST", plan.path, body=plan.body,
                             headers=plan.headers)

    def read_native_glpi(self):
        """Explicit independent synthetic human-session GETs; no real GLPI."""
        paths = {
            "getFullSession": "/apirest.php/getFullSession",
            "User": "/apirest.php/User/77",
            "Profile": "/apirest.php/Profile/4",
            "Entity": "/apirest.php/Entity/42",
            "Ticket": "/apirest.php/Ticket/123",
        }
        rows = {}
        for name, path in paths.items():
            status, body, _ = self._request(
                1, "glpi.example.test", self.glpi_cert, "GET", path,
                headers={"App-Token": "synthetic-app-token",
                         "Session-Token": "synthetic-human-session"})
            if status != 200:
                raise ValueError("disposable GLPI readback unavailable")
            rows[name] = body
        return rows

    def read_ticket_users(self):
        """Test-only native Ticket_User GET; never a permission or Portal fetch."""
        status, body, _ = self._request(
            1, "glpi.example.test", self.glpi_cert, "GET",
            "/apirest.php/Ticket/123/Ticket_User",
            headers={"App-Token": "synthetic-app-token",
                     "Session-Token": "synthetic-human-session"})
        if status != 200 or not isinstance(body, list):
            raise ValueError("disposable Ticket_User readback unavailable")
        return body
