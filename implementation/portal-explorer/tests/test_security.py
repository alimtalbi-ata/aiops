"""Run in candidate image: python3 -m unittest discover -s /app/explorer_tests -v."""
import os
import unittest
from unittest.mock import patch
from io import BytesIO
from urllib.error import HTTPError
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

    def test_database_browser_routes_registered(self):
        routes = {(r.path, method) for r in e.api.routes for method in (r.methods or [])}
        for path, method in (
            ("/api/explorer/databases/{source}/tables", "GET"),
            ("/api/explorer/databases/{source}/columns", "GET"),
            ("/api/explorer/databases/{source}/preview", "GET"),
            ("/api/explorer/databases/{source}/query", "POST"),
        ):
            with self.subTest(path=path):
                self.assertIn((path, method), routes)

    def test_n8n_read_routes_only(self):
        self.assertEqual(e.PATHS["n8n"]["workflows"], "/api/v1/workflows")
        self.assertEqual(e.PATHS["n8n"]["executions"], "/api/v1/executions")
        self.assertFalse(any("execute" in key or "activate" in key for key in e.PATHS["n8n"]))

    def test_n8n_rejected_key_is_not_service_outage(self):
        with patch.dict(os.environ, {"EXPLORER_N8N_URL": "http://n8n:5678",
                                     "EXPLORER_N8N_API_KEY": "invalid-test-key"}):
            with patch.object(e, "urlopen", side_effect=HTTPError(
                    "http://n8n:5678/api/v1/workflows", 401, "Unauthorized", {}, None)):
                with self.assertRaises(HTTPException) as raised:
                    e._read("n8n", "/api/v1/workflows")
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(raised.exception.detail, "n8n_read_api_credentials_rejected")

    def test_n8n_api_key_is_never_in_error(self):
        with patch.dict(os.environ, {"EXPLORER_N8N_URL": "http://n8n:5678",
                                     "EXPLORER_N8N_API_KEY": "secret-check-123"}):
            with patch.object(e, "urlopen", side_effect=HTTPError(
                    "http://n8n:5678/api/v1/executions", 403, "Forbidden", {}, None)):
                with self.assertRaises(HTTPException) as raised:
                    e._read("n8n", "/api/v1/executions")
        self.assertNotIn("secret-check-123", str(raised.exception.detail))

    def test_temporal_namespace_route_is_read_only(self):
        routes = {(r.path, method) for r in e.api.routes for method in (r.methods or [])}
        self.assertIn(("/api/explorer/temporal/namespaces/{namespace}/workflows", "GET"), routes)
        self.assertEqual(e.PATHS["temporal"]["namespaces"], "/api/v1/namespaces")
        self.assertNotIn("start", e.PATHS["temporal"])

    def test_temporal_namespace_rejects_path_injection(self):
        from unittest.mock import Mock
        with patch.object(e, "_check"):
            with self.assertRaises(HTTPException) as raised:
                e.temporal_workflows("../default", Mock())
        self.assertEqual(raised.exception.status_code, 400)

    def test_temporal_workflow_pagesize_limited(self):
        from unittest.mock import Mock
        with patch.object(e, "_check"):
            with self.assertRaises(HTTPException) as raised:
                e.temporal_workflows("default", Mock(), 1000)
        self.assertEqual(raised.exception.status_code, 400)

    def test_temporal_workflow_uses_confirmed_path(self):
        from unittest.mock import Mock
        with patch.object(e, "_check"):
            with patch.object(e, "_read", return_value={"executions": []}) as reader:
                result = e.temporal_workflows("default", Mock(), 25)
        self.assertEqual(result, {"executions": [], "returned": 0, "upstream_returned": 0, "truncated": False})
        reader.assert_called_once_with("temporal", "/api/v1/namespaces/default/workflows", {"pagesize": 25})

    def test_temporal_caps_upstream_workflows(self):
        from unittest.mock import Mock
        payload = {"executions": [{"execution": {"workflowId": str(i)}} for i in range(22)]}
        with patch.object(e, "_check"):
            with patch.object(e, "_read", return_value=payload):
                result = e.temporal_workflows("default", Mock(), 1)
        self.assertEqual(len(result["executions"]), 1)
        self.assertEqual(result["upstream_returned"], 22)
        self.assertTrue(result["truncated"])

    def test_temporal_rejects_unexpected_workflow_payload(self):
        from unittest.mock import Mock
        with patch.object(e, "_check"):
            with patch.object(e, "_read", return_value={"unexpected": []}):
                with self.assertRaises(HTTPException) as raised:
                    e.temporal_workflows("default", Mock(), 25)
        self.assertEqual(raised.exception.status_code, 502)

    def test_cmdb_rejects_unknown_type_without_glpi_call(self):
        with patch.object(e, "urlopen") as opener:
            with self.assertRaises(HTTPException) as raised:
                e._glpi_inventory("Ticket")
        self.assertEqual(raised.exception.status_code, 404)
        opener.assert_not_called()

    def test_cmdb_rejects_invalid_pagination(self):
        for offset, limit in ((-1, 25), (0, 101), (100001, 1)):
            with self.subTest(offset=offset, limit=limit):
                with self.assertRaises(HTTPException):
                    e._glpi_inventory("Computer", offset=offset, limit=limit)

    def test_cmdb_requires_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(HTTPException) as raised:
                e._glpi_inventory("Computer")
        self.assertEqual(raised.exception.status_code, 503)

    def test_cmdb_routes_are_get_only(self):
        routes = {r.path: r.methods for r in e.api.routes}
        for path in ("/api/explorer/cmdb/inventory/{kind}",
                     "/api/explorer/cmdb/inventory/{kind}/{item_id}"):
            self.assertEqual(routes[path], {"GET"})

    def test_core_collections_are_read_only(self):
        from unittest.mock import Mock
        self.assertEqual(set(e.PATHS["core"]), {"dashboard", "incidents", "runs", "scenarios"})
        with patch.object(e, "_check"):
            with patch.object(e, "_read", return_value={"items": [{"id": i} for i in range(8)]}):
                result = e.core_collection("incidents", Mock(), 3)
        self.assertEqual(result["returned"], 3)
        self.assertEqual(result["upstream_returned"], 8)
        self.assertTrue(result["truncated"])

    def test_core_collection_rejects_unknown_or_invalid_limit(self):
        from unittest.mock import Mock
        with patch.object(e, "_check"):
            for name, limit in (("execute", 10), ("runs", 201)):
                with self.subTest(name=name, limit=limit):
                    with self.assertRaises(HTTPException):
                        e.core_collection(name, Mock(), limit)

    def test_core_rejects_unexpected_response(self):
        from unittest.mock import Mock
        with patch.object(e, "_check"):
            with patch.object(e, "_read", return_value={"other": []}):
                with self.assertRaises(HTTPException) as raised:
                    e.core_collection("runs", Mock())
        self.assertEqual(raised.exception.status_code, 502)

    def test_tempo_search_empty_results(self):
        from unittest.mock import Mock
        with patch.object(e, "_check"):
            with patch.object(e, "_read", return_value={"traces": [], "metrics": {"completedJobs": 1}}) as reader:
                result = e.tempo_search(Mock(), 60, 20)
        self.assertEqual(result["traces"], [])
        self.assertEqual(result["returned"], 0)
        self.assertFalse(result["truncated"])
        self.assertEqual(reader.call_args.args[:2], ("tempo", "/api/search"))

    def test_tempo_search_rejects_invalid_window(self):
        from unittest.mock import Mock
        with patch.object(e, "_check"):
            with self.assertRaises(HTTPException) as raised:
                e.tempo_search(Mock(), 10080, 20)
        self.assertEqual(raised.exception.status_code, 400)

    def test_tempo_search_caps_results(self):
        from unittest.mock import Mock
        with patch.object(e, "_check"):
            with patch.object(e, "_read", return_value={"traces": [{}] * 22}):
                result = e.tempo_search(Mock(), 60, 5)
        self.assertEqual(result["returned"], 5)
        self.assertTrue(result["truncated"])

    def test_read_only_router(self):
        paths=[r.path for r in e.api.routes]
        self.assertNotIn("/api/explorer/execute", paths)
        self.assertIn("/api/explorer/databases/{source}/query", paths)

if __name__ == "__main__":
    unittest.main()
