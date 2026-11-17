import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.acme_isolated_browser_bundle import verify_browser_bundle

SHA = "a" * 40
PNG = bytes.fromhex("89504e470d0a1a0a") + b"test-png-placeholder" * 4


class BrowserBundleTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        manifest = {
            "schema": "aiops.acme-isolated-browser-png-manifest.v1",
            "authority": "CI_LOOPBACK_TEST_APP_NOT_DEPLOYED",
            "status": "PASS_ISOLATED_BROWSER_ONLY",
            **{k: False for k in ("deployed_sha_attested", "runtime_e2e_verified",
                                  "viewer_acl_verified", "remediation_effect_verified",
                                  "learning_verified")},
            "captures": [],
        }
        for width in (375, 1440):
            filename = f"workbench-{width}.png"
            (self.root / filename).write_bytes(PNG)
            manifest["captures"].append({
                "viewport_width": width, "file": filename,
                "sha256": hashlib.sha256(PNG).hexdigest(),
                "size_bytes": len(PNG), "browser_status": "PASS_ISOLATED_BROWSER_ONLY"})
        (self.root / "manifest.json").write_text(json.dumps(manifest))
        self.receipt = {
            "schema": "aiops.acme-isolated-browser-receipt.v1",
            "source_sha": SHA, "status": "PASS_CI_LOOPBACK_BROWSER_ONLY",
            "browser": "CHROMIUM", "viewports": [375, 1440],
            "navigation": ["/demo-studio", "/acme-workbench"],
            "external_requests": "BLOCKED_BY_BROWSER_TEST",
            "upstream_services": "DISABLED_BY_TEST_APP",
            **{k: False for k in ("deployed_sha_attested", "runtime_e2e_verified",
                                  "viewer_acl_verified", "remediation_effect_verified",
                                  "learning_verified", "autonomous_execution_allowed")},
        }
        self.save()

    def save(self):
        (self.root / "receipt.json").write_text(json.dumps(self.receipt))

    def verify(self, sha=SHA):
        return verify_browser_bundle(captures_dir=self.root,
                                     receipt_path=self.root / "receipt.json",
                                     expected_source_sha=sha)

    def test_valid_bundle_stays_local_only(self):
        result = self.verify()
        self.assertEqual(result["status"], "CI_LOCAL_BUNDLE_CONSISTENT_ONLY")
        self.assertIs(result["runtime_e2e_verified"], False)
        self.assertEqual(len(result["receipt_sha256"]), 64)

    def test_wrong_source_sha_rejected(self):
        with self.assertRaises(ValueError):
            self.verify("b" * 40)

    def test_forged_runtime_attestation_rejected(self):
        self.receipt["deployed_sha_attested"] = True
        self.save()
        with self.assertRaises(ValueError):
            self.verify()

    def test_forged_external_network_access_rejected(self):
        self.receipt["external_requests"] = "ALLOWED"
        self.save()
        with self.assertRaises(ValueError):
            self.verify()

    def test_mutated_png_rejected(self):
        (self.root / "workbench-1440.png").write_bytes(PNG + b"tamper")
        with self.assertRaises(ValueError):
            self.verify()

    def test_wrong_browser_rejected(self):
        self.receipt["browser"] = "FIREFOX"
        self.save()
        with self.assertRaises(ValueError):
            self.verify()

    def test_oversized_receipt_rejected(self):
        (self.root / "receipt.json").write_bytes(b" " * 16385)
        with self.assertRaises(ValueError):
            self.verify()

    def test_oversized_manifest_rejected(self):
        manifest_path = self.root / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["padding"] = "x" * 17000
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            self.verify()

    def test_missing_runtime_false_key_rejected(self):
        self.receipt.pop("learning_verified")
        self.save()
        with self.assertRaises(ValueError):
            self.verify()

    def test_wrong_navigation_rejected(self):
        self.receipt["navigation"] = ["/demo-studio", "/api/demo"]
        self.save()
        with self.assertRaises(ValueError):
            self.verify()
