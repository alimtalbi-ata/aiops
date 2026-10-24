"""Verify actual legacy PNG bytes against historical SHA declarations.

This is offline integrity verification, never runtime/business authentication.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from collections.abc import Mapping
from demo.star_legacy_playwright_audit import audit_legacy_manifest
from demo.star_png_integrity import inspect_png

def verify_legacy_pngs(document: dict, root: Path) -> dict:
    report = audit_legacy_manifest(document)
    captures = document.get("results", document.get("captures"))
    base = root.resolve(strict=True)
    if not base.is_dir() or root.is_symlink():
        raise ValueError("invalid evidence root")
    seen_names = set()
    for original, row in zip(captures, report["entries"]):
        name = original.get("file")
        if name is None and isinstance(original.get("screenshot"), str):
            historical = original["screenshot"]
            # Historical absolute paths must be a canonical POSIX path with no traversal.
            if ("\\" in historical or "\x00" in historical or
                    any(part in ("", ".", "..") for part in historical.split("/")[1:]) or
                    not historical.startswith("/home/aiops/")):
                row["migration_note"] = "unsafe_historical_path"
                continue
            name = historical.rsplit("/", 1)[-1]
        # Legacy absolute paths are not trusted; require an exact leaf basename.
        if not isinstance(name, str) or name != Path(name).name or not name.endswith(".png"):
            continue
        if "/" in name or "\\" in name or name.startswith("."):
            continue
        # Repeated filenames make historical attribution ambiguous: fail closed.
        if name in seen_names:
            row["migration_note"] = "duplicate_filename"
            continue
        seen_names.add(name)
        if original.get("status") != "PASS":
            row["migration_note"] = "legacy_capture_failed"
            continue
        p = root / name
        if p.is_symlink() or not p.is_file() or p.resolve().parent != base:
            continue
        expected=original.get("sha256")
        if not isinstance(expected,str) or len(expected)!=64 or any(x not in "0123456789abcdef" for x in expected):
            continue
        try:
            actual, _ = inspect_png(p)
        except (OSError, ValueError):
            continue
        row["capture_file_available"]=True
        row["integrity_verified"]=actual==expected
        # Offline byte integrity is NEVER live origin attestation.
    return report

def main() -> None:
    parser = argparse.ArgumentParser(description="Offline F20.13 legacy PNG byte audit")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    document = json.loads(args.manifest.read_text(encoding="utf-8"))
    report = verify_legacy_pngs(document, args.root)
    if args.output.is_symlink():
        raise ValueError("symlink output is forbidden")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    print("LEGACY_PNG_BYTES_AUDITED;RUNTIME_UNATTESTED")

if __name__ == "__main__":
    main()
