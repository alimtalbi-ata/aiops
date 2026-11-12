"""Native GLPI human actor source preflight: synthetic transports, zero network."""
import json
import os
import unittest
from unittest.mock import patch

from core import actor_native_authority as native

NOW = 1793506558
KEY = "ci-only-separate-mapping-authority-key-00000001"
CFG = {"tenant_id": "TEN-A", "glpi_instance_id": "GLPI-A",
       "mapping_url": "https://identity.example.invalid/v1/glpi-subject-map",
       "mapping_client_id": "mapping-client-identity",
       "mapping_client_secret": "mapping-secret-only-for-disposable-ci-0001",
       "mapping_mac_key": KEY,
       "glpi_origin": "https://glpi.example.invalid",
       "glpi_app_token": "glpi-ci-app-token-123456789"}
CLAIMS = {"sub": "idp|alice", "iss": "https://issuer.example.invalid",
          "jti": "JTI_disposable_0000000000000001", "glpi_user_id": 47,
          "exp": NOW + 180}
EXPECTED = {"tenant_id": "TEN-A", "glpi_instance_id": "GLPI-A",
            "ticket_id": "123", "glpi_entity_id": "7",
            "nonce": "NONCE_disposable_000000000001"}


class Response:
    status_code = 200
    headers = {"Content-Type": "application/json"}
    def __init__(self, data):
        self.data = data
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def iter_content(self, chunk_size=4096):
        yield json.dumps(self.data).encode("utf-8")


class Session:
    def __init__(self, mapping, overrides=None):
        self.trust_env = True
        self.mapping = mapping
        self.overrides = overrides or {}
        self.calls = []
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def _check(self, url, kwargs):
        assert self.trust_env is False
        assert kwargs["verify"] is True and kwargs["stream"] is True
        assert kwargs["allow_redirects"] is False
        assert kwargs["timeout"] == (2, 3)
        self.calls.append(url)
    def post(self, url, **kwargs):
        self._check(url, kwargs)
        assert url == CFG["mapping_url"]
        assert kwargs["auth"] == (CFG["mapping_client_id"], CFG["mapping_client_secret"])
        assert kwargs["json"]["subject"] == CLAIMS["sub"]
        return Response(self.overrides.get("mapping", self.mapping))
    def get(self, url, **kwargs):
        self._check(url, kwargs)
        assert url.startswith(CFG["glpi_origin"] + "/apirest.php/")
        assert kwargs["headers"]["Session-Token"] == self.mapping["glpi_session_token"]
        path = url.split("/apirest.php/", 1)[1]
        data = {"getFullSession": {"session": {"glpiID": 47,
                    "glpiactiveprofile": {"id": 2}, "glpiactiveentities": [7]}},
                "User/47": {"id": 47, "is_active": 1}, "Profile/2": {"id": 2, "ticket": 1},
                "Entity/7": {"id": 7},
                "Ticket/123": {"id": 123, "entities_id": 7}}[path]
        return Response(self.overrides.get(path, data))


def mapping():
    m = {"schema_version": "aiops.core-oidc-glpi-actor-binding.v1",
         "subject": CLAIMS["sub"], "issuer": CLAIMS["iss"],
         "tenant_id": EXPECTED["tenant_id"],
         "glpi_instance_id": EXPECTED["glpi_instance_id"],
         "glpi_user_id": 47, "jti": CLAIMS["jti"],
         "nonce": EXPECTED["nonce"], "source_event_id": "IDMAP-001",
         "issued_at": NOW - 10, "expires_at": NOW + 100,
         "revoked": False,
         "glpi_session_token": "human-actor-session-token-disposable-0001"}
    m["binding_mac"] = native._mapping_mac(m, KEY)
    return m


