"""Offline, fail-closed ZIP source recovery; never writes to runtime or GitHub.

Inventory is metadata only. Extraction requires explicit --apply and exact --allow.
A passing syntax check is NOT proof that historical code is complete or usable.
"""
from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import unicodedata
import zipfile

MAX_MEMBERS = 5000
MAX_MEMBER = 2 * 1024 * 1024
# Nested ZIPs in historical cumulative releases are opaque metadata only.
# Never recurse into, extract or execute their contents in this recovery tool.
MAX_OPAQUE_ZIP = 32 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
MAX_NESTED_ARCHIVES = 8
MAX_NESTED_MEMBERS = 1000
# One global budget across every inspected inner ZIP; never recursive.
MAX_NESTED_TOTAL = 64 * 1024 * 1024
OPAQUE_METADATA_EXTENSIONS = frozenset({".pdf", ".docx", ".png", ".svg", ".jpg", ".jpeg", ".zip"})
MAX_RATIO = 200
EXTENSIONS = {".py", ".js", ".ts", ".html", ".css", ".sh", ".yml", ".yaml", ".toml", ".json", ".md"}
BLOCKED_NAMES = re.compile(r"(?:^|[._/-])(?:\.env|credentials?|secrets?|tokens?|cookies?|sessions?|private|id_rsa|\.git)(?:[._/-]|$)", re.I)
BLOCKED_CONTENT = re.compile(rb"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|Bearer\s+[A-Za-z0-9._~+/=-]{16,}", re.I)
WINDOWS_RESERVED = frozenset({"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)})
WINDOWS_INVALID = frozenset('< > " | ? *'.replace(" ", ""))
VERSION = re.compile(r"(?i)v(\d+(?:[._]\d+){1,5}|\d{4,6})(?!\d)")


def _safe_name(name: str) -> bool:
    if not name or "\\" in name or "\x00" in name or name.startswith("/") or ":" in name:
        return False
    path = PurePosixPath(name)
    parts = name.split("/")
    # Preserve deterministic identity across Windows/Linux checkout and ZIP tools.
    # Windows device names (including CON.py) and NFC aliases are unsafe.
    if unicodedata.normalize("NFC", name) != name:
        return False
    for part in parts:
        if (part in {"", ".", ".."} or part.endswith((".", " "))
                or any(ord(ch) < 32 or ord(ch) == 127 or ch in WINDOWS_INVALID for ch in part)
                or part.split(".", 1)[0].upper() in WINDOWS_RESERVED):
            return False
    return len(path.parts) <= 20 and len(name) <= 240


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validated_infos(z: zipfile.ZipFile, *, nested: bool = False) -> list[zipfile.ZipInfo]:
    """Apply the same whole-archive structural fence before audit OR extraction."""
    infos = [i for i in z.infolist() if not i.is_dir()]
    if len(infos) > MAX_MEMBERS:
        raise ValueError("too many archive members")
    used_paths, total = set(), 0
    for item in infos:
        name = item.filename
        if not _safe_name(name):
            raise ValueError("unsafe ZIP member path")
        folded = name.casefold()
        if folded in used_paths:
            raise ValueError("duplicate ZIP member path")
        used_paths.add(folded)
        if stat.S_IFMT(item.external_attr >> 16) not in (0, stat.S_IFREG):
            raise ValueError("nonregular ZIP member")
        total += item.file_size
        extension = PurePosixPath(name).suffix.lower()
        # Inner archive non-source assets (diagrams/media) are never read or
        # exported. Permit bounded opaque media without relaxing source limits.
        member_limit = (MAX_OPAQUE_ZIP if extension == ".zip"
                        or (nested and extension not in EXTENSIONS) else MAX_MEMBER)
        if (item.file_size > member_limit or total > MAX_TOTAL or
                (item.file_size > 1024 and item.file_size > MAX_RATIO * max(item.compress_size, 1))):
            raise ValueError("oversized or high-ratio ZIP member")
    return infos



@contextmanager
def _open_stable_archive(archive: Path):
    """Hash and parse the *same* regular ZIP descriptor, never reopen its path.

    O_NOFOLLOW closes the symlink-swap window after Path.is_symlink().
    O_NONBLOCK prevents a replaced FIFO from blocking the recovery worker.
    """
    if archive.suffix.lower() != ".zip":
        raise ValueError("source must be a ZIP")
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    fd = os.open(archive, flags)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("source must be a regular ZIP")
        with os.fdopen(fd, "rb") as stream:
            fd = -1  # fdopen owns the descriptor from this point onward.
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
            stream.seek(0)
            yield stream, digest
    finally:
        if fd >= 0:
            os.close(fd)


def _inspect_nested_members(data: bytes, *, outer: str, outer_sha: str,
                            nested_path: str, nested_sha: str,
                            seen: dict[str, dict], budget: dict[str, int]) -> tuple[list[dict], list[dict]]:
    """Inventory a single bounded inner ZIP; never extract or recurse.

    The original nested ZIP bytes are already SHA-pinned by the outer reader.
    Budget is shared across all nested ZIPs in this invocation, including
    excluded/opaque entries, so adversarial archives cannot evade the cap.
    """
    results: list[dict] = []
    assets: list[dict] = []
    with zipfile.ZipFile(io.BytesIO(data)) as inner:
        infos = _validated_infos(inner, nested=True)
        budget["members"] += len(infos)
        budget["bytes"] += sum(info.file_size for info in infos)
        if budget["members"] > MAX_NESTED_MEMBERS or budget["bytes"] > MAX_NESTED_TOTAL:
            raise ValueError("nested ZIP inspection budget exceeded")
        for info in infos:
            name = info.filename
            extension = PurePosixPath(name).suffix.lower()
            if BLOCKED_NAMES.search(name):
                continue
            if extension not in EXTENSIONS and extension not in OPAQUE_METADATA_EXTENSIONS:
                continue  # Unknown binary; no source bytes or content published.
            if extension in EXTENSIONS and info.file_size > MAX_MEMBER:
                raise ValueError("oversized nested source member")
            raw = inner.read(info)  # CRC checked by zipfile; bounded by preflight.
            if len(raw) != info.file_size:
                raise ValueError("invalid nested ZIP member size")
            digest = _sha(raw)
            if extension not in EXTENSIONS:
                assets.append({
                    "archive": outer, "archive_sha256": outer_sha,
                    "nested_archive_member": nested_path,
                    "nested_archive_sha256": nested_sha,
                    "member_path": name, "member_sha256": digest,
                    "bytes": len(raw), "status": ("NESTED_ZIP_NOT_RECURSED" if extension == ".zip"
                                                else "OPAQUE_ASSET_METADATA_ONLY_NOT_PARSED"),
                    "import_authorized": False,
                })
                continue
            sensitive = bool(BLOCKED_CONTENT.search(raw))
            syntax = "not_checked"
            if extension == ".py" and not sensitive:
                try:
                    ast.parse(raw.decode("utf-8"), filename=name)
                    syntax = "parse_pass_not_completeness"
                except (SyntaxError, UnicodeError, ValueError):
                    syntax = "parse_failed"
            origin = {"archive": outer, "nested_zip": nested_path, "path": name}
            previous = seen.setdefault(digest, origin)
            results.append({
                "archive": outer, "archive_sha256": outer_sha,
                "nested_archive_member": nested_path,
                "nested_archive_sha256": nested_sha,
                "member_path": name, "member_sha256": digest,
                "bytes": len(raw), "duplicate_of": None if previous == origin else previous,
                "sensitive_pattern_detected": sensitive, "python_syntax": syntax,
                "reuse_status": "quarantine_review_required",
                "import_authorized": False,
            })
    return results, assets


def inventory(archives: list[Path], *, inspect_nested: bool = False) -> dict:
    """Read only original ZIPs, produce metadata; never export member contents."""
    if type(inspect_nested) is not bool:
        raise ValueError("inspect_nested must be boolean")
    records, seen_hashes, opaque_archives = [], {}, []
    nested_members: list[dict] = []
    nested_assets: list[dict] = []
    nested_seen: dict[str, dict] = {}
    nested_budget = {"members": 0, "bytes": 0}
    for archive in sorted(archives, key=lambda p: p.name):
        if archive.is_symlink() or not archive.is_file() or archive.suffix.lower() != ".zip":
            raise ValueError("source must be a regular ZIP, not a symlink")
        version_match = VERSION.search(archive.name)
        version = version_match.group(1).replace("_", ".") if version_match else "unknown"
        if re.fullmatch(r"213\d{1,3}", version):
            version = "2.13." + version[3:]
        with _open_stable_archive(archive) as (stream, archive_hash):
            with zipfile.ZipFile(stream) as z:
                for item in _validated_infos(z):
                    name = item.filename
                    if BLOCKED_NAMES.search(name):
                        continue
                    extension = PurePosixPath(name).suffix.lower()
                    if extension not in EXTENSIONS and extension != ".zip":
                        continue
                    data = z.read(item)
                    if len(data) != item.file_size:
                        raise ValueError("invalid ZIP member size")
                    digest = _sha(data)
                    if extension == ".zip":
                        # No nested ZIP parsing, no recursive imports, no source claim.
                        opaque_archives.append({
                            "archive": archive.name, "archive_sha256": archive_hash,
                            "member_path": name, "member_sha256": digest,
                            "bytes": len(data), "status": ("NESTED_METADATA_ONLY_INSPECTED"
                                                       if inspect_nested else "OPAQUE_NESTED_ZIP_NOT_INSPECTED"),
                            "import_authorized": False,
                        })
                        if inspect_nested:
                            if len(opaque_archives) > MAX_NESTED_ARCHIVES:
                                raise ValueError("too many nested ZIPs to inspect")
                            sources, assets = _inspect_nested_members(
                                data, outer=archive.name, outer_sha=archive_hash,
                                nested_path=name, nested_sha=digest,
                                seen=nested_seen, budget=nested_budget)
                            nested_members.extend(sources)
                            nested_assets.extend(assets)
                        continue
                    sensitive = bool(BLOCKED_CONTENT.search(data))
                    syntax = "not_checked"
                    if name.endswith(".py") and not sensitive:
                        try:
                            ast.parse(data.decode("utf-8"), filename=name)
                            syntax = "parse_pass_not_completeness"
                        except (SyntaxError, UnicodeError, ValueError):
                            syntax = "parse_failed"
                    first = seen_hashes.setdefault(digest, {"archive": archive.name, "path": name})
                    records.append({
                        "archive": archive.name, "archive_sha256": archive_hash,
                        "version": version, "member_path": name, "member_sha256": digest,
                        "bytes": len(data), "duplicate_of": None if first == {"archive": archive.name, "path": name} else first,
                        "sensitive_pattern_detected": sensitive, "python_syntax": syntax,
                        "reuse_status": "quarantine_review_required",
                    })
    return {"schema": "aiops-zip-source-inventory/v1", "runtime_attested": False,
            "complete_source_attested": False, "member_count": len(records), "members": records,
            "opaque_archive_count": len(opaque_archives), "opaque_archives": opaque_archives,
            "nested_inspection_requested": inspect_nested,
            "nested_member_count": len(nested_members), "nested_members": nested_members,
            "nested_asset_count": len(nested_assets), "nested_assets": nested_assets}


def recover(archive: Path, member: str, destination: Path, *,
            expected_archive_sha256: str, expected_member_sha256: str) -> dict:
    """Quarantine a reviewed exact member, pinned to original archive and bytes.

    SHA pins must come from a separately reviewed inventory. The archive must
    still pass all structural checks, not only checks on the selected member.
    """
    if not _safe_name(member) or BLOCKED_NAMES.search(member) or PurePosixPath(member).suffix.lower() not in EXTENSIONS:
        raise ValueError("member not eligible for quarantine")
    for digest in (expected_archive_sha256, expected_member_sha256):
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("explicit lowercase SHA-256 pins required")
    if (archive.is_symlink() or not archive.is_file() or archive.suffix.lower() != ".zip"
            or destination.is_symlink()):
        raise ValueError("regular ZIP and non-symlink quarantine required")
    with _open_stable_archive(archive) as (stream, archive_hash):
        if archive_hash != expected_archive_sha256:
            raise ValueError("archive SHA-256 differs from reviewed inventory")
        with zipfile.ZipFile(stream) as z:
            infos = [i for i in _validated_infos(z) if i.filename == member]
            if len(infos) != 1:
                raise ValueError("missing or ambiguous member")
            data = z.read(infos[0])
            if len(data) != infos[0].file_size or _sha(data) != expected_member_sha256:
                raise ValueError("member bytes differ from reviewed inventory")
    if BLOCKED_CONTENT.search(data):
        raise ValueError("sensitive-looking content requires private manual review")
    if member.endswith(".py"):
        ast.parse(data.decode("utf-8"), filename=member)
    # Destination is an existing operator-owned quarantine directory; no mkdir,
    # path traversal, symlink follow, overwrite or arbitrary absolute member path.
    if not destination.is_dir() or destination.is_symlink():
        raise ValueError("quarantine directory must exist and not be a symlink")
    rootfd = os.open(destination, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        safe_basename = _sha((archive.name + "\0" + member).encode())[:16] + "-" + PurePosixPath(member).name
        fd = os.open(safe_basename, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=rootfd)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
        except BaseException:
            os.unlink(safe_basename, dir_fd=rootfd)
            raise
    finally:
        os.close(rootfd)
    return {"quarantine_file": safe_basename, "sha256": _sha(data),
            "source_member": member, "status": "QUARANTINED_NOT_QUALIFIED"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, help="metadata-only JSON (new file only)")
    parser.add_argument("--apply", action="store_true", help="explicit extraction of exactly one member")
    parser.add_argument("--inspect-nested", action="store_true",
                        help="metadata-only one-level ZIP inspection; no extraction or recursive imports")
    parser.add_argument("--allow", help="exact ZIP member path for extraction")
    parser.add_argument("--quarantine", type=Path, help="existing empty or private quarantine directory")
    parser.add_argument("--expected-archive-sha256", help="reviewed archive digest from inventory")
    parser.add_argument("--expected-member-sha256", help="reviewed member digest from inventory")
    args = parser.parse_args()
    if args.apply:
        if args.inspect_nested:
            parser.error("--inspect-nested is inventory-only")
        if (len(args.archives) != 1 or not args.allow or args.quarantine is None or
                not args.expected_archive_sha256 or not args.expected_member_sha256):
            parser.error("--apply requires one ZIP, --allow, --quarantine and both SHA-256 pins")
        result = recover(args.archives[0], args.allow, args.quarantine,
                         expected_archive_sha256=args.expected_archive_sha256,
                         expected_member_sha256=args.expected_member_sha256)
    else:
        if args.allow or args.quarantine or args.expected_archive_sha256 or args.expected_member_sha256:
            parser.error("extraction options and SHA-256 pins require --apply")
        result = inventory(args.archives, inspect_nested=args.inspect_nested)
    encoded = json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(encoded)
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
