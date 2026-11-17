"""Fail-closed CI-local browser evidence bundle verifier.

Bind the successful browser receipt to the actual PNG manifest and source SHA.
Neither artifact is a cryptographic signature or deployed-host attestation.
"""
import hashlib
import json
import re
from pathlib import Path

from scripts.acme_isolated_png_integrity import verify_isolated_png_manifest

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
FALSE_KEYS = (
    "deployed_sha_attested", "runtime_e2e_verified", "viewer_acl_verified",
    "remediation_effect_verified", "learning_verified",
    "autonomous_execution_allowed",
)


def verify_browser_bundle(*, captures_dir: Path, receipt_path: Path,
                          expected_source_sha: str) -> dict:
    if not isinstance(expected_source_sha, str) or not SHA_RE.fullmatch(expected_source_sha):
        raise ValueError("invalid expected source SHA")
    captures_dir, receipt_path = Path(captures_dir), Path(receipt_path)
    png_result = verify_isolated_png_manifest(captures_dir)
    if png_result["status"] != "BYTES_CONSISTENT_CI_LOOPBACK_ONLY":
        raise ValueError("PNG integrity failed")
    receipt_bytes = receipt_path.read_bytes()
    if len(receipt_bytes) > 16384:
        raise ValueError("oversized receipt")
    receipt = json.loads(receipt_bytes)
    if not isinstance(receipt, dict):
        raise ValueError("invalid receipt")
    if receipt.get("schema") != "aiops.acme-isolated-browser-receipt.v1":
        raise ValueError("wrong receipt schema")
    if receipt.get("source_sha") != expected_source_sha:
        raise ValueError("receipt source SHA mismatch")
    if receipt.get("status") != "PASS_CI_LOOPBACK_BROWSER_ONLY":
        raise ValueError("wrong receipt status")
    if receipt.get("browser") != "CHROMIUM" or receipt.get("viewports") != [375, 1440]:
        raise ValueError("browser/viewport mismatch")
    if receipt.get("navigation") != ["/demo-studio", "/acme-workbench"]:
        raise ValueError("navigation mismatch")
    if receipt.get("external_requests") != "BLOCKED_BY_BROWSER_TEST":
        raise ValueError("external requests not denied")
    if receipt.get("upstream_services") != "DISABLED_BY_TEST_APP":
        raise ValueError("upstream services not disabled")
    if any(receipt.get(key) is not False for key in FALSE_KEYS):
        raise ValueError("forged runtime authority")
    manifest_bytes = (captures_dir / "manifest.json").read_bytes()
    if len(manifest_bytes) > 16384:
        raise ValueError("oversized manifest")
    return {
        "schema": "aiops.acme-isolated-browser-bundle-check.v1",
        "status": "CI_LOCAL_BUNDLE_CONSISTENT_ONLY",
        "source_sha": expected_source_sha,
        "png_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "receipt_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
        "runtime_e2e_verified": False,
        "deployed_sha_attested": False,
        "viewer_acl_verified": False,
        "autonomous_execution_allowed": False,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--captures-dir", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--expected-source-sha", required=True)
    args = parser.parse_args()
    print(json.dumps(verify_browser_bundle(
        captures_dir=args.captures_dir, receipt_path=args.receipt,
        expected_source_sha=args.expected_source_sha), sort_keys=True))