class NativeActorRightsTests(unittest.TestCase):
    def setUp(self):
        self.config = patch.dict(os.environ, {"AIOPS_XREF_ACTOR_NATIVE_SOURCES_JSON": json.dumps([CFG])})
        self.config.start()
        self.addCleanup(self.config.stop)
        self.m = mapping()
        self.s = Session(self.m)
        self.session = patch.object(native.requests, "Session", return_value=self.s)
        self.session.start()
        self.addCleanup(self.session.stop)
    def check(self, claims=None, expected=None):
        return native._native_glpi_preflight(claims or CLAIMS, expected or EXPECTED, NOW)
    def test_distinct_authenticated_sources_and_exact_native_actor_reads(self):
        # Only a *source-contract* preflight; never a business ALLOW.
        self.assertTrue(self.check())
        self.assertEqual(len(self.s.calls), 6)
        self.assertEqual(self.s.calls[0], CFG["mapping_url"])
        self.assertTrue(self.s.calls[-1].endswith("/Ticket/123"))
    def test_missing_source_configuration_fails_closed(self):
        with patch.dict(os.environ, {"AIOPS_XREF_ACTOR_NATIVE_SOURCES_JSON": ""}):
            self.assertFalse(self.check())
        self.assertEqual(self.s.calls, [])
    def test_untrusted_verified_true_is_not_a_mapping_signature(self):
        self.s.overrides["mapping"] = {**self.m, "verified": True}
        self.assertFalse(self.check())
    def test_mapping_signature_tamper(self):
        self.s.overrides["mapping"] = {**self.m, "glpi_user_id": 48}
        self.assertFalse(self.check())
    def test_mapping_subject_swap_even_with_valid_mac(self):
        m = {**self.m, "subject": "idp|mallory"}
        m["binding_mac"] = native._mapping_mac(m, KEY)
        self.s.overrides["mapping"] = m
        self.assertFalse(self.check())
    def test_mapping_foreign_tenant_even_with_valid_mac(self):
        m = {**self.m, "tenant_id": "TEN-B"}
        m["binding_mac"] = native._mapping_mac(m, KEY)
        self.s.overrides["mapping"] = m
        self.assertFalse(self.check())
    def test_mapping_revocation_even_with_valid_mac(self):
        m = {**self.m, "revoked": True}
        m["binding_mac"] = native._mapping_mac(m, KEY)
        self.s.overrides["mapping"] = m
        self.assertFalse(self.check())
    def test_mapping_expiry_even_with_valid_mac(self):
        m = {**self.m, "expires_at": NOW - 1}
        m["binding_mac"] = native._mapping_mac(m, KEY)
        self.s.overrides["mapping"] = m
        self.assertFalse(self.check())
    def test_native_session_user_swap(self):
        self.s.overrides["getFullSession"] = {"session": {"glpiID": 48,
            "glpiactiveprofile": {"id": 2}, "glpiactiveentities": [7]}}
        self.assertFalse(self.check())
    def test_native_entity_acl_missing(self):
        self.s.overrides["getFullSession"] = {"session": {"glpiID": 47,
            "glpiactiveprofile": {"id": 2}, "glpiactiveentities": [8]}}
        self.assertFalse(self.check())
    def test_native_profile_mismatch(self):
        self.s.overrides["Profile/2"] = {"id": 3, "ticket": 1}
        self.assertFalse(self.check())
    def test_profile_id_without_ticket_read_is_not_permission(self):
        for rights in (None, 0, 1024, True, "1"):
            with self.subTest(rights=rights):
                self.s.overrides["Profile/2"] = {"id": 2, "ticket": rights}
                self.assertFalse(self.check())
    def test_inactive_or_untyped_glpi_user_is_not_human_authority(self):
        for active in (0, None, True, "1"):
            with self.subTest(active=active):
                self.s.overrides["User/47"] = {"id": 47, "is_active": active}
                self.assertFalse(self.check())
    def test_native_ticket_entity_mismatch(self):
        self.s.overrides["Ticket/123"] = {"id": 123, "entities_id": 8}
        self.assertFalse(self.check())
    def test_native_ticket_id_mismatch(self):
        self.s.overrides["Ticket/123"] = {"id": 124, "entities_id": 7}
        self.assertFalse(self.check())
    def test_foreign_expected_entity(self):
        self.assertFalse(self.check(expected={**EXPECTED, "glpi_entity_id": "8"}))
    def test_no_issuer_claim(self):
        self.assertFalse(self.check(claims={**CLAIMS, "iss": None}))
    def test_no_cross_origin_identity_mirror(self):
        cfg = {**CFG, "mapping_url": "https://glpi.example.invalid/v1/mapping"}
        with patch.dict(os.environ, {"AIOPS_XREF_ACTOR_NATIVE_SOURCES_JSON": json.dumps([cfg])}):
            self.assertFalse(self.check())
        self.assertEqual(self.s.calls, [])
    def test_no_http_or_redirected_url(self):
        cfg = {**CFG, "mapping_url": "http://identity.example.invalid/v1/mapping"}
        with patch.dict(os.environ, {"AIOPS_XREF_ACTOR_NATIVE_SOURCES_JSON": json.dumps([cfg])}):
            self.assertFalse(self.check())
        self.assertEqual(self.s.calls, [])


if __name__ == "__main__":
    unittest.main()
