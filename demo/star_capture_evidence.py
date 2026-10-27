"""Offline, fail-closed evidence ingestion for STAR demo screenshots.

No browser automation, HTTP, Docker, credential access, or application mutation.
The operator captures PNGs separately; this module verifies bytes, identity and
chronology before producing a manifest explicitly NOT claiming runtime approval.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from datetime import datetime
from pathlib import Path
from typing import Mapping

from demo.star_snapshot_choreography import CUE_BY_NAME, validate_capture
from demo.star_png_integrity import inspect_png

HEX64 = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,95}$")
MAX_MANIFEST_BYTES = 300_000


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject ambiguous duplicate keys at every nesting level."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate evidence manifest JSON key")
        result[key] = value
    return result


def _read_manifest_bytes(path: Path) -> bytes:
    """Read bounded manifest bytes from one stable, no-follow descriptor.

    On platforms without a working O_NOFOLLOW primitive, fail closed rather
    than silently falling back to a pathname check susceptible to a swap race.
    """
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if not isinstance(nofollow, int) or nofollow == 0:
        raise ValueError("safe manifest descriptor reads unavailable")
    fd = None
    try:
        if path.is_symlink():
            raise ValueError("manifest symlink refused")
        flags = (os.O_RDONLY | nofollow
                 | getattr(os, "O_CLOEXEC", 0)
                 | getattr(os, "O_NONBLOCK", 0))
        fd = os.open(path, flags)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("evidence manifest must be a regular file")
        if before.st_size < 0 or before.st_size > MAX_MANIFEST_BYTES:
            raise ValueError("manifest too large")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(MAX_MANIFEST_BYTES + 1)
        after = os.fstat(fd)
        before_state = (before.st_dev, before.st_ino, before.st_mode, before.st_size,
                        before.st_mtime_ns, before.st_ctime_ns)
        after_state = (after.st_dev, after.st_ino, after.st_mode, after.st_size,
                       after.st_mtime_ns, after.st_ctime_ns)
        if before_state != after_state or len(raw) != after.st_size:
            raise ValueError("manifest changed during read")
        if len(raw) > MAX_MANIFEST_BYTES:
            raise ValueError("manifest too large")
        return raw
    except ValueError:
        raise
    except OSError as exc:
        raise ValueError("cannot read evidence manifest (" + type(exc).__name__ + ")") from exc
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass


def _contained_file(evidence_root: Path, relative_path: str) -> Path:
    """Resolve a capture only after rejecting symlinks in every path component."""
    if (not isinstance(relative_path, str) or not relative_path.startswith("evidence/")
            or "\\" in relative_path or "\x00" in relative_path):
        raise ValueError("evidence path required")
    parts = relative_path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("invalid evidence-relative path")
    try:
        base = evidence_root.resolve(strict=True)
        candidate = base.joinpath(*parts)
        current = base
        for part in parts:
            current = current / part
            if stat.S_ISLNK(current.lstat().st_mode):
                raise ValueError("capture symlink is forbidden")
        target = candidate.resolve(strict=True)
        if (target != candidate or not target.is_relative_to(base)
                or not stat.S_ISREG(target.stat().st_mode)):
            raise ValueError("capture escaped evidence root or is not a regular file")
        return target
    except ValueError:
        raise
    except OSError:
        raise ValueError("capture path cannot be opened safely") from None

def verify_manifest(
    evidence_root: Path,
    run_id: str,
    capture_records: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Check screenshots against their timeline cues and a single run identity.

    A successful check is an *integrity check*, not authentication that an
    external application was genuinely observed or an action authorized.
    """
    if not isinstance(run_id, str) or not SAFE_ID.fullmatch(run_id):
        raise ValueError("invalid canonical run ID")
    if not isinstance(capture_records, Mapping):
        raise ValueError("capture records must be an object")
    if any(not isinstance(name, str) for name in capture_records):
        raise ValueError("capture cue names must be strings")
    if any(not isinstance(record, Mapping) for record in capture_records.values()):
        raise ValueError("capture record must be an object")
    unknown = set(capture_records) - set(CUE_BY_NAME)
    if unknown:
        raise ValueError("unrecognized STAR cue")
    entries = []
    previous = None
    seen_digests: set[str] = set()
    for cue_name, cue in CUE_BY_NAME.items():
        record = capture_records.get(cue_name)
        if record is None:
            entries.append({"cue": cue_name, "status": "missing"})
            continue
        if record.get("run_id") != run_id:
            raise ValueError("cross-run capture blocked")
        meta = validate_capture(cue_name, record)
        if not meta["metadata_complete"]:
            entries.append({"cue": cue_name, "status": meta["proof_state"]})
            continue
        path = _contained_file(evidence_root, str(record["screenshot_path"]))
        actual_digest, size = inspect_png(path)
        declared_digest = record["sha256"]
        if not isinstance(declared_digest, str) or not HEX64.fullmatch(declared_digest):
            raise ValueError("invalid expected SHA")
        if actual_digest != declared_digest:
            raise ValueError("screenshot hash mismatch")
        # Two distinct STAR scenes cannot be substantiated by identical PNG
        # bytes, even if both records carry a valid SHA-256. This catches
        # accidental replay/relabeling of the same image across applications.
        if actual_digest in seen_digests:
            raise ValueError("screenshot reused across STAR cues")
        seen_digests.add(actual_digest)
        captured = datetime.fromisoformat(str(record["captured_at"]).replace("Z", "+00:00"))
        if previous is not None and captured < previous:
            raise ValueError("nonmonotonic capture timeline")
        previous = captured
        entries.append({
            "cue": cue_name, "status": "integrity_checked",
            "sha256": actual_digest, "bytes": size,
            "captured_at": captured.isoformat(),
            "view": cue.view,
        })
    return {
        "schema": "star-capture-evidence-v1",
        "run_id": run_id,
        "entries": entries,
        "integrity_checked": all(e["status"] == "integrity_checked" for e in entries),
        "runtime_authenticated": False,
        "business_validated": False,
        "human_approval_authenticated": False,
        "live_action_authorized": False,
    }

def verify_file(manifest_path: Path, root: Path) -> dict[str, object]:
    """Read untrusted manifest bytes once and return only a sanitized summary."""
    raw = _read_manifest_bytes(manifest_path)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("manifest must be UTF-8") from exc
    try:
        data = json.loads(text, object_pairs_hook=_unique_json_object)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid evidence manifest JSON") from exc
    if not isinstance(data, dict) or not isinstance(data.get("captures"), dict):
        raise ValueError("invalid manifest schema")
    return verify_manifest(root, data.get("run_id"), data["captures"])

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify_file(args.manifest, args.root), indent=2, ensure_ascii=False))
