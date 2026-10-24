"""One-level historical ZIP source quarantine, offline and fail-closed.

No automatic import, execution, production access or third-level ZIP traversal.
Default invocation is a fully validated dry run. All three independent SHA-256
pins must come from a separately reviewed inventory.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

from recovery.tools.zip_source_recovery import (
    BLOCKED_CONTENT, BLOCKED_NAMES, EXTENSIONS, MAX_MEMBER,
    MAX_NESTED_MEMBERS, MAX_NESTED_TOTAL, MAX_OPAQUE_ZIP,
    _open_stable_archive, _safe_name, _validated_infos,
)

_SHA = re.compile(r"[a-f0-9]{64}\Z")


def quarantine_nested_source(
    archive: Path,
    nested_member: str,
    source_member: str,
    *,
    expected_outer_sha256: str,
    expected_nested_sha256: str,
    expected_member_sha256: str,
    quarantine: Path | None = None,
    apply: bool = False,
) -> dict:
    """Verify outer->inner->source bytes, optionally quarantine exactly one file.

    The original outer archive and all ZIP members are structurally checked.
    No member is imported or executed; Python AST parse is only a syntax gate.
    """
    if type(apply) is not bool:
        raise ValueError("apply must be boolean")
    if (not isinstance(nested_member, str) or not _safe_name(nested_member)
            or BLOCKED_NAMES.search(nested_member) or not nested_member.lower().endswith(".zip")):
        raise ValueError("invalid nested ZIP member")
    if (not isinstance(source_member, str) or not _safe_name(source_member)
            or BLOCKED_NAMES.search(source_member)
            or PurePosixPath(source_member).suffix.lower() not in EXTENSIONS):
        raise ValueError("invalid nested source member")
    if not all(isinstance(d, str) and _SHA.fullmatch(d) for d in (
        expected_outer_sha256, expected_nested_sha256, expected_member_sha256
    )):
        raise ValueError("three independently reviewed SHA-256 pins required")
    if archive.is_symlink() or not archive.is_file() or archive.suffix.lower() != ".zip":
        raise ValueError("source must be a regular ZIP")
    if apply and (quarantine is None or quarantine.is_symlink() or not quarantine.is_dir()):
        raise ValueError("existing non-symlink quarantine directory required")

    with _open_stable_archive(archive) as (stream, outer_sha):
        if outer_sha != expected_outer_sha256:
            raise ValueError("outer archive SHA-256 mismatch")
        with zipfile.ZipFile(stream) as outer:
            infos = _validated_infos(outer)
            candidates = [i for i in infos if i.filename == nested_member]
            if len(candidates) != 1 or candidates[0].file_size > MAX_OPAQUE_ZIP:
                raise ValueError("nested archive missing or oversized")
            nested_data = outer.read(candidates[0])
            if len(nested_data) != candidates[0].file_size:
                raise ValueError("nested archive length mismatch")
        if hashlib.sha256(nested_data).hexdigest() != expected_nested_sha256:
            raise ValueError("nested archive SHA-256 mismatch")
        with zipfile.ZipFile(io.BytesIO(nested_data)) as inner:
            inner_infos = _validated_infos(inner, nested=True)
            if (len(inner_infos) > MAX_NESTED_MEMBERS
                    or sum(i.file_size for i in inner_infos) > MAX_NESTED_TOTAL):
                raise ValueError("nested archive inspection budget exceeded")
            matches = [i for i in inner_infos if i.filename == source_member]
            if len(matches) != 1 or matches[0].file_size > MAX_MEMBER:
                raise ValueError("nested source missing or oversized")
            data = inner.read(matches[0])
            if len(data) != matches[0].file_size:
                raise ValueError("nested source length mismatch")
        digest = hashlib.sha256(data).hexdigest()
        if digest != expected_member_sha256:
            raise ValueError("nested source SHA-256 mismatch")
        if BLOCKED_CONTENT.search(data):
            raise ValueError("sensitive-looking source requires private manual review")
        if source_member.lower().endswith(".py"):
            import ast
            ast.parse(data.decode("utf-8"), filename=source_member)
        # Detect an outer archive altered while being inspected, using the
        # same open descriptor. Never rely on a second path lookup.
        stream.seek(0)
        if hashlib.file_digest(stream, "sha256").hexdigest() != outer_sha:
            raise ValueError("outer archive changed during inspection")

    report = {
        "status": "VALIDATED_DRY_RUN_NOT_IMPORTED",
        "outer_sha256": outer_sha,
        "nested_sha256": expected_nested_sha256,
        "member_sha256": digest,
        "bytes": len(data),
        "import_authorized": False,
        "runtime_attested": False,
        "source_completeness_attested": False,
    }
    if not apply:
        return report

    # Existing operator-owned directory only; no mkdir, symlink traversal,
    # overwrite, or write outside the selected quarantine directory.
    assert quarantine is not None
    rootfd = os.open(quarantine, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    basename = (
        hashlib.sha256((archive.name + "\0" + nested_member + "\0" + source_member).encode()).hexdigest()[:16]
        + "-" + PurePosixPath(source_member).name
    )
    try:
        fd = os.open(basename, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=rootfd)
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
        except BaseException:
            os.unlink(basename, dir_fd=rootfd)
            raise
    finally:
        os.close(rootfd)
    report["status"] = "QUARANTINED_NOT_QUALIFIED"
    report["quarantine_file"] = basename
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--nested-member", required=True)
    parser.add_argument("--source-member", required=True)
    parser.add_argument("--outer-sha256", required=True)
    parser.add_argument("--nested-sha256", required=True)
    parser.add_argument("--member-sha256", required=True)
    parser.add_argument("--quarantine", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = quarantine_nested_source(
            args.archive, args.nested_member, args.source_member,
            expected_outer_sha256=args.outer_sha256,
            expected_nested_sha256=args.nested_sha256,
            expected_member_sha256=args.member_sha256,
            quarantine=args.quarantine, apply=args.apply,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:
        # Never print raw exceptions: filenames or archive metadata can be private.
        print(json.dumps({"status": "REJECTED", "error_class": type(exc).__name__}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
