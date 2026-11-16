"""Offline NOC screenshot integrity gate. No network, browser or LIVE effects.

Usage: python scripts/noc_capture_integrity_gate.py manifest.json capture-directory EXPECTED_HEAD_SHA
This checks actual PNG bytes and declarations; it does not prove browser execution.
"""
import hashlib
import json
import pathlib
import struct
import sys

VIEWPORTS = (320, 768, 1440)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def qualify(manifest, root, expected_sha):
    errors = []
    if not isinstance(manifest, dict):
        return ["manifest must be an object"]
    if manifest.get("source_sha") != expected_sha or len(expected_sha) != 40 or any(c not in "0123456789abcdef" for c in expected_sha):
        errors.append("source SHA mismatch or invalid")
    if manifest.get("mode") not in ("DEMO", "SIMULATION"):
        errors.append("mode must be DEMO or SIMULATION")
    if manifest.get("policy") != "DENY_LIVE" or manifest.get("hitl") != "REQUIRED":
        errors.append("Policy/HITL must fail closed")
    captures = manifest.get("captures")
    if not isinstance(captures, list) or len(captures) != len(VIEWPORTS):
        return errors + ["exactly three captures required"]
    widths = set()
    root = pathlib.Path(root).resolve()
    for i, item in enumerate(captures):
        if not isinstance(item, dict):
            errors.append(f"capture {i}: invalid object")
            continue
        width = item.get("viewport_width")
        if type(width) is not int or width not in VIEWPORTS or width in widths:
            errors.append(f"capture {i}: invalid or repeated viewport")
        widths.add(width)
        if any(item.get(k) is not True for k in ("unknown_visible", "deny_live_visible", "no_horizontal_overflow", "external_requests_blocked")):
            errors.append(f"capture {i}: safety assertions missing")
        filename = item.get("file")
        if not isinstance(filename, str) or not filename or pathlib.PurePath(filename).name != filename or filename in (".", ".."):
            errors.append(f"capture {i}: unsafe filename")
            continue
        path = (root / filename).resolve()
        if not path.is_relative_to(root) or not path.is_file() or path.is_symlink():
            errors.append(f"capture {i}: missing/unsafe file")
            continue
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != item.get("sha256"):
            errors.append(f"capture {i}: SHA-256 mismatch")
        if len(raw) < 24 or raw[:8] != PNG_SIGNATURE or raw[12:16] != b"IHDR":
            errors.append(f"capture {i}: invalid PNG header")
        else:
            png_width, png_height = struct.unpack(">II", raw[16:24])
            if png_width != width or png_height < 1:
                errors.append(f"capture {i}: PNG dimensions mismatch")
    if widths != set(VIEWPORTS):
        errors.append("viewport coverage incomplete")
    return errors


def main(argv):
    if len(argv) != 4:
        print("usage: noc_capture_integrity_gate.py manifest.json capture-directory EXPECTED_HEAD_SHA", file=sys.stderr)
        return 2
    try:
        manifest = json.loads(pathlib.Path(argv[1]).read_text(encoding="utf-8"))
        errors = qualify(manifest, argv[2], argv[3])
    except (OSError, ValueError) as exc:
        print(f"NOT_QUALIFIED: {type(exc).__name__}", file=sys.stderr)
        return 2
    for error in errors:
        print("FAIL:", error)
    print("MANIFEST_BYTES_CHECKED" if not errors else "NOT_QUALIFIED")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
