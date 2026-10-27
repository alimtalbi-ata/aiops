import unittest
from demo.star_legacy_playwright_audit import audit_legacy_manifest

class LegacyPlaywrightAuditTests(unittest.TestCase):
    def test_grafana_login_is_not_verified(self):
        d={"version":"UCP-F20.13-DEMO-MULTISTACK","browser":"Chromium","automation":"Playwright",
           "captures":[{"name":"10-grafana","service":"Grafana","status":"PASS",
                        "url":"http://127.0.0.1:3000/login","file":"10-grafana.png"}]}
        r=audit_legacy_manifest(d)
        self.assertEqual(r["entries"][0]["application"],"grafana")
        self.assertFalse(r["entries"][0]["business_state_verified"])
        self.assertFalse(r["entries"][0]["eligible_for_star_proof"])
        self.assertNotIn("url",r["entries"][0])
    def test_declared_sha_is_never_verified(self):
        d={"browser":"Chromium","automation":"Playwright","results":[
            {"name":"overview","status":"PASS","sha256":"a"*64}]}
        r=audit_legacy_manifest(d)
        self.assertTrue(r["entries"][0]["sha256_declared"])
        self.assertFalse(r["entries"][0]["integrity_verified"])
    def test_rejects_malformed_name(self):
        d={"browser":"Chromium","automation":"Playwright",
           "captures":[{"name":"../escape","status":"PASS"}]}
        with self.assertRaises(ValueError): audit_legacy_manifest(d)
    def test_rejects_missing_browser_identity(self):
        with self.assertRaises(ValueError):
            audit_legacy_manifest({"captures":[]})
if __name__=="__main__":unittest.main()
