"""Full offline signed-xref -> ACL -> authenticated GET -> readback contract."""
import hashlib
import hmac
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from shared.glpi_server_readonly_assembly import make_server_glpi_readonly_qualifier
from shared.glpi_hmac_qualification import GLPIHmacQualificationBlocked
from shared.glpi_xref_hmac_verifier import canonical_event_bytes


class Response:
    status = 200
    headers = {"Content-Type": "application/json"}
    def __init__(self, data):
        self.data = io.BytesIO(json.dumps(data).encode())
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, size):
        return self.data.read(size)


class Opener:
    def __init__(self, requests, core_incident="INC-DEMO-12345678"):
        self.requests = requests
        self.core_incident = core_incident
    def open(self, request, timeout):
        self.requests.append(request)
        if request.full_url == "https://core.internal/api/runs/RUN-12345678":
            return Response({"run": {"run_id": "RUN-12345678",
                                     "incident_id": self.core_incident,
                                     "mode": "DEMO"}})
        if request.full_url == "https://glpi.internal/Ticket/201":
            return Response({"id": 201, "entities_id": 7})
        raise AssertionError("unexpected URL")


class GLPISessionOpener:
    def __init__(self, requests):
        self.requests = requests
    def open(self, request, timeout):
        self.requests.append(request)
        path = request.full_url.split("/apirest.php/")[-1]
        if path == "initSession":
            assert request.get_header("Authorization") == "user_token glpi-user-credential"
            assert request.get_header("App-token") == "glpi-app-credential"
            return Response({"session_token": "session-only-credential"})
        assert request.get_header("Session-token") == "session-only-credential"
        assert request.get_header("App-token") == "glpi-app-credential"
        if path == "Ticket/201":
            return Response({"id": 201, "entities_id": 7})
        if path == "killSession":
            return Response({})
        raise AssertionError(path)


