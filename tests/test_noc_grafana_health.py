"""Offline HTTP contract tests. Actual Grafana integration runs separately in CI."""
import json
import os
import pathlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from portal import noc_grafana_health as module

TOKEN = "synthetic-read-token-only"

class Response:
    def __init__(self, url, payload=None, content_type="application/json", code=200):
        self.url = url
        self.body = json.dumps(payload if payload is not None else
                               {"database": "ok", "version": "11.6.0"}).encode()
        self.headers = {"Content-Type": content_type}
        self.code = code
    def geturl(self): return self.url
    def getcode(self): return self.code
    def read(self, n): return self.body[:n]
    def __enter__(self): return self
    def __exit__(self, *args): return False

class Opener:
    def __init__(self, response=None):
        self.response = response
        self.called = 0
    def open(self, req, timeout):
        self.called += 1
        assert req.get_method() == "GET"
        assert req.full_url == "http://127.0.0.1:3000/api/health"
        assert timeout == 3
        return self.response or Response(req.full_url)

class GrafanaHealthContractTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(module.router)
        self.client = TestClient(app)
        self.env = patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": TOKEN,
                                           "AIOPS_GRAFANA_READ_URL": "http://127.0.0.1:3000"})
        self.env.start()
        self.addCleanup(self.env.stop)
    def get(self, token=TOKEN):
        return self.client.get("/api/noc/grafana-health",
                               headers={"Authorization": "Bearer " + token})
    def test_auth_before_network(self):
        with patch.object(module, "read_grafana_health", side_effect=AssertionError("network")):
            r = self.get("wrong")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.headers["cache-control"], "no-store")
    def test_missing_token_configuration_fails_closed(self):
        with patch.dict(os.environ, {"AIOPS_PORTAL_READ_TOKEN": ""}):
            r = self.get()
        self.assertEqual(r.status_code, 503)
    def test_unconfigured_or_unapproved_url_no_network(self):
        for url in ("", "http://evil.invalid:3000", "http://127.0.0.1:3000@evil.invalid",
                    "http://127.0.0.1:3000/path", "http://localhost:5432",
                    "http://127.0.0.1:3000?x=1", "https://127.0.0.1:3000"):
            with self.subTest(url=url), patch.dict(os.environ, {"AIOPS_GRAFANA_READ_URL": url}), patch.object(
                    module.urllib.request, "build_opener", side_effect=AssertionError("network")):
                with self.assertRaises(ValueError):
                    module.read_grafana_health()
    def test_real_response_contract_never_attests_metrics(self):
        # Internal adapter contract only; not a browser tenant authorization.
        opener = Opener()
        with patch.object(module.urllib.request, "build_opener", return_value=opener):
            result = module.read_grafana_health()
        self.assertEqual(opener.called, 1)
        self.assertEqual(result["state"], "GRAFANA_HTTP_READY_UNATTESTED")
        self.assertEqual(result["grafana_observation"], "NOT_TESTED")
        self.assertFalse(result["tenant_acl_qualified"])
        self.assertFalse(result["live_remediation_authorized"])
        self.assertNotIn("version", result)
    def test_invalid_health_and_redirect_fail_closed(self):
        url = "http://127.0.0.1:3000/api/health"
        for response in (Response(url, {"database": "fail", "version": "11.6.0"}),
                         Response(url, {"database": "ok"}),
                         Response(url, content_type="text/html"),
                         Response("http://evil.invalid/api/health"),
                         Response(url, code=302)):
            with self.subTest(response=response), patch.object(
                    module.urllib.request, "build_opener", return_value=Opener(response)):
                with self.assertRaises(ValueError):
                    module.read_grafana_health()
    def test_oversize_and_duplicate_keys_rejected(self):
        url = "http://127.0.0.1:3000/api/health"
        for body in (b'{"database":"ok","database":"fail","version":"1"}',
                     b'{"database":"ok","version":"1","extra":"' + b'x'*5000 + b'"}',
                     b'{"database":"ok","version":NaN}'):
            response = Response(url)
            response.body = body
            with self.subTest(body=body[:30]), patch.object(
                    module.urllib.request, "build_opener", return_value=Opener(response)):
                with self.assertRaises(ValueError):
                    module.read_grafana_health()
    def test_shared_token_never_probes_grafana_without_tenant_acl(self):
        with patch.object(module, "read_grafana_health", side_effect=AssertionError("no upstream")) as read:
            response = self.get()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["reason"], "TENANT_ACL_NOT_QUALIFIED")
        self.assertEqual(response.json()["source_freshness"], "UNKNOWN")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])
        read.assert_not_called()
    def test_portal_mount_is_fail_closed_without_tenant_acl(self):
        with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": TOKEN,
                                     "AIOPS_PORTAL_READ_TOKEN": TOKEN}):
            from portal import main as portal_main
        self.assertIn("/api/noc/grafana-health", [r.path for r in portal_main.app.routes])
        # The current Portal deliberately exposes no unscoped Grafana button or
        # global probe. A shared viewer token is not a tenant ACL; the mounted
        # route must remain UNKNOWN/503 and must not contact Grafana.
        from fastapi.testclient import TestClient
        client = TestClient(portal_main.app)
        with patch.object(module, "read_grafana_health",
                          side_effect=AssertionError("unscoped Grafana probe")) as read:
            response = client.get("/api/noc/grafana-health",
                                  headers={"Authorization": "Bearer " + TOKEN})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["reason"], "TENANT_ACL_NOT_QUALIFIED")
        read.assert_not_called()

if __name__ == "__main__":
    unittest.main()
