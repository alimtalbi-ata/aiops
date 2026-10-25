#!/usr/bin/env python3
"""Fail-closed offline verification of an AIOps single-portal candidate ZIP.

Never connects to the target portal. Internal integrity is distinct from
pinned-checkout provenance and neither constitutes runtime qualification.
"""
from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path, PurePosixPath

from deploy.single_portal_candidate_kit import APPROVED, SENSITIVE, safe_path, sha256, source_paths, registry_routes

MAX_FILES = 64
MAX_MEMBER = 4_000_000
MAX_TOTAL = 12_000_000
HEX = re.compile(r"[0-9a-f]{64}\Z")
META = {"metadata/source-manifest.json", "metadata/planned-routes.json",
        "metadata/README.md", "metadata/SHA256SUMS"}


def _json(data: bytes) -> dict:
    value = json.loads(data.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def verify(archive_path: Path, checkout: Path | None = None) -> dict:
    """Verify ZIP bytes and, optionally, every source against a clean pinned checkout."""
    archive_path = Path(archive_path)
    if not archive_path.is_file() or archive_path.is_symlink():
        raise ValueError("candidate archive must be a regular file")
    if archive_path.stat().st_size > MAX_TOTAL:
        raise ValueError("candidate archive exceeds size limit")
    with zipfile.ZipFile(archive_path) as z:
        infos = z.infolist()
        names = [item.filename for item in infos]
        if not 4 <= len(names) <= MAX_FILES or len(set(names)) != len(names):
            raise ValueError("duplicate or excessive ZIP entries")
        expected = META | {"sources/" + path for path in APPROVED}
        if set(names) != expected:
            raise ValueError("candidate member set mismatch")
        total = 0
        data = {}
        for info in infos:
            name = info.filename
            parts = PurePosixPath(name)
            if (parts.is_absolute() or ".." in parts.parts or "\\" in name or
                    info.is_dir() or info.flag_bits & 0x1 or
                    (info.external_attr >> 16) & 0o170000 not in (0, 0o100000)):
                raise ValueError("unsafe candidate ZIP entry")
            if info.file_size > MAX_MEMBER or info.file_size < 0:
                raise ValueError("oversized candidate member")
            total += info.file_size
            if total > MAX_TOTAL:
                raise ValueError("candidate uncompressed limit exceeded")
            if info.compress_size == 0 and info.file_size:
                raise ValueError("invalid compression ratio")
            if info.compress_size and info.file_size > info.compress_size * 2000:
                raise ValueError("suspicious compression ratio")
            data[name] = z.read(info)
    checksum_lines = data["metadata/SHA256SUMS"].decode("ascii").splitlines()
    expected_lines = [f"{sha256(data[name])}  {name}" for name in sorted(set(names) - {"metadata/SHA256SUMS"})]
    if checksum_lines != expected_lines:
        raise ValueError("candidate checksum manifest mismatch")
    manifest = _json(data["metadata/source-manifest.json"])
    if (manifest.get("schema") != "aiops-single-portal-candidate-kit-v1" or
            manifest.get("production_qualified") is not False or
            manifest.get("runtime_e2e_qualified") is not False or
            manifest.get("source_mode") != "reviewed_subset_plus_pinned_git_sha256_references"):
        raise ValueError("candidate status or schema mismatch")
    commit = manifest.get("commit")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("invalid pinned commit")
    inventory = manifest.get("source_inventory")
    if not isinstance(inventory, list) or not inventory:
        raise ValueError("missing source inventory")
    seen = set()
    for row in inventory:
        if not isinstance(row, dict) or set(row) != {"path", "sha256", "bytes", "embedded"}:
            raise ValueError("invalid source inventory row")
        path, digest, size, embedded = (row[k] for k in ("path", "sha256", "bytes", "embedded"))
        if (not isinstance(path, str) or not safe_path(path) or path in seen or
                not isinstance(digest, str) or not HEX.fullmatch(digest) or
                type(size) is not int or not 0 <= size <= MAX_MEMBER or
                type(embedded) is not bool or embedded != (path in APPROVED)):
            raise ValueError("unsafe source inventory row")
        seen.add(path)
        if embedded:
            source = data["sources/" + path]
            if SENSITIVE.search(source) or b"\0" in source:
                raise ValueError("sensitive embedded source")
            if sha256(source) != digest or len(source) != size:
                raise ValueError("embedded source provenance mismatch")
    if (set(APPROVED) - seen or manifest.get("embedded_count") != len(APPROVED) or
            manifest.get("route_count") != 20):
        raise ValueError("candidate inventory counts mismatch")
    routes = _json(data["metadata/planned-routes.json"])
    if (routes.get("entrypoint") != "http://10.79.94.202:17777/" or
            routes.get("all_unverified") is not True or
            routes.get("routes") != registry_routes(data["sources/demo/noc_platform_registry.py"])):
        raise ValueError("route attestation or registry mismatch")
    if checkout is not None:
        root = Path(checkout).resolve(strict=True)
        checkout_commit, tracked = source_paths(root)
        if checkout_commit != commit:
            raise ValueError("pinned checkout mismatch")
        eligible = {path for path in tracked if safe_path(path)}
        if eligible != seen:
            raise ValueError("checkout source set mismatch")
        for row in inventory:
            file = root / row["path"]
            if file.is_symlink() or not file.is_file() or root not in file.resolve().parents:
                raise ValueError("unsafe checkout source")
            source = file.read_bytes()
            if sha256(source) != row["sha256"] or len(source) != row["bytes"]:
                raise ValueError("checkout source mismatch")
    return {"commit": commit, "zip_sha256": sha256(archive_path.read_bytes()),
            "verified_members": len(names), "inventory_sources": len(inventory),
            "routes_unverified": 20, "checkout_provenance_verified": checkout is not None,
            "production_qualified": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--checkout", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.archive, args.checkout), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