class FullChainTests(unittest.TestCase):
    def setUp(self):
        self.secret = b"k" * 32
        self.calls = []
        self.requests = []
        self.claims = dict(aud="aiops-glpi-copilot-xref",
                           iss="aiops-core-xref-signer",
                           actor="operator", tenant_id="tenant-a",
                           ticket_id="201", glpi_instance_id="ci",
                           glpi_entity_id="7", incident_id="INC-DEMO-12345678",
                           run_id="RUN-12345678", association_state="ACTIVE",
                           association_count=1, iat=1000, exp=1100,
                           nonce="nonce123456789012")

    def make(self, core_incident="INC-DEMO-12345678", read_allowed=True,
             nonce_allowed=True, actor_allowed=True):
        def fetch(**kwargs):
            self.calls.append("fetch")
            return {"claims": dict(self.claims),
                    "signature": hmac.new(self.secret,
                                          canonical_event_bytes(self.claims),
                                          hashlib.sha256).hexdigest()}
        def acl(**kwargs):
            self.calls.append("xref_acl")
            return actor_allowed
        def nonce(**kwargs):
            self.calls.append("nonce")
            return nonce_allowed
        def read_acl(**kwargs):
            self.calls.append("read_acl:" + kwargs["resource"])
            return (read_allowed.get(kwargs["resource"], False)
                    if isinstance(read_allowed, dict) else read_allowed)
        def core_token(**kwargs):
            self.calls.append("core_token")
            return "core-only-credential"
        def glpi_app_token(**kwargs):
            self.calls.append("glpi_app_token")
            return "glpi-app-credential"
        def glpi_user_token(**kwargs):
            self.calls.append("glpi_user_token")
            return "glpi-user-credential"
        openers = [Opener(self.requests, core_incident),
                   GLPISessionOpener(self.requests)]
        with patch("shared.glpi_http_json_transport.build_opener",
                   return_value=openers[0]), patch(
                   "shared.glpi_session_readonly.build_opener",
                   return_value=openers[1]):
            return make_server_glpi_readonly_qualifier(
                secret=self.secret, fetch_signed_event=fetch,
                consume_nonce=nonce, authorize_actor=acl,
                authorize_read=read_acl, core_token=core_token,
                glpi_app_token=glpi_app_token, glpi_user_token=glpi_user_token,
                core_base_url="https://core.internal",
                glpi_base_url="https://glpi.internal", clock=lambda: 1050)

    def test_full_readonly_chain_with_real_transport_contract(self):
        result = self.make()(actor="operator", tenant_id="tenant-a",
                             ticket_id="201")
        self.assertEqual(result["status"], "READ_ONLY_XREF_COMPARISON")
        self.assertTrue(result["raw_readbacks_match"])
        self.assertFalse(result["copilot_context_authorized"])
        self.assertFalse(result["hitl_proposal_authorized"])
        self.assertFalse(result["execution_allowed"])
        self.assertEqual(len(self.requests), 4)
        self.assertTrue(all(r.get_method() == "GET" for r in self.requests))
        self.assertEqual(self.requests[0].get_header("Authorization"),
                         "Bearer core-only-credential")
        self.assertEqual(self.requests[1].get_header("Authorization"),
                         "user_token glpi-user-credential")
        self.assertEqual(self.requests[2].get_header("Session-token"),
                         "session-only-credential")
        self.assertEqual(self.requests[3].full_url,
                         "https://glpi.internal/apirest.php/killSession")
        self.assertEqual(self.calls, ["fetch", "xref_acl", "nonce",
                                      "read_acl:core_run", "core_token",
                                      "read_acl:glpi_ticket", "glpi_app_token", "glpi_user_token"])

    def test_replayed_nonce_never_reads_core_or_glpi(self):
        with self.assertRaises(GLPIHmacQualificationBlocked):
            self.make(nonce_allowed=False)(
                actor="operator", tenant_id="tenant-a", ticket_id="201")
        self.assertEqual(self.requests, [])
        self.assertNotIn("core_token", self.calls)
        self.assertNotIn("glpi_app_token", self.calls)
        self.assertNotIn("read_acl:core_run", self.calls)

    def test_denied_signed_xref_actor_never_reads_upstream(self):
        with self.assertRaises(GLPIHmacQualificationBlocked):
            self.make(actor_allowed=False)(
                actor="operator", tenant_id="tenant-a", ticket_id="201")
        self.assertEqual(self.requests, [])
        self.assertNotIn("core_token", self.calls)
        self.assertNotIn("glpi_user_token", self.calls)

    def test_denied_core_acl_never_fetches_upstream(self):
        with self.assertRaises(GLPIHmacQualificationBlocked):
            self.make(read_allowed=False)(
                actor="operator", tenant_id="tenant-a", ticket_id="201")
        self.assertEqual(self.requests, [])
        self.assertNotIn("core_token", self.calls)
        self.assertNotIn("glpi_app_token", self.calls)
        self.assertNotIn("glpi_user_token", self.calls)

    def test_denied_glpi_acl_never_opens_glpi_session(self):
        with self.assertRaises(GLPIHmacQualificationBlocked):
            self.make(read_allowed={"core_run": True, "glpi_ticket": False})(
                actor="operator", tenant_id="tenant-a", ticket_id="201")
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.requests[0].full_url,
                         "https://core.internal/api/runs/RUN-12345678")
        self.assertIn("read_acl:glpi_ticket", self.calls)
        self.assertNotIn("glpi_app_token", self.calls)
        self.assertNotIn("glpi_user_token", self.calls)

    def test_mismatched_core_identity_fails_closed(self):
        with self.assertRaises(GLPIHmacQualificationBlocked):
            self.make(core_incident="INC-OTHER-12345678")(
                actor="operator", tenant_id="tenant-a", ticket_id="201")
        self.assertEqual(len(self.requests), 4)


if __name__ == "__main__":
    unittest.main()
