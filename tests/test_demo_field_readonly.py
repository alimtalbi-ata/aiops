"""Real loopback HTTP fixture tests; NOT actual Core/Twin/Copilot/Portal integration."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import io
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import threading
import unittest

from scripts.check_demo_field_readonly import UnsafeEndpoint, main, qualify, validate_base, verify_local_applied_sha


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
        elif self.path == "/api/noc/runs/SMOKE-UNAUTH/evidence-refs":
            status, content_type, payload = server.auth_status, "application/json", b'{}'
        elif self.path == "/demo-studio":
            status, content_type, payload = 200, "text/html", server.landing_body
        elif self.path == "/runs":
            status, content_type, payload = 200, "text/html", b"<h1>Incidents &amp; Runs</h1>"
        elif self.path == "/timeline":
            status, content_type, payload = 200, "text/html", b"<h1>Timeline des incidents</h1>"
        elif self.path == "/demo-studio/business-story":
            status, content_type, payload = server.story_status, "text/html", server.story_body
        else:
            status, content_type, payload = 404, "text/plain", b"not found"
        if self.path in server.redirect_paths:
            status, payload = 302, b""
        if self.path in server.missing_paths:
            status, payload = 404, b""
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
            server.story_status = 200
            server.landing_body = (
                b'<title>ACME Demo Studio</title>'
                b'<a href="/runs">Runs</a><a href="/timeline">Timeline</a>'
            )
            server.story_body = (
                b'<section id="acme-step-1">ACME-SAN-FABRIC-A SIMULATED UNKNOWN</section>'
                b'<section id="acme-step-6">PROJECTED_ONLY</section>'
                b'<a href="/twin">Twin</a><a href="/policy-control">Policy</a>'
                b'<a href="/evidence">Evidence</a>'
            )
            server.redirect_paths = set()
            server.missing_paths = set()
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

    def test_story_route_is_checked_without_e2e_claim(self):
        receipt = qualify(self.endpoints)
        self.assertEqual(receipt["checks"]["portal_acme_business_story_navigable"], "PASS")
        self.assertEqual(receipt["overall"], "NO_GO")
        self.assertEqual(receipt["core_temporal_analyst_critic_policy_evidence"], "NOT_TESTED")

    def test_landing_requires_real_run_and_timeline_links(self):
        portal = self.servers[3][0]
        portal.landing_body = b"<title>ACME Demo Studio</title>"
        self.assertEqual(qualify(self.endpoints)["checks"]["portal_demo_studio_readable"], "BLOCKED")

    def test_run_and_timeline_routes_are_checked(self):
        portal = self.servers[3][0]
        receipt = qualify(self.endpoints)
        self.assertEqual(receipt["checks"]["portal_runs_readable"], "PASS")
        self.assertEqual(receipt["checks"]["portal_timeline_readable"], "PASS")
        self.assertEqual(receipt["overall"], "NO_GO")
        for path, key in (("/runs", "portal_runs_readable"),
                          ("/timeline", "portal_timeline_readable")):
            portal.missing_paths.add(path)
            self.assertEqual(qualify(self.endpoints)["checks"][key], "BLOCKED")
            portal.missing_paths.clear()
            portal.redirect_paths.add(path)
            self.assertEqual(qualify(self.endpoints)["checks"][key], "BLOCKED")
            portal.redirect_paths.clear()

    def test_missing_or_unqualified_business_story_blocks(self):
        portal = self.servers[3][0]
        portal.story_status = 404
        self.assertEqual(qualify(self.endpoints)["checks"]["portal_acme_business_story_navigable"], "BLOCKED")
        portal.story_status = 200
        portal.story_body = b'<html>generic portal</html>'
        self.assertEqual(qualify(self.endpoints)["assessment"], "BLOCKED")

    def test_business_story_redirect_and_oversize_block(self):
        portal = self.servers[3][0]
        portal.redirect_paths.add("/demo-studio/business-story")
        self.assertEqual(qualify(self.endpoints)["assessment"], "BLOCKED")
        portal.redirect_paths.clear()
        portal.large_paths.add("/demo-studio/business-story")
        self.assertEqual(qualify(self.endpoints)["assessment"], "BLOCKED")

    def test_wrong_health_component_blocks(self):
        self.servers[1][0].bad_health = True
        self.assertEqual(qualify(self.endpoints)["checks"]["twin_health"], "BLOCKED")

    def test_anonymous_core_200_blocks(self):
        self.servers[0][0].auth_status = 200
        self.assertEqual(qualify(self.endpoints)["checks"]["core_anonymous_noc_denied"], "BLOCKED")

    def test_anonymous_core_404_blocks(self):
        # Unknown route is not evidence of an authorization denial.
        self.servers[0][0].auth_status = 404
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

    def test_applied_sha_match_remains_unattested_and_never_go(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "applied.sha"
            sha = "a" * 40
            for content in (sha, sha + "\n"):
                path.write_text(content)
                self.assertEqual(verify_local_applied_sha(str(path), sha), "MATCH_UNATTESTED")
            result = qualify(self.endpoints, "MATCH_UNATTESTED")
            self.assertEqual(result["checks"]["local_applied_sha_consistency"], "PASS")
            self.assertEqual(result["applied_sha_verified"], "MATCH_UNATTESTED")
            self.assertEqual(result["overall"], "NO_GO")

    def test_applied_sha_mismatch_and_invalid_format_block(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "applied.sha"
            path.write_text("b" * 40 + "\n")
            for sha in ("a" * 40, "A" * 40, "a" * 39, "a" * 40 + "x"):
                self.assertEqual(verify_local_applied_sha(str(path), sha), "BLOCKED")
            self.assertEqual(verify_local_applied_sha("relative/applied.sha", "b" * 40), "BLOCKED")
            self.assertEqual(qualify(self.endpoints, "BLOCKED")["assessment"], "BLOCKED")

    def test_applied_sha_symlink_directory_and_oversize_block(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "applied.sha"
            target = Path(root) / "target.sha"
            sha = "c" * 40
            target.write_text(sha)
            path.symlink_to(target)
            self.assertEqual(verify_local_applied_sha(str(path), sha), "BLOCKED")
            self.assertEqual(verify_local_applied_sha(root, sha), "BLOCKED")
            path.unlink()
            path.write_text(sha + "\n" + "extra")
            self.assertEqual(verify_local_applied_sha(str(path), sha), "BLOCKED")
            self.assertEqual(verify_local_applied_sha(str(Path(root) / "missing"), sha), "BLOCKED")

    def test_applied_sha_mismatch_blocks_before_http_and_redacts_path(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "secret-path-applied.sha"
            path.write_text("d" * 40)
            args = [item for name, url in self.endpoints.items()
                    for item in ("--" + name + "-url", url)]
            args += ["--expected-sha", "e" * 40, "--applied-sha-file", str(path)]
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(args)
            receipt = json.loads(output.getvalue())
            self.assertEqual(exit_code, 2)
            self.assertEqual(receipt["assessment"], "BLOCKED")
            self.assertEqual(receipt["overall"], "NO_GO")
            self.assertEqual(receipt["field_e2e"], "NOT_TESTED")
            self.assertNotIn(str(path), output.getvalue())
            self.assertNotIn("e" * 40, output.getvalue())
            self.assertNotIn("checks", receipt)

    def test_applied_sha_matching_cli_is_still_not_e2e(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "applied.sha"
            sha = "f" * 40
            path.write_text(sha + "\n")
            args = [item for name, url in self.endpoints.items()
                    for item in ("--" + name + "-url", url)]
            args += ["--expected-sha", sha, "--applied-sha-file", str(path)]
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(args)
            receipt = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(receipt["assessment"], "READONLY_PREFLIGHT_PASS")
            self.assertEqual(receipt["applied_sha_verified"], "MATCH_UNATTESTED")
            self.assertEqual(receipt["overall"], "NO_GO")
            self.assertEqual(receipt["core_temporal_analyst_critic_policy_evidence"], "NOT_TESTED")

    def test_applied_sha_flags_must_be_paired(self):
        args = [item for name, url in self.endpoints.items()
                for item in ("--" + name + "-url", url)]
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(args + ["--expected-sha", "f" * 40])
        self.assertEqual(exit_code, 2)
        self.assertEqual(json.loads(output.getvalue())["reason"], "applied_sha_pair_required")

    def test_invalid_applied_status_is_refused(self):
        with self.assertRaises(UnsafeEndpoint):
            qualify(self.endpoints, "VERIFIED_LIVE")


if __name__ == "__main__":
    unittest.main()
