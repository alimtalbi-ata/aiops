"""Independent source-authenticated Core actor/Run/event binding negative tests.

All upstreams are disposable in-process transports. No real IdP/GLPI/Core
network, no positive actor authorization, no migration or audit mutation.
"""
import json
import os
import unittest
from unittest.mock import patch

import requests
from core import actor_run_event_source as binding
from core import actor_resource_authz as actor

NOW = 1793510000
CONFIG = {"tenant_id": "TEN-A", "glpi_instance_id": "GLPI-A",
          "url": "https://core-proof.example.invalid/v1/run-event-readback",
          "issuer": "core-canonical-tenant-source",
          "client_id": "core-actor-source-reader",
          "client_secret": "s" * 48}
EXPECTED = {"tenant_id": "TEN-A", "run_id": "RUN-A", "incident_id": "INC-A",
            "glpi_instance_id": "GLPI-A", "ticket_id": "123",
            "glpi_entity_id": "7", "permission": "run:read",
            "nonce": "nonce_012345678901234567890123"}
CLAIMS = {"sub": "idp|alice", "exp": NOW + 120}
RECORD = {"run_id": "RUN-A", "incident_id": "INC-A", "glpi_entity_id": "7",
          "source_event_id": "EVT-SOURCE-A", "source_payload_hash": "a" * 64}
REQUEST = {k: EXPECTED[k] for k in binding._FIELDS if k in EXPECTED}
REQUEST.update(actor_subject="idp|alice", source_event_id="EVT-SOURCE-A",
               source_event_hash="a" * 64)
PROOF = {**REQUEST, "schema": binding.SCHEMA, "issuer": CONFIG["issuer"],
         "source_system": "CORE_CANONICAL_READBACK",
         "observed_at": NOW - 30, "known_at": NOW - 20,
         "expires_at": NOW + 60, "revoked": False, "verified": True}


class FakeResponse:
    def __init__(self, data=None, code=200, content_type="application/json"):
        self.status_code = code
        self.headers = {"Content-Type": content_type}
        self.data = json.dumps(PROOF if data is None else data).encode()
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def iter_content(self, chunk_size=4096):
        yield self.data


class FakeSession:
    def __init__(self, response, request=REQUEST):
        self.response = response
        self.request = request
        self.trust_env = True
        self.calls = []
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def post(self, url, **kwargs):
        assert self.trust_env is False
        assert url == CONFIG["url"]
        assert kwargs["auth"] == (CONFIG["client_id"], CONFIG["client_secret"])
        assert kwargs["json"] == self.request
        assert kwargs["allow_redirects"] is False
        assert kwargs["stream"] is True
        assert kwargs["verify"] is True
        assert kwargs["timeout"] == (2, 3)
        self.calls.append((url, kwargs))
        return self.response


class CoreActorSourceBindingTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "AIOPS_XREF_ACTOR_CORE_SOURCE_JSON": json.dumps([CONFIG])})
        self.env.start()
        self.addCleanup(self.env.stop)

    def read(self, proof=None, claims=None, expected=None, record=None,
             response=None):
        scope = RECORD if record is None else record
        request = {**REQUEST, "source_event_id": scope.get("source_event_id"),
                   "source_event_hash": scope.get("source_payload_hash")}
        session = FakeSession(response or FakeResponse(proof), request=request)
        with patch.object(requests, "Session", return_value=session):
            result = binding._source_run_event_preflight(
                CLAIMS if claims is None else claims,
                EXPECTED if expected is None else expected,
                RECORD if record is None else record, NOW)
        return result, session

    def test_independently_authenticated_exact_readback_is_only_preflight(self):
        passed, session = self.read()
        self.assertTrue(passed)
        self.assertEqual(len(session.calls), 1)
        self.assertEqual(json.loads(actor._reply().body)["decision"], "UNKNOWN")

    def test_all_resource_and_actor_fields_must_match(self):
        for key, changed in (("tenant_id", "TEN-B"), ("run_id", "RUN-B"),
                             ("incident_id", "INC-B"), ("glpi_instance_id", "GLPI-B"),
                             ("ticket_id", "999"), ("glpi_entity_id", "8"),
                             ("permission", "ticket:write"), ("actor_subject", "idp|bob"),
                             ("source_event_id", "EVT-OTHER"),
                             ("source_event_hash", "b" * 64)):
            with self.subTest(key=key):
                self.assertFalse(self.read(proof={**PROOF, key: changed})[0])

    def test_source_attestation_flags_cannot_override_exact_binding(self):
        for changes in ({"verified": "true"}, {"verified": False},
                        {"revoked": True}, {"revoked": "false"},
                        {"issuer": "foreign"}, {"schema": "v2"},
                        {"source_system": "HMAC_FIXTURE"},
                        {"observed_at": NOW + 1},
                        {"known_at": NOW + 1},
                        {"observed_at": NOW - 301},
                        {"known_at": NOW - 310},
                        {"expires_at": NOW},
                        {"expires_at": NOW + 301},
                        {"expires_at": NOW + 121},
                        {"extra": "forged"}):
            with self.subTest(changes=changes):
                self.assertFalse(self.read(proof={**PROOF, **changes})[0])

    def test_xref_record_tamper_rejected_before_network(self):
        for changed in ({"source_event_id": "EVT-B"},
                        {"source_payload_hash": "b" * 64},
                        {"source_payload_hash": "invalid"},
                        {"run_id": "RUN-B"},
                        {"incident_id": "INC-B"},
                        {"glpi_entity_id": "8"}):
            with self.subTest(changed=changed):
                result, session = self.read(record={**RECORD, **changed})
                if changed.get("source_event_id") == "EVT-B" or changed.get("source_payload_hash") == "b" * 64:
                    # A different valid source must be independently read back;
                    # old source reply is not accepted.
                    self.assertFalse(result)
                else:
                    self.assertFalse(result)
                if changed.get("source_payload_hash") == "invalid" or any(
                        k in changed for k in ("run_id", "incident_id", "glpi_entity_id")):
                    self.assertEqual(session.calls, [])

    def test_unconfigured_duplicate_or_unsafe_authority_has_no_network(self):
        configs = ("", "[]", json.dumps([CONFIG, CONFIG]),
                   json.dumps([{**CONFIG, "url": "http://core-proof.invalid/v1/read"}]),
                   json.dumps([{**CONFIG, "url": CONFIG["url"] + "?redirect=1"}]),
                   json.dumps([{**CONFIG, "client_secret": "short"}]))
        for raw in configs:
            with self.subTest(raw=raw):
                with patch.dict(os.environ, {"AIOPS_XREF_ACTOR_CORE_SOURCE_JSON": raw}):
                    with patch.object(requests, "Session") as network:
                        self.assertFalse(binding._source_run_event_preflight(
                            CLAIMS, EXPECTED, RECORD, NOW))
                        network.assert_not_called()

    def test_redirect_html_oversize_and_upstream_failure_are_unknown(self):
        for response in (FakeResponse(code=302),
                         FakeResponse(content_type="text/html"),
                         FakeResponse({"junk": "a" * 18000}),
                         FakeResponse(code=503)):
            with self.subTest(code=response.status_code):
                self.assertFalse(self.read(response=response)[0])

    def test_missing_claim_or_expiry_never_passes(self):
        for claims in ({"sub": "idp|alice", "exp": NOW - 1},
                       {"sub": "idp|alice", "exp": True},
                       {"sub": "", "exp": NOW + 60},
                       {"exp": NOW + 60}):
            with self.subTest(claims=claims):
                self.assertFalse(self.read(claims=claims)[0])


if __name__ == "__main__":
    unittest.main()
