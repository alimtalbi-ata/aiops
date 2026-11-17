import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from scripts.acme_isolated_png_integrity import verify_isolated_png_manifest

PNG = bytes.fromhex("89504e470d0a1a0a") + b"test-png-placeholder" * 4

class IsolatedPngIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = {
            "schema": "aiops.acme-isolated-browser-png-manifest.v1",
            "authority": "CI_LOOPBACK_TEST_APP_NOT_DEPLOYED",
            "status": "PASS_ISOLATED_BROWSER_ONLY",
            **{key: False for key in ("deployed_sha_attested", "runtime_e2e_verified",
                                      "viewer_acl_verified", "remediation_effect_verified",
                                      "learning_verified")},
            "captures": [],
        }
        for width in (375, 1440):
            filename = f"workbench-{width}.png"
            (self.root / filename).write_bytes(PNG)
            self.manifest["captures"].append({
                "viewport_width": width, "file": filename,
                "sha256": hashlib.sha256(PNG).hexdigest(), "size_bytes": len(PNG),
                "browser_status": "PASS_ISOLATED_BROWSER_ONLY"})
        self.save()

    def save(self):
        (self.root / "manifest.json").write_text(json.dumps(self.manifest))

    def test_bytes_consistent_not_runtime_attestation(self):
        result = verify_isolated_png_manifest(self.root)
        self.assertEqual(result["status"], "BYTES_CONSISTENT_CI_LOOPBACK_ONLY")
        self.assertIs(result["runtime_e2e_verified"], False)

    def test_mutated_png_rejected(self):
        (self.root / "workbench-375.png").write_bytes(PNG + b"tampered")
        with self.assertRaises(ValueError):
            verify_isolated_png_manifest(self.root)

    def test_forged_runtime_claim_rejected(self):
        self.manifest["viewer_acl_verified"] = True
        self.save()
        with self.assertRaises(ValueError):
            verify_isolated_png_manifest(self.root)

    def test_path_traversal_identity_rejected(self):
        self.manifest["captures"][0]["file"] = "../secret.png"
        self.save()
        with self.assertRaises(ValueError):
            verify_isolated_png_manifest(self.root)

    def test_wrong_viewport_rejected(self):
        self.manifest["captures"][1]["viewport_width"] = 375
        self.save()
        with self.assertRaises(ValueError):
            verify_isolated_png_manifest(self.root)
