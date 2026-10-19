import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("AIOPS_INTERNAL_TOKEN", "test-internal-token-not-a-real-secret")

from shared.http import _request, get_json, post_json


class SharedHttpRetryTests(unittest.TestCase):
    @patch("shared.http.time.sleep")
    @patch("shared.http.requests.request")
    def test_get_retries_transient_failures(self, request, sleep):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"status": "ok"}
        request.side_effect = [TimeoutError("first"), TimeoutError("second"), response]
        result = get_json("http://core:810", "/api/dashboard")
        self.assertEqual(result, {"status": "ok"})
        self.assertEqual(request.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    @patch("shared.http.time.sleep")
    @patch("shared.http.requests.request")
    def test_post_is_not_retried_automatically(self, request, sleep):
        request.side_effect = TimeoutError("response lost after possible commit")
        with self.assertRaises(TimeoutError):
            post_json("http://core:810", "/api/incidents", {"external_id": "test"})
        self.assertEqual(request.call_count, 1)
        sleep.assert_not_called()

    @patch("shared.http.time.sleep")
    @patch("shared.http.requests.request")
    def test_explicit_retry_override_is_respected(self, request, sleep):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"accepted": True}
        request.side_effect = [TimeoutError("transient"), response]
        result = _request("POST", "http://core:810", "/api/runs", {}, retries=1)
        self.assertEqual(result, {"accepted": True})
        self.assertEqual(request.call_count, 2)
        sleep.assert_called_once()

    @patch("shared.http.requests.request")
    def test_internal_bearer_header_is_sent(self, request):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {}
        request.return_value = response
        get_json("http://core:810", "/health")
        kwargs = request.call_args.kwargs
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-internal-token-not-a-real-secret")
        self.assertEqual(kwargs["headers"]["X-AIOPS-Request"], "internal")


if __name__ == "__main__":
    unittest.main()
