"""Read-only recipe: deny unsafe destinations before any I/O."""
import unittest
import os
from unittest.mock import MagicMock
from unittest.mock import patch

from scripts.acme_readonly_runtime_recipe import loopback_url, qualify_runtime_readback, main
from test_acme_core_worker_binding import pair, ATTEMPT


class RuntimeRecipeTests(unittest.TestCase):
    def setUp(self):
        self.core = "http://127.0.0.1:17771"
        self.worker = "http://127.0.0.1:17772"
        self.token = "a" * 40

    def check(self, fetch, **changes):
        args = dict(attempt=ATTEMPT, core_base=self.core,
                    worker_base=self.worker, core_token=self.token,
                    worker_token="b" * 40, fetch=fetch)
        args.update(changes)
        return qualify_runtime_readback(**args)

    def test_cli_requires_explicit_isolated_sandbox_opt_in(self):
        with patch.dict(os.environ, {
            "ACME_READONLY_SANDBOX_APPROVED": "",
            "ACME_SANDBOX_ISOLATED": "",
            "ACME_CORE_LOOPBACK_URL": self.core,
            "ACME_WORKER_LOOPBACK_URL": self.worker,
            "ACME_ATTEMPT_ID": ATTEMPT,
            "ACME_CORE_SERVICE_TOKEN": self.token,
            "ACME_WORKER_SERVICE_TOKEN": "b" * 40,
        }):
            self.assertEqual(main(), 2)
        with patch.dict(os.environ, {
            "ACME_READONLY_SANDBOX_APPROVED": "YES",
            "ACME_SANDBOX_ISOLATED": "",
        }):
            self.assertEqual(main(), 2)

    def test_runtime_transport_ignores_proxy_env_and_requires_json(self):
        from scripts.acme_readonly_runtime_recipe import NoRedirect
        from urllib.request import ProxyHandler
        core, worker = pair()
        payloads = [core, worker]
        calls = []
        class Response:
            status = 200
            headers = MagicMock()
            def __init__(self, data, content_type="application/json"):
                self.data = data
                self.headers.get_content_type.return_value = content_type
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, size):
                return self.data
        import json
        responses = [Response(json.dumps(x).encode("utf-8")) for x in payloads]
        class Opener:
            def open(self, request, timeout):
                calls.append(request)
                return responses[len(calls)-1]
        with patch("scripts.acme_readonly_runtime_recipe.build_opener", return_value=Opener()) as build:
            result = self.check(None)
        self.assertEqual(result["status"], "RUNTIME_READBACK_CONSISTENT_ONLY")
        self.assertIsInstance(build.call_args.args[0], ProxyHandler)
        self.assertEqual(build.call_args.args[0].proxies, {})
        self.assertIsInstance(build.call_args.args[1], NoRedirect)
        self.assertEqual([r.get_method() for r in calls], ["GET", "GET"])
        calls.clear()
        responses[0] = Response(b"<html/>", "text/html")
        with patch("scripts.acme_readonly_runtime_recipe.build_opener", return_value=Opener()):
            result = self.check(None)
        self.assertEqual(result["reason"], "READBACK_UNAVAILABLE_OR_INVALID")
        self.assertEqual(len(calls), 1)

    def test_non_loopback_and_redirect_targets_rejected_before_io(self):
        def forbidden(*args):
            raise AssertionError("No I/O allowed")
        for url in ("https://example.org", "http://example.org:7777",
                    "http://127.0.0.1:17771/path", "http://localhost:7777",
                    "http://user:pass@127.0.0.1:7777",
                    "http://127.0.0.1:7777?x=1"):
            with self.subTest(url=url):
                self.assertFalse(loopback_url(url))
                self.assertEqual(self.check(forbidden, core_base=url)["status"], "NO_GO")

    def test_invalid_attempt_and_token_do_not_read(self):
        def forbidden(*args):
            raise AssertionError("No I/O allowed")
        for changes in ({"attempt": "wrong"}, {"core_token": "short"},
                        {"worker_base": self.core}):
            self.assertEqual(self.check(forbidden, **changes)["status"], "NO_GO")

    def test_canonical_pair_read_only_in_order(self):
        core, worker = pair()
        calls = []
        def fetch(url, token):
            calls.append(url)
            return core if len(calls) == 1 else worker
        result = self.check(fetch)
        self.assertEqual(result["status"], "RUNTIME_READBACK_CONSISTENT_ONLY")
        self.assertTrue(result["runtime_evidence_consistent"])
        self.assertFalse(result["viewer_acl_verified"])
        self.assertFalse(result["browser_verified"])
        self.assertFalse(result["real_execution_allowed"])
        for claim in ("remediation_effect_verified", "autonomous_closed_loop_verified",
                      "deployed_sha_attested", "learning_claim_verified"):
            self.assertIs(result[claim], False)
        self.assertEqual(len(calls), 2)
        self.assertTrue(all("/api/sandbox/acme/e2e/" in url for url in calls))

    def test_bad_core_stops_before_worker(self):
        core, _ = pair()
        core["tenant_id"] = "OTHER"
        calls = []
        def fetch(url, token):
            calls.append(url)
            return core
        self.assertEqual(self.check(fetch)["reason"], "CORE_READBACK_REJECTED")
        self.assertEqual(len(calls), 1)

    def test_worker_mismatch_is_no_go(self):
        core, worker = pair()
        worker["effect_allowed"] = True
        calls = []
        def fetch(url, token):
            calls.append(url)
            return core if len(calls) == 1 else worker
        result = self.check(fetch)
        self.assertEqual(result["status"], "NO_GO")
        self.assertIn("WORKER_EFFECT_ALLOWED_INVALID", result["rejection_codes"])


if __name__ == "__main__":
    unittest.main()
