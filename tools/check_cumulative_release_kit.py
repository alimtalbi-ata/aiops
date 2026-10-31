#!/usr/bin/env python3
"""Fail-closed, read-only inventory gate for a cumulative AIOps2 release ZIP.

This checks file integrity and source correspondence, not runtime installation,
upgrade, rollback behavior, identity, tenant isolation or production readiness.
"""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import zipfile

REQUIRED_PATHS = (
    "RELEASE-MANIFEST.txt",
    "manifests/MANIFEST.json",
    "README.md",
    "compose.yml",
    "config/.env.example",
    "deploy/package.sh",
    "db/migrations/011_hitl_decision_outbox.sql",
    "app/core/hitl_identity.py",
    "app/shared/hitl_identity.py",
    "app/intelligence/main.py",
    "tools/evaluate_ai_core.py",
    "tools/summarize_ai_benchmark.py",
    "app/portal/acme_run_detail.py",
    "app/policy/simulate_fixture.py",
    "app/shared/acme_evidence_utc_preflight.py",
    "docs/architecture/AI-INVOCATION-TELEMETRY-IMPLEMENTATION.md",
    "docs/architecture/AIOPS2-REFERENCE-ARCHITECTURE-2026-10-30.md",
    "docs/architecture/AIOPS2-AI-BENCHMARK-GOVERNANCE-2026-10-30.md",
    "docs/architecture/AIOPS2-REUSE-CONVERGENCE-REGISTER-2026-10-30.md",
    "docs/planning/AIOPS2-48H-DELIVERY-PLAN-2026-10-30.md",
    "docs/customer-story/ACME-P1-SAN-PAYMENTS-ITIL-DEMO-2026-10-30.md",
    "docs/operations/AIOPS2-SCHEDULE-AND-CRON-STRATEGY-2026-10-30.md",
    "docs/release/AIOPS2-RC1.4-KIT-AUDIT-2026-10-30.md",
)
ENTRYPOINT_ALTERNATIVES = {
    "install_upgrade_entrypoint": ("deploy/aiops_release.py", "deploy/deploy-acme-p0.py"),
    "rollback_entrypoint": ("deploy/aiops_release.py", "deploy/deploy-acme-p0.py"),
}
SHA = re.compile(r"^[0-9a-f]{40}$")
CHECKSUM = re.compile(r"^([0-9a-f]{64})  (?:\./)?(.+)$")
MAX_ENTRIES = 10000
MAX_TOTAL_BYTES = 1024 * 1024 * 1024


def _safe_name(name):
    p = PurePosixPath(name)
    return (bool(name) and not name.startswith("/") and "\\" not in name
            and not name.startswith("./") and all(x not in ("", ".", "..") for x in name.split("/"))
            and not p.is_absolute())


