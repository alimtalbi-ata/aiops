"""Offline transport tests: never perform a network request."""
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import ProxyHandler
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from shared.glpi_http_json_transport import ReadTransportBlocked, make_json_get


class Response:
    status = 200
    headers = {"Content-Type": "application/json"}
    def __init__(self, body=b'{"id":201}'):
        self.body = io.BytesIO(body)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, n):
        return self.body.read(n)


class FakeOpener:
    def __init__(self, response):
        self.response = response
        self.calls = []
    def open(self, request, timeout):
        self.calls.append((request, timeout))
        return self.response


class TransportTests(unittest.TestCase):
    def create(self, response=None, token="server-only-token", max_bytes=262144):
        opener = FakeOpener(response or Response())
        with patch("shared.glpi_http_json_transport.build_opener", return_value=opener):
            get = make_json_get(get_token=lambda **kwargs: token,
                                allowed_origin="https://core.internal",
                                max_bytes=max_bytes)
        return get, opener

    def test_authenticated_get_only(self):
        get, opener = self.create()
        self.assertEqual(get(url="https://core.internal/api/runs/RUN-1",
                             actor="operator", tenant_id="tenant-a"), {"id": 201})
        request, timeout = opener.calls[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.get_header("Authorization"), "Bearer server-only-token")
        self.assertEqual(timeout, 3.0)

    def test_invalid_credentials_and_scope_do_not_open(self):
        for token in ("", "bad\\nheader", None):
            get, opener = self.create(token=token)
            with self.assertRaises(ReadTransportBlocked):
                get(url="https://core.internal/api/runs/RUN-1",
                    actor="operator", tenant_id="tenant-a")
            self.assertEqual(opener.calls, [])
        get, opener = self.create()
        with self.assertRaises(ReadTransportBlocked):
            get(url="http://core.internal", actor="operator", tenant_id="tenant-a")
        self.assertEqual(opener.calls, [])

    def test_non_json_and_oversized_fail_closed(self):
        for response in (Response(b'[]'), Response(b'{bad')):
            get, _ = self.create(response=response)
            with self.assertRaises(ReadTransportBlocked):
                get(url="https://core.internal", actor="operator",
                    tenant_id="tenant-a")
        get, _ = self.create(response=Response(b'x' * 2048), max_bytes=1024)
        with self.assertRaises(ReadTransportBlocked):
            get(url="https://core.internal", actor="operator",
                tenant_id="tenant-a")

    def test_credentials_never_sent_to_other_origin(self):
        get, opener = self.create()
        for url in ("https://evil.internal/api/runs/RUN-1",
                    "https://core.internal.evil.invalid/api/runs/RUN-1",
                    "https://core.internal:444/api/runs/RUN-1",
                    "https://core.internal@evil.internal/api/runs/RUN-1",
                    "https://core.internal:invalid/api/runs/RUN-1"):
            with self.subTest(url=url), self.assertRaises(ReadTransportBlocked):
                get(url=url, actor="operator", tenant_id="tenant-a")
        self.assertEqual(opener.calls, [])

    def test_environment_proxy_is_explicitly_disabled(self):
        handlers = []
        def capture(*args):
            handlers.extend(args)
            return FakeOpener(Response())
        with patch("shared.glpi_http_json_transport.build_opener", side_effect=capture):
            make_json_get(get_token=lambda **kwargs: "server-only-token",
                          allowed_origin="https://core.internal")
        proxies = [handler for handler in handlers if isinstance(handler, ProxyHandler)]
        self.assertEqual(len(proxies), 1)
        self.assertEqual(proxies[0].proxies, {})

    def test_no_redirect_handler_installed(self):
        from shared.glpi_http_json_transport import _NoRedirect
        self.assertIsNone(_NoRedirect().redirect_request(None, None, 302,
                                                          "redirect", {}, "https://evil"))


if __name__ == "__main__":
    unittest.main()
