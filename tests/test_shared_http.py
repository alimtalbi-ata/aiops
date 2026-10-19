import os
import pathlib
import sys
import unittest
from unittest.mock import patch
import requests

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
os.environ.setdefault("AIOPS_INTERNAL_TOKEN", "unit-test-only-token")
from shared import http as client

class SharedHttpRetryTests(unittest.TestCase):
    def test_get_retries_transient_connection_failure(self):
        ok = type("Response", (), {"raise_for_status": lambda self: None, "json": lambda self: {"ok": True}})()
        with patch.object(client.requests, "request", side_effect=[requests.ConnectionError("transient"), ok]) as mocked:
            result = client.get_json("http://service", "/health", retries=1)
        self.assertEqual(result, {"ok": True})
        self.assertEqual(mocked.call_count, 2)

    def test_post_does_not_retry_ambiguous_timeout_by_default(self):
        with patch.object(client.requests, "request", side_effect=requests.Timeout("ambiguous")) as mocked:
            with self.assertRaises(requests.Timeout):
                client.post_json("http://service", "/mutate", {"idempotency_key": "test"})
        self.assertEqual(mocked.call_count, 1)

    def test_client_error_is_not_retried(self):
        response = requests.Response()
        response.status_code = 401
        with patch.object(client.requests, "request", return_value=response) as mocked:
            with self.assertRaises(requests.HTTPError):
                client.get_json("http://service", "/protected", retries=3)
        self.assertEqual(mocked.call_count, 1)

    def test_server_error_can_be_retried_for_get(self):
        bad = requests.Response()
        bad.status_code = 503
        ok = type("Response", (), {"raise_for_status": lambda self: None, "json": lambda self: {"ready": True}})()
        with patch.object(client.requests, "request", side_effect=[bad, ok]) as mocked:
            result = client.get_json("http://service", "/ready", retries=1)
        self.assertEqual(result, {"ready": True})
        self.assertEqual(mocked.call_count, 2)

if __name__ == "__main__":
    unittest.main()
