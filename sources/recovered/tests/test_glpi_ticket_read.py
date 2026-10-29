"""Offline GLPI contract tests; NOT a real GLPI integration qualification."""
import io
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from shared.glpi_ticket_read import GLPIUnverified, _configuration, read_ticket

ENV = {
    "AIOPS_GLPI_API_BASE_URL": "https://glpi.example.invalid/apirest.php",
    "AIOPS_GLPI_APP_TOKEN": "a" * 32,
    "AIOPS_GLPI_SESSION_TOKEN": "b" * 32,
    "AIOPS_GLPI_ENTITY_ID": "7",
}
TICKET = {"id": 123, "entities_id": 7, "status": 2,
          "name": "private title MUST NOT leak", "content": "private content MUST NOT leak",
          "date_mod": "2026-10-27 23:01:00"}


class Response:
    def __init__(self, raw, url, *, status=200, ctype="application/json", length=None):
        self._io = io.BytesIO(raw)
        self._url = url
        self._status = status
        self.headers = {"Content-Type": ctype}
        if length is not None:
            self.headers["Content-Length"] = str(length)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._io.close()

    def geturl(self):
        return self._url

    def getcode(self):
        return self._status

    def read(self, size):
        return self._io.read(size)


def transport_for(ticket=TICKET, *, url_override=None, status=200,
                  ctype="application/json", raw=None, length=None):
    payload = json.dumps(ticket).encode() if raw is None else raw

    def transport(request, *, timeout):
        assert request.get_method() == "GET"
        assert timeout == 3
        assert request.get_header("App-token") == ENV["AIOPS_GLPI_APP_TOKEN"]
        assert request.get_header("Session-token") == ENV["AIOPS_GLPI_SESSION_TOKEN"]
        assert request.full_url == ENV["AIOPS_GLPI_API_BASE_URL"] + "/Ticket/123"
        return Response(payload, url_override or request.full_url, status=status,
                        ctype=ctype, length=length)
    return transport


