"""Fail-closed validation of offline NOC browser qualification manifests.

No network, browser, production service, or filesystem writes are performed.
A manifest documents evidence; passing validation does NOT prove a browser ran.
"""
import hashlib
import json
import unittest

VIEWPORTS = (320, 768, 1440)
REQUIRED = ("source_sha", "mode", "policy", "viewport", "screenshot_sha256",
            "screenshot_path", "external_requests", "horizontal_overflow",
            "unknown_visible", "deny_live_visible", "browser_executed")


def validate_manifest(records, source_sha):
    """Return explicit contract violations; never infer success from missing fields."""
    errors = []
    if not isinstance(source_sha, str) or len(source_sha) != 40 or any(
        c not in "0123456789abcdef" for c in source_sha
    ):
        return ["invalid source SHA"]
    if not isinstance(records, list) or len(records) != 3:
        return ["expected exactly three viewport records"]
    widths = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"record {index}: not an object")
            continue
        missing = set(REQUIRED) - set(record)
        if missing:
            errors.append(f"record {index}: missing {','.join(sorted(missing))}")
            continue
        width = record["viewport"]
        widths.append(width)
        if type(width) is not int or width not in VIEWPORTS:
            errors.append(f"record {index}: invalid viewport")
        if record["source_sha"] != source_sha:
            errors.append(f"record {index}: source SHA mismatch")
        if record["mode"] not in ("DEMO", "SIMULATION"):
            errors.append(f"record {index}: mode not isolated")
        if record["policy"] != "DENY_LIVE":
            errors.append(f"record {index}: policy not fail-closed")
        if record["browser_executed"] is not True:
            errors.append(f"record {index}: browser execution unverified")
        if record["unknown_visible"] is not True or record["deny_live_visible"] is not True:
            errors.append(f"record {index}: safety label not observed")
        if record["horizontal_overflow"] is not False:
            errors.append(f"record {index}: overflow unverified")
        if record["external_requests"] != 0 or type(record["external_requests"]) is not int:
            errors.append(f"record {index}: external request count invalid")
        digest = record["screenshot_sha256"]
        if not isinstance(digest, str) or len(digest) != 64 or any(
            c not in "0123456789abcdef" for c in digest
        ):
            errors.append(f"record {index}: invalid screenshot digest")
        path = record["screenshot_path"]
        if not isinstance(path, str) or not path.startswith("artifacts/noc/") or ".." in path:
            errors.append(f"record {index}: invalid screenshot path")
    if sorted(widths) != list(VIEWPORTS):
        errors.append("viewport set incomplete or duplicated")
    return errors


class ManifestContractTests(unittest.TestCase):
    SHA = "a" * 40

    def record(self, width):
        return dict(source_sha=self.SHA, mode="SIMULATION", policy="DENY_LIVE",
                    viewport=width, screenshot_sha256="b" * 64,
                    screenshot_path=f"artifacts/noc/{width}.png",
                    external_requests=0, horizontal_overflow=False,
                    unknown_visible=True, deny_live_visible=True,
                    browser_executed=True)

    def test_complete_manifest_contract(self):
        self.assertEqual(validate_manifest([self.record(w) for w in VIEWPORTS], self.SHA), [])

    def test_missing_proof_fails_closed(self):
        records = [self.record(w) for w in VIEWPORTS]
        records[0]["browser_executed"] = False
        records[1]["screenshot_sha256"] = "UNKNOWN"
        records[2]["policy"] = "ALLOW"
        self.assertGreaterEqual(len(validate_manifest(records, self.SHA)), 3)

    def test_duplicate_viewport_rejected(self):
        self.assertIn("viewport set incomplete or duplicated",
                      validate_manifest([self.record(320), self.record(320), self.record(1440)], self.SHA))

    def test_external_network_and_missing_fields_rejected(self):
        records = [self.record(w) for w in VIEWPORTS]
        records[0]["external_requests"] = 1
        del records[1]["unknown_visible"]
        self.assertTrue(validate_manifest(records, self.SHA))


if __name__ == "__main__":
    unittest.main()
