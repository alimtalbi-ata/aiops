"""Offline exact-byte comparison of reviewed ZIP inventory against a checkout.

Never imports or executes recovered sources. A hash match establishes only byte
identity, NOT completeness, provenance authenticity or production readiness.
Output is a metadata-only reuse decision; it is not an automatic import plan.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from recovery.tools.zip_source_recovery import (
    BLOCKED_NAMES, EXTENSIONS, MAX_MEMBER, _safe_name,
)

_SHA = re.compile(r"^[0-9a-f]{64}$")
_MAX_CHECKOUT_FILES = 20000
_MAX_INVENTORY_BYTES = 8 * 1024 * 1024
_SKIPPED_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".tox", ".mypy_cache"}


def _sha_regular_file(path: Path) -> str | None:
    """Read a regular file without following a final-component symlink."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except (OSError, ValueError):
        return None
    try:
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_MEMBER:
                return None
            return hashlib.file_digest(stream, "sha256").hexdigest()
    except OSError:
        return None


def index_checkout(root: Path) -> dict[str, str]:
    """Index safe eligible source paths only, never symlinks or secrets.

    Caller must supply an existing checkout directory; no Git commands or
    network access are made. Hashes are metadata, not source publication.
    """
    if root.is_symlink() or not root.is_dir():
        raise ValueError("checkout root must be an existing real directory")
    result: dict[str, str] = {}
    examined = 0
    for parent, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in _SKIPPED_DIRS
                         and not (Path(parent) / d).is_symlink()
                         and not BLOCKED_NAMES.search(d))
        for filename in sorted(files):
            path = Path(parent) / filename
            rel = path.relative_to(root).as_posix()
            if (not _safe_name(rel) or BLOCKED_NAMES.search(rel)
                    or path.suffix.lower() not in EXTENSIONS or path.is_symlink()):
                continue
            examined += 1
            if examined > _MAX_CHECKOUT_FILES:
                raise ValueError("checkout source file limit exceeded")
            digest = _sha_regular_file(path)
            if digest is not None:
                result[rel] = digest
    return result


