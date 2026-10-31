#!/usr/bin/env python3
"""Rebuild the staged release inventory from the exact files being packaged.

The tracked V8 manifest is historical source metadata, not a release attestation.
This step updates only the disposable staging tree; it never modifies the Git
checkout and never asserts runtime, model, tenant, or production qualification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re


def _safe(path: str) -> bool:
    return (isinstance(path, str) and bool(path) and not path.startswith("/")
            and "\\" not in path and all(part not in ("", ".", "..")
            for part in path.split("/")) and not PurePosixPath(path).is_absolute())


def refresh(root: Path, release: str) -> int:
    if not release or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]*", release):
        raise ValueError("invalid_release_version")
    root = root.resolve(strict=True)
    manifest = root / "manifests" / "MANIFEST.json"
    if not manifest.is_file() or manifest.is_symlink():
        raise ValueError("embedded_manifest_missing_or_link")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("files"), list) or not data["files"]:
        raise ValueError("embedded_manifest_invalid")
    seen = set()
    for entry in data["files"]:
        if not isinstance(entry, dict):
            raise ValueError("embedded_manifest_entry_invalid")
        path = entry.get("path")
        if (not _safe(path) or path in seen or
                path in ("manifests/MANIFEST.json", "FILES-SHA256SUMS")):
            raise ValueError("embedded_manifest_path_invalid")
        seen.add(path)
        target = root / path
        if not target.is_file() or target.is_symlink():
            raise ValueError("embedded_manifest_file_missing:" + path)
        payload = target.read_bytes()
        entry["bytes"] = len(payload)
        entry["sha256"] = hashlib.sha256(payload).hexdigest()
    data.setdefault("source_manifest_release", data.get("release", "UNKNOWN"))
    data.setdefault("source_manifest_name", data.get("name", "UNKNOWN"))
    data["release"] = release
    data["name"] = "AIOps 2.0 staged deployment kit inventory"
    data["inventory_kind"] = "staged-release-file-digests"
    manifest.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return len(seen)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--release", required=True)
    args = parser.parse_args()
    print("STAGED_RELEASE_MANIFEST_REFRESHED=" + str(refresh(args.root, args.release)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
