"""No identity or ACL authorization may be inferred from OIDC config."""
import unittest
from scripts.acme_oidc_integration_preflight import assess_oidc_integration

VALID = {"issuer": "https://identity.example.org/realms/acme",
         "client_id": "aiops-portal", "audience": "aiops-workbench",
         "tenant_acl_source": "server-tenant-directory",
         "run_acl_source": "core-authoritative-run-acl"}


class OidcPreflightTests(unittest.TestCase):
    def test_complete_config_still_denies(self):
        result = assess_oidc_integration(VALID)
        self.assertEqual(result["status"], "NO_GO")
        self.assertEqual(result["reason"], "OIDC_AUTHORITY_NOT_RUNTIME_VERIFIED")
        self.assertFalse(result["browser_evidence_enabled"])
        self.assertFalse(result["exact_run_acl_runtime_verified"])

    def test_missing_and_extra_fields_fail(self):
        for value in ({}, {**VALID, "token": "secret"}, None):
            with self.subTest(value=value):
                self.assertEqual(assess_oidc_integration(value)["status"], "NO_GO")

    def test_untrusted_issuers_fail(self):
        for issuer in ("http://identity.example.org", "https://localhost",
                       "https://user:pass@identity.example.org",
                       "https://identity.example.org?token=abc",
                       "https://identity.example.org:8443", "https://[::1]",
                       "https://10.1.2.3/realms/acme",
                       "https://192.168.1.2", "https://identity.example.org\\\\@evil.example",
                       "https://identity.example.org/path\\nnext",
                       "https://identity..example.org"):
            with self.subTest(issuer=issuer):
                self.assertEqual(
                    assess_oidc_integration({**VALID, "issuer": issuer})["reason"],
                    "OIDC_ISSUER_NOT_QUALIFIED")

    def test_browser_supplied_acl_is_not_authority(self):
        for field in ("tenant_acl_source", "run_acl_source"):
            with self.subTest(field=field):
                self.assertEqual(
                    assess_oidc_integration({**VALID, field: "client_claims"})["reason"],
                    "ACL_AUTHORITY_NOT_QUALIFIED")


if __name__ == "__main__":
    unittest.main()
