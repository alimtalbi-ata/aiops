"""Offline GLPI REST session GET-only lifecycle and fail-closed checks."""
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from shared.glpi_session_readonly import make_glpi_session_ticket_get, GLPISessionReadBlocked


class Response:
    status = 200
    headers = {"Content-Type": "application/json"}
    def __init__(self, payload):
        self.stream = io.BytesIO(json.dumps(payload).encode())
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, n):
        return self.stream.read(n)


class Opener:
    def __init__(self, calls, fail_ticket=False):
        self.calls = calls
        self.fail_ticket = fail_ticket
    def open(self, request, timeout):
        path = request.full_url.split("/apirest.php/")[-1]
        self.calls.append((path, request))
        if path == "initSession":
            assert request.get_header("Authorization") == "user_token user-secret"
            assert request.get_header("App-token") == "app-secret"
            return Response({"session_token": "session-secret"})
        assert request.get_header("Session-token") == "session-secret"
        assert request.get_header("App-token") == "app-secret"
        if path == "Ticket/201":
            if self.fail_ticket:
                raise OSError("upstream offline")
            return Response({"id": 201, "entities_id": 7})
        if path == "killSession":
            return Response({})
        raise AssertionError(path)


class SessionTests(unittest.TestCase):
    def make(self, calls, fail_ticket=False, **overrides):
        args = dict(glpi_base_url="https://glpi.internal",
                    get_app_token=lambda **kwargs: "app-secret",
                    get_user_token=lambda **kwargs: "user-secret")
        args.update(overrides)
        with patch("shared.glpi_session_readonly.build_opener",
                   return_value=Opener(calls, fail_ticket)):
            return make_glpi_session_ticket_get(**args)

    def read(self, fn):
        return fn(url="https://glpi.internal/Ticket/201", actor="operator",
                  tenant_id="tenant-a", ticket_id="201", glpi_instance_id="ci")

    def test_session_ticket_cleanup_and_distinct_headers(self):
        calls = []
        self.assertEqual(self.read(self.make(calls))["id"], 201)
        self.assertEqual([name for name, _ in calls],
                         ["initSession", "Ticket/201", "killSession"])
        self.assertEqual({r.get_method() for _, r in calls}, {"GET"})

    def test_reader_contract_without_ticket_keyword(self):
        calls = []
        fn = self.make(calls)
        payload = fn(url="https://glpi.internal/Ticket/201", actor="operator",
                     tenant_id="tenant-a", glpi_instance_id="ci")
        self.assertEqual(payload["id"], 201)
        self.assertEqual([name for name, _ in calls],
                         ["initSession", "Ticket/201", "killSession"])

    def test_explicit_ticket_mismatch_rejected_before_credentials(self):
        calls = []
        fn = self.make(calls)
        with self.assertRaises(GLPISessionReadBlocked):
            fn(url="https://glpi.internal/Ticket/201", actor="operator",
               tenant_id="tenant-a", ticket_id="202", glpi_instance_id="ci")
        self.assertEqual(calls, [])

    def test_ticket_failure_still_closes_session(self):
        calls = []
        with self.assertRaises(GLPISessionReadBlocked):
            self.read(self.make(calls, fail_ticket=True))
        self.assertEqual([name for name, _ in calls],
                         ["initSession", "Ticket/201", "killSession"])

    def test_untrusted_ticket_path_never_opens_session(self):
        calls = []
        fn = self.make(calls)
        with self.assertRaises(GLPISessionReadBlocked):
            fn(url="https://glpi.internal/Ticket/202", actor="operator",
               tenant_id="tenant-a", ticket_id="201", glpi_instance_id="ci")
        self.assertEqual(calls, [])

    def test_missing_credential_dependency_rejected(self):
        with self.assertRaises(ValueError):
            self.make([], get_user_token=None)


if __name__ == "__main__":
    unittest.main()
