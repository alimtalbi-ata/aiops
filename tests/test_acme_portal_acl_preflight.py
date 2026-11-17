import unittest
from pathlib import Path
from scripts.acme_portal_acl_preflight import assess_portal_acl


class PortalAclPreflightTests(unittest.TestCase):
    def test_real_portal_is_not_acl_attested(self):
        source = Path("app/portal/main.py").read_text(encoding="utf-8")
        result = assess_portal_acl(source)
        self.assertEqual(result["status"], "NO_GO")
        self.assertEqual(result["reason"], "VIEWER_TENANT_RUN_ACL_NOT_ATTESTED")
        self.assertIn("/demo-studio", result["source_get_routes"])
        self.assertFalse(result["internal_bearer_is_viewer_acl"])

    def test_source_route_is_not_authorization(self):
        source = '@app.get("/api/acme/worker/{attempt_id}")\ndef read(): return {"tenant_id": "ACME-TEST"}'
        self.assertEqual(assess_portal_acl(source)["status"], "NO_GO")

    def test_asserted_attestation_cannot_override(self):
        result = assess_portal_acl('@app.get("/ok")\ndef ok(): return True',
                                   tenant_authority_attested=True)
        self.assertEqual(result["status"], "NO_GO")
        self.assertTrue(result["attestation_claim_ignored"])

    def test_malformed_source_fails_closed(self):
        self.assertEqual(assess_portal_acl("def bad(")["reason"],
                         "PORTAL_SOURCE_INVALID")


if __name__ == "__main__":
    unittest.main()
