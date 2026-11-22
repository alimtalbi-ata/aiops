"""Verify actual CI-local Chromium PNG bytes against the isolated manifest.

This does not attest a deployed host, runtime ACL or any service effect.
"""
import hashlib
import json
from pathlib import Path

PNG_MAGIC = bytes.fromhex("89504e470d0a1a0a")
REQUIRED_FALSE = ("deployed_sha_attested", "runtime_e2e_verified",
                  "viewer_acl_verified", "remediation_effect_verified",
                  "learning_verified")


def verify_isolated_png_manifest(directory: Path) -> dict:
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be object")
    if manifest.get("schema") != "aiops.acme-isolated-browser-png-manifest.v1":
        raise ValueError("wrong schema")
    if manifest.get("authority") != "CI_LOOPBACK_TEST_APP_NOT_DEPLOYED":
        raise ValueError("wrong authority")
    if manifest.get("status") != "PASS_ISOLATED_BROWSER_ONLY":
        raise ValueError("wrong status")
    if any(manifest.get(key) is not False for key in REQUIRED_FALSE):
        raise ValueError("runtime claim forbidden")
    captures = manifest.get("captures")
    if not isinstance(captures, list) or len(captures) != 2:
        raise ValueError("expected two captures")
    for capture, width in zip(captures, (375, 1440)):
        if not isinstance(capture, dict) or capture.get("viewport_width") != width:
            raise ValueError("unexpected viewport")
        filename = f"workbench-{width}.png"
        if capture.get("file") != filename or capture.get("browser_status") != "PASS_ISOLATED_BROWSER_ONLY":
            raise ValueError("unexpected capture identity")
        data = (directory / filename).read_bytes()
        if len(data) < 32 or not data.startswith(PNG_MAGIC):
            raise ValueError("invalid PNG")
        if capture.get("size_bytes") != len(data):
            raise ValueError("size mismatch")
        if capture.get("sha256") != hashlib.sha256(data).hexdigest():
            raise ValueError("sha256 mismatch")
    return {"status": "BYTES_CONSISTENT_CI_LOOPBACK_ONLY",
            "deployed_sha_attested": False, "runtime_e2e_verified": False}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_isolated_png_manifest(args.directory), sort_keys=True))
