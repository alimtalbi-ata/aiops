"""Real HTTP transport integration against ephemeral loopback-only fake servers.

No production services, Temporal, GLPI, browser, or Docker. Every server is
bound to 127.0.0.1 on an ephemeral port, closed after each test.
"""
from __future__ import annotations

import json
import os
import threading
import unittest
from contextlib import ExitStack, contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from scripts.acme_readonly_runtime_recipe import qualify_runtime_readback
from test_acme_core_worker_binding import ATTEMPT, pair

CORE_TOKEN = "c" * 40
WORKER_TOKEN = "w" * 40
PATH = "/api/sandbox/acme/e2e/" + ATTEMPT


@contextmanager
def fake_endpoint(receipt, token, *, status=200, content_type="application/json",
                  redirect=None, oversized=False):
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append((self.command, self.path,
                          self.headers.get("Authorization")))
            if self.path != PATH or self.headers.get("Authorization") != "Bearer " + token:
                self.send_response(403)
                self.end_headers()
                return
            if redirect is not None:
                self.send_response(302)
                self.send_header("Location", redirect)
                self.end_headers()
                return
            body = (b"x" * 262145 if oversized else
                    json.dumps(receipt).encode("utf-8"))
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except BrokenPipeError:
                pass

        def do_POST(self):
            calls.append(("POST", self.path, None))
            self.send_response(405)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:" + str(server.server_port), calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


class RealLoopbackTransportTests(unittest.TestCase):
    def run_pair(self, *, core=None, worker=None, core_opts=None, worker_opts=None):
        good_core, good_worker = pair()
        with ExitStack() as stack:
            cb, cc = stack.enter_context(fake_endpoint(
                good_core if core is None else core, CORE_TOKEN, **(core_opts or {})))
            wb, wc = stack.enter_context(fake_endpoint(
                good_worker if worker is None else worker, WORKER_TOKEN, **(worker_opts or {})))
            # A malicious environment proxy must not receive loopback traffic.
            with patch.dict(os.environ, {"HTTP_PROXY": "http://127.0.0.1:1",
                                         "http_proxy": "http://127.0.0.1:1",
                                         "NO_PROXY": "", "no_proxy": ""}):
                result = qualify_runtime_readback(
                    attempt=ATTEMPT, core_base=cb, worker_base=wb,
                    core_token=CORE_TOKEN, worker_token=WORKER_TOKEN)
            return result, cc, wc

    def test_success_is_only_readback_consistency(self):
        result, core_calls, worker_calls = self.run_pair()
        self.assertEqual(result["status"], "RUNTIME_READBACK_CONSISTENT_ONLY")
        self.assertTrue(result["runtime_evidence_consistent"])
        for field in ("viewer_acl_verified", "browser_verified",
                      "remediation_effect_verified", "autonomous_closed_loop_verified",
                      "deployed_sha_attested", "learning_claim_verified",
                      "real_execution_allowed"):
            self.assertIs(result[field], False)
        self.assertEqual(core_calls, [("GET", PATH, "Bearer " + CORE_TOKEN)])
        self.assertEqual(worker_calls, [("GET", PATH, "Bearer " + WORKER_TOKEN)])

    def test_core_identity_mismatch_prevents_worker_access(self):
        core, _ = pair()
        core["tenant_id"] = "FOREIGN-TENANT"
        result, core_calls, worker_calls = self.run_pair(core=core)
        self.assertEqual(result["reason"], "CORE_READBACK_REJECTED")
        self.assertEqual(len(core_calls), 1)
        self.assertEqual(worker_calls, [])

    def test_core_redirect_is_not_followed(self):
        result, core_calls, worker_calls = self.run_pair(
            core_opts={"redirect": "http://127.0.0.1:9/unsafe"})
        self.assertEqual(result["status"], "NO_GO")
        self.assertEqual(result["reason"], "READBACK_UNAVAILABLE_OR_INVALID")
        self.assertEqual(len(core_calls), 1)
        self.assertEqual(worker_calls, [])

    def test_non_json_core_prevents_worker_access(self):
        result, core_calls, worker_calls = self.run_pair(
            core_opts={"content_type": "text/html"})
        self.assertEqual(result["reason"], "READBACK_UNAVAILABLE_OR_INVALID")
        self.assertEqual(len(core_calls), 1)
        self.assertEqual(worker_calls, [])

    def test_oversized_core_prevents_worker_access(self):
        result, core_calls, worker_calls = self.run_pair(
            core_opts={"oversized": True})
        self.assertEqual(result["reason"], "READBACK_UNAVAILABLE_OR_INVALID")
        self.assertEqual(len(core_calls), 1)
        self.assertEqual(worker_calls, [])

    def test_core_http_error_prevents_worker_access(self):
        result, core_calls, worker_calls = self.run_pair(
            core_opts={"status": 503})
        self.assertEqual(result["reason"], "READBACK_UNAVAILABLE_OR_INVALID")
        self.assertEqual(len(core_calls), 1)
        self.assertEqual(worker_calls, [])

    def test_worker_receipt_mismatch_is_rejected(self):
        _, worker = pair()
        worker["effect_allowed"] = True
        result, core_calls, worker_calls = self.run_pair(worker=worker)
        self.assertEqual(result["reason"], "CORE_WORKER_INCONSISTENT")
        self.assertIn("WORKER_EFFECT_ALLOWED_INVALID", result["rejection_codes"])
        self.assertEqual(len(core_calls), 1)
        self.assertEqual(len(worker_calls), 1)

    def test_worker_redirect_rejected(self):
        result, core_calls, worker_calls = self.run_pair(
            worker_opts={"redirect": "http://127.0.0.1:9/unsafe"})
        self.assertEqual(result["reason"], "READBACK_UNAVAILABLE_OR_INVALID")
        self.assertEqual(len(core_calls), 1)
        self.assertEqual(len(worker_calls), 1)


if __name__ == "__main__":
    unittest.main()
