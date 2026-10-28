"""Real loopback HTTP fixture tests; NOT actual Core/Twin/Copilot/Portal integration."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import unittest

from scripts.check_demo_field_readonly import UnsafeEndpoint, qualify, validate_base


class FixtureHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        server = self.server
        if self.path == "/health":
            status = 200
            content_type = "application/json"
            payload = json.dumps({"status": "ok", "component": server.component}).encode()
            if server.bad_health:
                payload = b'{"status":"ok","component":"wrong"}'
        elif self.path == "/api/noc/runs/SMOKE-UNAUTH":
            status, content_type, payload = server.auth_status, "application/json", b'{}'
        elif self.path == "/demo-studio":
            status, content_type, payload = 200, "text/html", b"<title>ACME Demo Studio</title>"
        else:
            status, content_type, payload = 404, "text/plain", b"not found"
        if self.path in server.redirect_paths:
            status, payload = 302, b""
        if self.path in server.large_paths:
            payload = b"x" * 140000
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if status == 302:
            self.send_header("Location", "http://127.0.0.1:1/secret")
        self.end_headers()
        self.wfile.write(payload)


class ReadOnlySmokeTests(unittest.TestCase):
    def setUp(self):
        self.servers = []
        self.endpoints = {}
        for name in ("core", "twin", "copilot", "portal"):
            server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
            server.component = name
            server.auth_status = 401
            server.bad_health = False
            server.redirect_paths = set()
            server.large_paths = set()
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.servers.append((server, thread))
            self.endpoints[name] = f"http://127.0.0.1:{server.server_port}"
        self.addCleanup(self.close_servers)

    def close_servers(self):
        for server, thread in self.servers:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_readonly_fixture_success_is_never_go(self):
        result = qualify(self.endpoints)
        self.assertEqual(result["assessment"], "READONLY_PREFLIGHT_PASS")
        self.assertEqual(result["overall"], "NO_GO")
        self.assertEqual(result["tenant_rbac"], "NOT_TESTED")
        self.assertEqual(result["run_incident_evidence_correlation"], "NOT_TESTED")

    def test_wrong_health_component_blocks(self):
        self.servers[1][0].bad_health = True
        self.assertEqual(qualify(self.endpoints)["checks"]["twin_health"], "BLOCKED")

    def test_anonymous_core_200_blocks(self):
        self.servers[0][0].auth_status = 200
        self.assertEqual(qualify(self.endpoints)["checks"]["core_anonymous_noc_denied"], "BLOCKED")

    def test_anonymous_core_503_blocks(self):
        self.servers[0][0].auth_status = 503
        self.assertEqual(qualify(self.endpoints)["assessment"], "BLOCKED")

    def test_redirect_is_not_followed(self):
        self.servers[3][0].redirect_paths.add("/demo-studio")
        self.assertEqual(qualify(self.endpoints)["checks"]["portal_demo_studio_readable"], "BLOCKED")

    def test_oversize_portal_response_blocks(self):
        self.servers[3][0].large_paths.add("/demo-studio")
        self.assertEqual(qualify(self.endpoints)["assessment"], "BLOCKED")

    def test_missing_service_blocks(self):
        self.servers[2][0].shutdown()
        self.servers[2][0].server_close()
        self.assertEqual(qualify(self.endpoints)["checks"]["copilot_health"], "BLOCKED")

    def test_untrusted_destinations_rejected_before_io(self):
        for url in ("http://10.79.94.202:7777", "http://localhost:7777", "http://127.0.0.2:80",
                    "https://127.0.0.1:7777", "http://127.0.0.1:7777/health",
                    "http://127.0.0.1:7777@evil.test", "http://127.0.0.1:7777?token=x",
                    "http://127.0.0.1:0", "http://127.0.0.1:99999"):
            with self.subTest(url=url), self.assertRaises(UnsafeEndpoint):
                validate_base(url)

    def test_no_partial_probe_when_one_url_is_untrusted(self):
        bad = dict(self.endpoints, portal="http://example.com:80")
        with self.assertRaises(UnsafeEndpoint):
            qualify(bad)


if __name__ == "__main__":
    unittest.main()