def compare_inventory(document: dict, checkout: dict[str, str]) -> dict:
    """Classify exact reuse and path divergence; always require human review."""
    if (not isinstance(document, dict) or document.get("schema") != "aiops-zip-source-inventory/v1"
            or not isinstance(document.get("members"), list)
            or document.get("member_count") != len(document["members"])
            or len(document["members"]) > 5000):
        raise ValueError("unsupported or inconsistent ZIP inventory")
    # V2.13.64 introduced optional one-level, metadata-only nested sources.
    # Compare their exact hashes to the same checkout without extracting them.
    # Older inventories without nested fields retain their original behavior.
    nested = document.get("nested_members", [])
    if (not isinstance(nested, list) or len(nested) > 1000
            or type(document.get("nested_member_count", len(nested))) is not int
            or document.get("nested_member_count", len(nested)) != len(nested)
            or (nested and document.get("nested_inspection_requested") is not True)):
        raise ValueError("inconsistent nested ZIP source inventory")
    # Bind every nested source to its parent ZIP fingerprint from the same
    # reviewed inventory. A fabricated nested row cannot borrow an arbitrary
    # plausible-looking SHA or path and be classified as reusable.
    inspected_nested_archives = set()
    if nested:
        opaque = document.get("opaque_archives")
        if (not isinstance(opaque, list)
                or type(document.get("opaque_archive_count")) is not int
                or document["opaque_archive_count"] != len(opaque)):
            raise ValueError("nested source lacks parent ZIP inventory")
        for parent in opaque:
            if not isinstance(parent, dict):
                raise ValueError("invalid parent ZIP inventory")
            if parent.get("status") != "NESTED_METADATA_ONLY_INSPECTED":
                continue
            origin = (parent.get("archive"), parent.get("archive_sha256"),
                      parent.get("member_path"), parent.get("member_sha256"))
            if (not all(isinstance(x, str) for x in origin)
                    or not _safe_name(origin[0]) or "/" in origin[0] or "\\" in origin[0]
                    or not origin[0].lower().endswith(".zip")
                    or not _SHA.fullmatch(origin[1])
                    or not _safe_name(origin[2]) or not origin[2].lower().endswith(".zip")
                    or BLOCKED_NAMES.search(origin[2])
                    or not _SHA.fullmatch(origin[3])
                    or parent.get("import_authorized") is not False
                    or origin in inspected_nested_archives):
                raise ValueError("unsafe or duplicated parent ZIP provenance")
            inspected_nested_archives.add(origin)
    if not isinstance(checkout, dict):
        raise ValueError("invalid checkout index")
    by_hash: dict[str, list[str]] = {}
    for path, digest in checkout.items():
        if (not isinstance(path, str) or not _safe_name(path)
                or BLOCKED_NAMES.search(path) or not isinstance(digest, str)
                or not _SHA.fullmatch(digest)):
            raise ValueError("invalid checkout index entry")
        by_hash.setdefault(digest, []).append(path)
    for paths in by_hash.values():
        paths.sort()
    entries, identities = [], set()
    # Explicit origin_kind prevents same-path files in an outer ZIP and an
    # embedded ZIP from silently collapsing into a single identity.
    for origin_kind, item in (
            [( "outer", row) for row in document["members"]] +
            [( "nested", row) for row in nested]):
        if not isinstance(item, dict):
            raise ValueError("invalid inventory member")
        archive, path = item.get("archive"), item.get("member_path")
        digest, archive_hash = item.get("member_sha256"), item.get("archive_sha256")
        if (not isinstance(archive, str) or not archive.endswith(".zip")
                or "/" in archive or "\\" in archive or not _safe_name(archive)
                or not isinstance(path, str) or not _safe_name(path)
                or BLOCKED_NAMES.search(path) or Path(path).suffix.lower() not in EXTENSIONS
                or not isinstance(digest, str) or not _SHA.fullmatch(digest)
                or not isinstance(archive_hash, str) or not _SHA.fullmatch(archive_hash)):
            raise ValueError("invalid inventory path or SHA-256")
        nested_path = item.get("nested_archive_member") if origin_kind == "nested" else None
        nested_sha = item.get("nested_archive_sha256") if origin_kind == "nested" else None
        if origin_kind == "nested":
            if (not isinstance(nested_path, str) or not _safe_name(nested_path)
                    or BLOCKED_NAMES.search(nested_path) or not nested_path.lower().endswith(".zip")
                    or not isinstance(nested_sha, str) or not _SHA.fullmatch(nested_sha)
                    or item.get("import_authorized") is not False
                    or item.get("reuse_status") != "quarantine_review_required"
                    or (archive, archive_hash, nested_path, nested_sha)
                       not in inspected_nested_archives):
                raise ValueError("unsafe or unreviewed nested source provenance")
        elif "nested_archive_member" in item or "nested_archive_sha256" in item:
            raise ValueError("outer member contains nested provenance")
        key = (archive, nested_path, path)
        if key in identities:
            raise ValueError("duplicate inventory identity")
        identities.add(key)
        if item.get("sensitive_pattern_detected") is not False or item.get("python_syntax") == "parse_failed":
            status = "BLOCKED_REVIEW"
        elif checkout.get(path) == digest:
            status = "EXACT_PATH_DUPLICATE"
        elif digest in by_hash:
            status = "EXACT_BYTES_OTHER_PATH"
        elif path in checkout:
            status = "DIVERGENT_PATH_REVIEW"
        else:
            status = "NEW_CANDIDATE_REVIEW"
        entry = {
            "archive": archive, "archive_sha256": archive_hash,
            "member_path": path, "member_sha256": digest,
            "origin_kind": origin_kind, "status": status,
            "matching_checkout_paths": by_hash.get(digest, [])[:20] if status.startswith("EXACT_") else [],
            "import_authorized": False,
        }
        if origin_kind == "nested":
            entry["nested_archive_member"] = nested_path
            entry["nested_archive_sha256"] = nested_sha
        entries.append(entry)
    return {
        "schema": "aiops-zip-reuse-comparison/v1",
        "source_schema": document["schema"],
        "runtime_attested": False,
        "complete_source_attested": False,
        "import_authorized": False,
        "entry_count": len(entries),
        "nested_entry_count": len(nested),
        "entries": entries,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path, help="reviewed metadata-only ZIP inventory JSON")
    parser.add_argument("--checkout", type=Path, required=True, help="existing local checkout (read-only)")
    parser.add_argument("--output", type=Path, help="create-only metadata report; stdout if omitted")
    args = parser.parse_args()
    if args.inventory.is_symlink() or not args.inventory.is_file() or args.inventory.stat().st_size > _MAX_INVENTORY_BYTES:
        parser.error("inventory must be a regular bounded JSON file")
    with args.inventory.open("rb") as stream:
        document = json.load(stream)
    report = compare_inventory(document, index_checkout(args.checkout))
    payload = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output is None:
        print(payload, end="")
    else:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(payload)


if __name__ == "__main__":
    main()
