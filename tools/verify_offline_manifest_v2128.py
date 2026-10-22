#!/usr/bin/env python3
"""Fail-closed integrity check for the offline ACME kit; does not attest provenance."""
import argparse
import hashlib
import json
import re
import stat
from pathlib import Path

REQUIRED = {"index.html", "ACME-MISSION-CONTROL.html", "ACME-HISTORICAL-AUDIT.html"}
HASH = re.compile(r"[0-9a-fA-F]{64}\Z")


def verify(root: Path) -> dict:
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("unsafe or absent kit directory")
    root = root.resolve()
    manifest_file = root / "manifest.json"
    if manifest_file.is_symlink() or not manifest_file.is_file():
        raise ValueError("missing or symlink manifest")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    if manifest.get("dgx_independently_attested") is not False or manifest.get("live_execution_qualified") is not False:
        raise ValueError("unsubstantiated attestation in offline manifest")
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise ValueError("missing file entries")
    seen = set()
    results = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("malformed entry")
        name, expected = entry.get("name"), entry.get("sha256")
        if not isinstance(name, str) or not name or not isinstance(expected, str) or not HASH.fullmatch(expected):
            raise ValueError("invalid name or sha256")
        relative = Path(name)
        if relative.is_absolute() or any(part in (".", "..") for part in name.replace("\\", "/").split("/")) or "\\" in name:
            raise ValueError("unsafe path")
        if name in seen:
            raise ValueError("duplicate entry")
        seen.add(name)
        path = root / relative
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
            raise ValueError("missing, symlink or out-of-root file")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected.lower():
            raise ValueError("sha256 mismatch: " + name)
        results.append({"name": name, "sha256": actual, "status": "PASS"})
    if seen != REQUIRED:
        raise ValueError("unexpected kit file inventory")
    actual_files = {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and p.name != "manifest.json"
    }
    if actual_files != seen:
        raise ValueError("unlisted kit files")
    return {
        "qualification_version": "2.12.8",
        "manifest_version": manifest.get("version"),
        "mode": manifest.get("mode"),
        "historical_source": manifest.get("historical_source"),
        "dgx_independently_attested": False,
        "live_execution_qualified": False,
        "files": results,
        "status": "PASS",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        report = verify(args.kit)
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        report = {"qualification_version": "2.12.8", "status": "FAIL",
                  "error": str(exc), "dgx_independently_attested": False,
                  "live_execution_qualified": False}
    if args.report:
        if args.report.is_symlink():
            raise SystemExit("refusing symlink report")
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("AIOPS_V2128_INTEGRITY=" + report["status"])
    if report["status"] != "PASS":
        print(report["error"])
        raise SystemExit(1)


if __name__ == "__main__":
    main()