class GLPITicketReadTests(unittest.TestCase):
    def test_verified_api_observation_is_still_uncorrelated(self):
        result = read_ticket("123", env=ENV, transport=transport_for(),
                             now=datetime(2026, 10, 28, tzinfo=timezone.utc))
        self.assertEqual(result["state"], "OBSERVED_UNCORRELATED")
        self.assertEqual(result["ticket_id"], "123")
        self.assertEqual(result["entity_id"], 7)
        self.assertEqual(result["read_at_utc"], "2026-10-28T00:00:00Z")
        self.assertEqual(result["correlation_state"], "UNKNOWN")
        self.assertIsNone(result["run_id"])
        self.assertIsNone(result["incident_id"])
        self.assertFalse(result["runtime_attested"])
        self.assertFalse(result["live_remediation_authorized"])
        self.assertNotIn("private title", str(result))
        self.assertNotIn("private content", str(result))

    def test_live_mode_rejected_before_any_network(self):
        for mode in ("LIVE", "live", "", None):
            with self.subTest(mode=mode), self.assertRaises(GLPIUnverified):
                read_ticket(123, env=ENV, mode=mode,
                            transport=lambda *_a, **_k: self.fail("LIVE network used"))

    def test_simulation_mode_still_unqualified(self):
        result = read_ticket(123, env=ENV, mode="SIMULATION",
                             transport=transport_for())
        self.assertEqual(result["correlation_state"], "UNKNOWN")
        self.assertFalse(result["production_qualified"])

    def test_invalid_ids_fail_before_transport(self):
        for value in ("SIM-GLPI-123", "123/../../users", "0", "-1", "12.3", True,
                      0, -1, 2147483648, None, "１２３"):
            with self.subTest(value=value):
                with self.assertRaises(GLPIUnverified):
                    read_ticket(value, env=ENV, transport=lambda *_a, **_k: self.fail("network used"))

    def test_https_required_outside_isolated_ci(self):
        with self.assertRaises(GLPIUnverified):
            _configuration({**ENV, "AIOPS_GLPI_API_BASE_URL": "http://glpi.example.invalid/apirest.php"})
        with self.assertRaises(GLPIUnverified):
            _configuration({**ENV, "CI": "true", "AIOPS_GLPI_API_BASE_URL": "http://example.invalid/apirest.php"})
        _configuration({**ENV, "CI": "true", "AIOPS_GLPI_API_BASE_URL": "http://aiops2-glpi/apirest.php"})

    def test_invalid_origin_and_path_refused(self):
        for base in ("https://user:pass@glpi.example.invalid/apirest.php",
                     "https://glpi.example.invalid/apirest.php?x=1",
                     "https://glpi.example.invalid/other",
                     "https://glpi.example.invalid/apirest.php#frag",
                     "https://glpi.example.invalid:bad/apirest.php",
                     "file:///apirest.php"):
            with self.subTest(base=base), self.assertRaises(GLPIUnverified):
                _configuration({**ENV, "AIOPS_GLPI_API_BASE_URL": base})

    def test_missing_tokens_and_entity_fail_closed(self):
        for key in ("AIOPS_GLPI_APP_TOKEN", "AIOPS_GLPI_SESSION_TOKEN", "AIOPS_GLPI_ENTITY_ID"):
            with self.subTest(key=key), self.assertRaises(GLPIUnverified):
                _configuration({k: v for k, v in ENV.items() if k != key})

    def test_mismatched_ticket_id_and_tenant_rejected(self):
        for changes in ({"id": 124}, {"entities_id": 8}, {"id": True},
                        {"entities_id": False}, {"status": 0}, {"status": True}):
            with self.subTest(changes=changes), self.assertRaises(GLPIUnverified):
                read_ticket(123, env=ENV, transport=transport_for({**TICKET, **changes}))

    def test_redirect_and_non_200_rejected(self):
        for changes in ({"url_override": "https://other.invalid/Ticket/123"}, {"status": 302}):
            with self.subTest(changes=changes), self.assertRaises(GLPIUnverified):
                read_ticket(123, env=ENV, transport=transport_for(**changes))

    def test_wrong_content_type_and_length_rejected(self):
        for changes in ({"ctype": "text/html"}, {"length": 999999}, {"length": 1}):
            with self.subTest(changes=changes), self.assertRaises(GLPIUnverified):
                read_ticket(123, env=ENV, transport=transport_for(**changes))

    def test_oversized_body_rejected(self):
        with self.assertRaises(GLPIUnverified):
            read_ticket(123, env=ENV, transport=transport_for(raw=b"x" * (65536 + 1)))

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(GLPIUnverified):
            read_ticket(123, env=ENV, transport=transport_for(
                raw=b'{"id":123,"id":123,"entities_id":7,"status":2}'))

    def test_malformed_json_and_nan_rejected(self):
        for raw in (b'{"id":', b'{"id":123,"entities_id":7,"status":NaN}', b'[]'):
            with self.subTest(raw=raw), self.assertRaises(GLPIUnverified):
                read_ticket(123, env=ENV, transport=transport_for(raw=raw))

    def test_bad_timestamp_rejected(self):
        with self.assertRaises(GLPIUnverified):
            read_ticket(123, env=ENV, transport=transport_for(
                {**TICKET, "date_mod": "tomorrow"}))

    def test_network_failure_does_not_leak_credentials(self):
        def fail(request, *, timeout):
            raise OSError("secret=" + ENV["AIOPS_GLPI_SESSION_TOKEN"])
        with self.assertRaises(GLPIUnverified) as caught:
            read_ticket(123, env=ENV, transport=fail)
        self.assertNotIn(ENV["AIOPS_GLPI_SESSION_TOKEN"], str(caught.exception))

    def test_no_ambient_proxy_and_redirect_handler(self):
        import urllib.request
        with patch("shared.glpi_ticket_read.urllib.request.build_opener",
                   wraps=urllib.request.build_opener) as build:
            read_ticket(123, env=ENV, transport=transport_for())
        handlers = build.call_args.args
        self.assertIsInstance(handlers[0], urllib.request.ProxyHandler)
        self.assertEqual(handlers[0].proxies, {})
        self.assertEqual(type(handlers[1]).__name__, "_NoRedirect")


if __name__ == "__main__":
    unittest.main()
