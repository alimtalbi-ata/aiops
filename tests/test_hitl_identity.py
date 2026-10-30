import os
import unittest
from unittest.mock import patch

from shared.hitl_identity import (
    IdentityError,
    authorize_critical_approvals,
    authorize_sudo_request,
    issue_simulated_assertion,
    simulator_ready,
    verify_assertion,
    oidc_configured,
    require_live_assertion,
)


class HitlIdentityTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "AIOPS_HITL_IDENTITY_MODE": "SIMULATOR",
            "AIOPS_HITL_SIMULATOR_ENABLED": "true",
            "AIOPS_HITL_SIMULATOR_SIGNING_KEY": "test-only-signing-key-32-bytes-minimum!!",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_simulator_assertion_is_explicitly_simulated(self):
        token, claims = issue_simulated_assertion("security.sara")
        verified = verify_assertion(token, allow_simulated=True)
        self.assertTrue(verified["simulated"])
        self.assertEqual(verified["sub"], "sim:security.sara")
        self.assertIn("security_admin", claims["roles"])

    def test_simulator_assertion_cannot_authorize_live(self):
        token, _ = issue_simulated_assertion("security.sara")
        with self.assertRaisesRegex(IdentityError, "simulated_identity_forbidden_for_live"):
            verify_assertion(token, allow_simulated=False)

    def test_signature_tampering_is_rejected(self):
        token, _ = issue_simulated_assertion("operator.alex")
        with self.assertRaises(IdentityError):
            verify_assertion(token + "x", allow_simulated=True)

    def test_disabled_simulator_fails_closed(self):
        with patch.dict(os.environ, {"AIOPS_HITL_SIMULATOR_ENABLED": "false"}):
            with self.assertRaisesRegex(IdentityError, "identity_simulator_disabled"):
                issue_simulated_assertion("operator.alex")

    def test_simulator_readiness_requires_signing_key(self):
        self.assertTrue(simulator_ready())
        with patch.dict(os.environ, {"AIOPS_HITL_SIMULATOR_SIGNING_KEY": ""}):
            self.assertFalse(simulator_ready())

    def test_critical_approval_requires_two_distinct_subjects_and_roles(self):
        self.assertFalse(authorize_critical_approvals([
            {"subject_id": "sim:sara", "role": "security_admin"},
            {"subject_id": "sim:sara", "role": "incident_commander"},
        ]))
        self.assertTrue(authorize_critical_approvals([
            {"subject_id": "ad:sara-guid", "role": "security_admin"},
            {"subject_id": "ad:ian-guid", "role": "incident_commander"},
        ]))

    def test_live_identity_fails_closed_when_oidc_is_not_configured(self):
        with patch.dict(os.environ, {
            "AIOPS_HITL_OIDC_ISSUER": "",
            "AIOPS_HITL_OIDC_AUDIENCE": "",
            "AIOPS_HITL_OIDC_JWKS_URL": "",
            "AIOPS_HITL_OIDC_GROUP_ROLE_MAP": "",
        }):
            self.assertFalse(oidc_configured())
            with self.assertRaisesRegex(IdentityError, "oidc_identity_provider_not_configured"):
                require_live_assertion("not-a-token")

    def test_oidc_configuration_requires_https_and_group_role_map(self):
        config = {
            "AIOPS_HITL_OIDC_ISSUER": "https://id.example.invalid/tenant",
            "AIOPS_HITL_OIDC_AUDIENCE": "aiops2-hitl",
            "AIOPS_HITL_OIDC_JWKS_URL": "https://id.example.invalid/tenant/keys",
            "AIOPS_HITL_OIDC_GROUP_ROLE_MAP": '{"00ab-group-sid":["security_admin"]}',
        }
        with patch.dict(os.environ, config):
            self.assertTrue(oidc_configured())
        config["AIOPS_HITL_OIDC_JWKS_URL"] = "http://id.example.invalid/keys"
        with patch.dict(os.environ, config):
            self.assertFalse(oidc_configured())

    def test_sudo_catalog_is_precheck_only(self):
        allowed = authorize_sudo_request(
            action_id="linux.collect_diagnostics",
            subject_roles=["operator"], host_id="rhel01",
            allowed_hosts={"rhel01"}, simulated=False,
        )
        self.assertTrue(allowed["allowed"])
        self.assertFalse(allowed["execution_allowed"])
        denied = authorize_sudo_request(
            action_id="bash.anything", subject_roles=["platform_admin"],
            host_id="rhel01", allowed_hosts={"rhel01"}, simulated=False,
        )
        self.assertFalse(denied["allowed"])


if __name__ == "__main__":
    unittest.main()