def audit_kit(kit, expected_sha, source_dir=None, required_paths=REQUIRED_PATHS,
              alternative_groups=ENTRYPOINT_ALTERNATIVES):
    errors = []
    checked = 0
    source_verified = 0
    if not SHA.fullmatch(expected_sha):
        errors.append("EXPECTED_SHA_INVALID")
    try:
        with zipfile.ZipFile(kit) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ENTRIES or sum(i.file_size for i in infos) > MAX_TOTAL_BYTES:
                errors.append("ARCHIVE_SIZE_LIMIT")
                return {"status": "FAIL", "errors": errors, "checksums_verified": 0, "source_files_verified": 0}
            names = [i.filename for i in infos if not i.is_dir()]
            if len(names) != len(set(names)):
                errors.append("DUPLICATE_MEMBERS")
            for i in infos:
                if not _safe_name(i.filename.rstrip("/")):
                    errors.append("UNSAFE_MEMBER_PATH:" + i.filename)
                if stat.S_ISLNK(i.external_attr >> 16):
                    errors.append("SYMLINK_MEMBER:" + i.filename)
            if errors:
                return {"status": "FAIL", "errors": sorted(set(errors)), "checksums_verified": 0, "source_files_verified": 0}
            files = set(names)
            for path in required_paths:
                if path not in files:
                    errors.append("REQUIRED_MISSING:" + path)
            for label, choices in alternative_groups.items():
                if not any(path in files for path in choices):
                    errors.append("ENTRYPOINT_MISSING:" + label)
            if "RELEASE-MANIFEST.txt" in files:
                manifest = archive.read("RELEASE-MANIFEST.txt").decode("utf-8", "replace")
                matches = re.findall(r"^git_commit=([^\r\n]+)$", manifest, re.MULTILINE)
                if len(matches) != 1 or matches[0] != expected_sha:
                    errors.append("MANIFEST_SHA_MISMATCH")
            # The embedded product manifest is an independent integrity claim.
            # A valid FILES-SHA256SUMS cannot excuse stale file digests here.
            if "manifests/MANIFEST.json" in files:
                try:
                    embedded = json.loads(archive.read("manifests/MANIFEST.json"))
                    if not isinstance(embedded, dict) or not isinstance(embedded.get("files"), list):
                        errors.append("EMBEDDED_MANIFEST_INVALID")
                    else:
                        release = embedded.get("release")
                        versions = re.findall(r"^version=([^\r\n]+)$", manifest, re.MULTILINE) if "RELEASE-MANIFEST.txt" in files else []
                        if not isinstance(release, str) or not release or len(versions) != 1 or versions[0] != release:
                            errors.append("EMBEDDED_RELEASE_VERSION_MISMATCH")
                        seen = set()
                        if not embedded["files"]:
                            errors.append("EMBEDDED_MANIFEST_EMPTY")
                        for entry in embedded["files"]:
                            if not isinstance(entry, dict):
                                errors.append("EMBEDDED_ENTRY_INVALID")
                                continue
                            path = entry.get("path")
                            size = entry.get("bytes")
                            digest = entry.get("sha256")
                            if not isinstance(path, str) or not _safe_name(path) or path in seen or not isinstance(size, int) or isinstance(size, bool) or size < 0 or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                                errors.append("EMBEDDED_ENTRY_INVALID")
                                continue
                            seen.add(path)
                            if path not in files:
                                errors.append("EMBEDDED_FILE_MISSING:" + path)
                                continue
                            content = archive.read(path)
                            if len(content) != size:
                                errors.append("EMBEDDED_FILE_SIZE_MISMATCH:" + path)
                            if hashlib.sha256(content).hexdigest() != digest:
                                errors.append("EMBEDDED_FILE_SHA_MISMATCH:" + path)
                except (ValueError, UnicodeDecodeError):
                    errors.append("EMBEDDED_MANIFEST_UNREADABLE")
            if "FILES-SHA256SUMS" not in files:
                errors.append("CHECKSUM_MANIFEST_MISSING")
            else:
                entries = {}
                for line in archive.read("FILES-SHA256SUMS").decode("utf-8", "replace").splitlines():
                    match = CHECKSUM.fullmatch(line)
                    if not match or not _safe_name(match.group(2)):
                        errors.append("CHECKSUM_LINE_INVALID")
                        continue
                    path = match.group(2)
                    if path in entries:
                        errors.append("DUPLICATE_CHECKSUM:" + path)
                    entries[path] = match.group(1)
                for path in sorted((files - {"FILES-SHA256SUMS"}) - entries.keys()):
                    errors.append("UNCHECKSUMMED_MEMBER:" + path)
                for path in sorted(entries.keys() - files):
                    errors.append("CHECKSUM_MEMBER_MISSING:" + path)
                for path, digest in entries.items():
                    if path in files:
                        if hashlib.sha256(archive.read(path)).hexdigest() != digest:
                            errors.append("CHECKSUM_MISMATCH:" + path)
                        else:
                            checked += 1
            bad_crc = archive.testzip()
            if bad_crc:
                errors.append("CRC_MISMATCH:" + bad_crc)
            if source_dir is None:
                errors.append("SOURCE_TREE_NOT_PROVIDED")
            else:
                root = Path(source_dir).resolve()
                try:
                    actual_sha = subprocess.check_output(
                        ["git", "-C", str(root), "rev-parse", "HEAD"],
                        text=True, stderr=subprocess.DEVNULL).strip()
                    if actual_sha != expected_sha:
                        errors.append("SOURCE_HEAD_MISMATCH")
                    # Matching HEAD alone is insufficient: modified tracked files
                    # can be repackaged with matching checksums but not that commit.
                    top = subprocess.check_output(
                        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                        text=True, stderr=subprocess.DEVNULL).strip()
                    if Path(top).resolve() != root:
                        errors.append("SOURCE_NOT_REPOSITORY_ROOT")
                    dirty = subprocess.check_output(
                        ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"],
                        text=True, stderr=subprocess.DEVNULL)
                    if dirty.strip():
                        errors.append("SOURCE_TREE_DIRTY")
                except (OSError, subprocess.CalledProcessError):
                    errors.append("SOURCE_HEAD_OR_STATUS_UNAVAILABLE")
                # Every packaged source member, not just the required subset,
                # must be backed by the exact tracked checkout. A checksummed
                # untracked payload can otherwise masquerade as the source SHA.
                # These two generated metadata files have independent checks.
                generated = {"RELEASE-MANIFEST.txt", "FILES-SHA256SUMS"}
                try:
                    tracked_output = subprocess.check_output(
                        ["git", "-C", str(root), "ls-files", "-z", "--cached"],
                        stderr=subprocess.DEVNULL)
                    tracked = set(tracked_output.decode("utf-8", "surrogateescape").rstrip("\0").split("\0"))
                except (OSError, subprocess.CalledProcessError):
                    errors.append("SOURCE_TRACKED_FILES_UNAVAILABLE")
                    tracked = set()
                # The staged generator deliberately refreshes MANIFEST.json from
                # source metadata and the exact archive bytes. Accept that one
                # generated member only when its entire JSON object is the
                # deterministic transformation of the tracked source manifest.
                # Other members must remain byte-identical to Git HEAD.
                staged_name = "manifests/MANIFEST.json"
                if staged_name in files:
                    try:
                        staged = json.loads(archive.read(staged_name))
                        if (isinstance(staged, dict) and
                                staged.get("inventory_kind") == "staged-release-file-digests"):
                            original = root / staged_name
                            if staged_name not in tracked or original.is_symlink() or not original.is_file():
                                errors.append("STAGED_MANIFEST_SOURCE_MISSING")
                            else:
                                expected = json.loads(original.read_text(encoding="utf-8"))
                                if (not isinstance(expected, dict) or
                                        not isinstance(expected.get("files"), list) or
                                        not expected["files"]):
                                    errors.append("STAGED_MANIFEST_SOURCE_INVALID")
                                else:
                                    valid_entries = True
                                    for entry in expected["files"]:
                                        if not isinstance(entry, dict):
                                            valid_entries = False
                                            break
                                        member = entry.get("path")
                                        if (not isinstance(member, str) or
                                                not _safe_name(member) or member not in files or
                                                member in {staged_name, "FILES-SHA256SUMS"}):
                                            valid_entries = False
                                            break
                                        payload = archive.read(member)
                                        entry["bytes"] = len(payload)
                                        entry["sha256"] = hashlib.sha256(payload).hexdigest()
                                    versions = re.findall(
                                        r"^version=([^\\r\\n]+)$",
                                        manifest if "RELEASE-MANIFEST.txt" in files else "",
                                        re.MULTILINE)
                                    if not valid_entries or len(versions) != 1:
                                        errors.append("STAGED_MANIFEST_SOURCE_INVALID")
                                    else:
                                        expected.setdefault("source_manifest_release", expected.get("release", "UNKNOWN"))
                                        expected.setdefault("source_manifest_name", expected.get("name", "UNKNOWN"))
                                        expected["release"] = versions[0]
                                        expected["name"] = "AIOps 2.0 staged deployment kit inventory"
                                        expected["inventory_kind"] = "staged-release-file-digests"
                                        if staged != expected:
                                            errors.append("STAGED_MANIFEST_SOURCE_PROVENANCE_MISMATCH")
                                        else:
                                            generated.add(staged_name)
                                            source_verified += 1
                    except (ValueError, UnicodeDecodeError, OSError, TypeError):
                        errors.append("STAGED_MANIFEST_SOURCE_UNREADABLE")
                for path in sorted(files - generated):
                    if path not in tracked:
                        errors.append("SOURCE_MEMBER_UNTRACKED:" + path)
                        continue
                    candidate = root / path
                    if candidate.is_symlink():
                        errors.append("SOURCE_FILE_SYMLINK:" + path)
                    elif not candidate.is_file():
                        errors.append("SOURCE_FILE_MISSING:" + path)
                    elif hashlib.sha256(candidate.read_bytes()).hexdigest() != hashlib.sha256(archive.read(path)).hexdigest():
                        errors.append("SOURCE_BLOB_MISMATCH:" + path)
                    else:
                        source_verified += 1
    except (OSError, zipfile.BadZipFile, RuntimeError, ValueError) as exc:
        errors.append("ARCHIVE_UNREADABLE:" + type(exc).__name__)
    return {"status": "FAIL" if errors else "PASS", "errors": sorted(set(errors)),
            "checksums_verified": checked, "source_files_verified": source_verified,
            "note": "Inventory/source gate only; install, upgrade, rollback and runtime smoke remain NOT_TESTED."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit", type=Path, required=True)
    parser.add_argument("--expected-source-sha", required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    args = parser.parse_args()
    result = audit_kit(args.kit, args.expected_source_sha, args.source_dir)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
