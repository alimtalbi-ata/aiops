"""Run in candidate image: python3 -m unittest discover -s /app/explorer_tests -v."""
import os
import unittest
from unittest.mock import patch
from io import BytesIO
from types import SimpleNamespace
from fastapi import HTTPException
from portal import explorer_api as e

class SecurityTests(unittest.TestCase):
    def test_rejects_non_select(self):
        for sql in ("DELETE FROM tickets", "UPDATE t SET x=1", "WITH x AS (DELETE FROM t RETURNING *) SELECT * FROM x",
                    "SELECT 1; DROP TABLE x", "SELECT 1 -- comment", "SELECT /* comment */ 1"):
            with self.subTest(sql=sql):
                with self.assertRaises(HTTPException):
                    e._safe_query(sql)

    def test_rejects_common_side_effect_selects(self):
        for sql in ("SELECT SLEEP(30)", "SELECT pg_sleep(30)",
                    "SELECT pg_advisory_lock(1)", "SELECT load_file('/etc/passwd')",
                    "SELECT name INTO OUTFILE '/tmp/x' FROM t",
                    "SELECT dblink('dbname=x','SELECT 1')",
                    "SELECT lo_export(123,'/tmp/x')"):
            with self.subTest(sql=sql):
                with self.assertRaises(HTTPException):
                    e._safe_query(sql)

    def test_network_denies_unparseable_peer(self):
        with patch.dict(os.environ, {"EXPLORER_ALLOWED_CIDRS": "10.79.94.0/24"}):
            with self.assertRaises(HTTPException):
                e._deny_untrusted(SimpleNamespace(client=SimpleNamespace(host="unknown")))

    def test_rejects_invalid_network_configuration(self):
        with patch.dict(os.environ, {"EXPLORER_ALLOWED_CIDRS": "10.79.94.xxx"}):
            with self.assertRaises(HTTPException):
                e._deny_untrusted(SimpleNamespace(client=SimpleNamespace(host="10.79.94.20")))

    def test_accepts_select(self):
        self.assertEqual(e._safe_query("SELECT 1"), "SELECT 1")

    def test_requires_allowlist(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(HTTPException) as raised:
                e._deny_untrusted(SimpleNamespace(client=SimpleNamespace(host="10.0.0.3")))
            self.assertEqual(raised.exception.status_code, 503)

    def test_network_denies_outside_cidr(self):
        with patch.dict(os.environ, {"EXPLORER_ALLOWED_CIDRS": "10.1.0.0/24"}):
            with self.assertRaises(HTTPException) as raised:
                e._deny_untrusted(SimpleNamespace(client=SimpleNamespace(host="10.2.0.2")))
            self.assertEqual(raised.exception.status_code, 403)

    def test_network_allows_inside_cidr(self):
        with patch.dict(os.environ, {"EXPLORER_ALLOWED_CIDRS": "10.1.0.0/24"}):
            e._deny_untrusted(SimpleNamespace(client=SimpleNamespace(host="10.1.0.2")))

    def test_rejects_unconfigured_db(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(HTTPException):
                e._source("core")

    def test_no_url_credentials(self):
        with patch.dict(os.environ, {"EXPLORER_PROMETHEUS_URL": "http://user:password@prometheus:9090"}):
            with self.assertRaises(HTTPException):
                e._upstream("prometheus")

    def test_temporal_html_health_response(self):
        class Response:
            status = 200
            headers = {"Content-Type": "text/html"}
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, size): return b"<html>Temporal UI</html>"
        with patch.dict(os.environ, {"EXPLORER_TEMPORAL_UI_URL": "http://temporal-ui:8080"}):
            with patch.object(e, "urlopen", return_value=Response()):
                result = e._read("temporal", "/")
        self.assertTrue(result["reachable"])
        self.assertEqual(result["http_status"], 200)
        self.assertIsNone(result["details"])

    def test_n8n_json_health_response(self):
        class Response:
            status = 200
            headers = {"Content-Type": "application/json"}
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, size): return b'{"status":"ok"}'
        with patch.dict(os.environ, {"EXPLORER_N8N_URL": "http://n8n:5678"}):
            with patch.object(e, "urlopen", return_value=Response()):
                result = e._read("n8n", "/healthz")
        self.assertEqual(result["details"], {"status": "ok"})

    def test_n8n_listing_requires_server_key(self):
        with patch.dict(os.environ, {"EXPLORER_N8N_URL": "http://n8n:5678"}, clear=True):
            with self.assertRaises(HTTPException) as raised:
                e._read("n8n", "/api/v1/executions")
            self.assertEqual(raised.exception.status_code, 503)

    def test_n8n_listing_sends_server_key(self):
        class Response:
            status = 200
            headers = {"Content-Type": "application/json"}
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, size): return b'{"data":[]}'
        with patch.dict(os.environ, {"EXPLORER_N8N_URL": "http://n8n:5678",
                                     "EXPLORER_N8N_API_KEY": "isolated-test-key"}):
            with patch.object(e, "urlopen", return_value=Response()) as opener:
                result = e._read("n8n", "/api/v1/executions", {"limit": "50"})
        self.assertEqual(result["data"], [])
        self.assertEqual(opener.call_args.args[0].get_header("X-n8n-api-key"), "isolated-test-key")

    def test_read_only_router(self):
        paths=[r.path for r in e.api.routes]
        self.assertNotIn("/api/explorer/execute", paths)
        self.assertIn("/api/explorer/databases/{source}/query", paths)

if __name__ == "__main__":
    unittest.main()
