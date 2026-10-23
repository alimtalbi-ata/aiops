"""Verify actual legacy PNG bytes against historical SHA declarations.

This is offline integrity verification, never runtime/business authentication.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
from collections.abc import Mapping
from demo.star_legacy_playwright_audit import audit_legacy_manifest

def verify_legacy_pngs(document: dict, root: Path) -> dict:
    report = audit_legacy_manifest(document)
    captures = document.get("results", document.get("captures"))
    base = root.resolve(strict=True)
    if not base.is_dir() or root.is_symlink():
        raise ValueError("invalid evidence root")
    for original, row in zip(captures, report["entries"]):
        name = original.get("file")
        if name is None and original.get("screenshot"):
            name = Path(original["screenshot"]).name
        # Legacy absolute paths are not trusted; require an exact leaf basename.
        if not isinstance(name, str) or name != Path(name).name or not name.endswith(".png"):
            continue
        if "/" in name or "\\" in name or name.startswith("."):
            continue
        p = root / name
        if p.is_symlink() or not p.is_file() or p.resolve().parent != base:
            continue
        expected=original.get("sha256")
        if not isinstance(expected,str) or len(expected)!=64 or any(x not in "0123456789abcdef" for x in expected):
            continue
        if p.stat().st_size > 24 * 1024 * 1024 or p.stat().st_size < 24:
            continue
        data=p.read_bytes()
        if not data.startswith(b"\x89PNG\r\n\x1a\n") or b"IEND" not in data[-20:]:
            continue
        row["capture_file_available"]=True
        row["integrity_verified"]=hashlib.sha256(data).hexdigest()==expected
        # Offline byte integrity is NEVER live origin attestation.
    return report
