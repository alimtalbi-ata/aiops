#!/usr/bin/env python3
"""Offline integrity audit for a five-view Evidence Studio bundle.

Hashes attest local bytes only. No browser, network, runtime identity, or LIVE
state is authenticated. This is NOT a video codec or privacy-content audit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys

from demo.evidence_video import SERVICES, verify
from demo.evidence_video_bundle import IDENT, NAMES, subtitles as canonical_subtitles

SHA256 = re.compile(r"^[0-9a-f]{64}$")
RECEIPT_KEYS = {"schema_version", "provenance", "runtime_authenticated",
                "production_qualified", "capture_count", "correlation",
                "captures", "video", "subtitles"}


def _unique(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate JSON key")
        obj[key] = value
    return obj


def _private_directory(path: Path) -> None:
    if path.is_symlink() or not path.is_dir() or stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError("private non-symlink bundle directory required (chmod 700)")


def _read_stable(path: Path, limit: int) -> bytes:
    """Open without following a final symlink and reject unstable/unsafe bytes."""
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow:
        raise ValueError("O_NOFOLLOW required")
    with os.fdopen(os.open(path, os.O_RDONLY | nofollow | getattr(os, "O_NONBLOCK", 0)), "rb") as src:
        before = os.fstat(src.fileno())
        if not stat.S_ISREG(before.st_mode) or not 1 <= before.st_size <= limit:
            raise ValueError("bounded regular file required")
        digest = src.read(limit + 1)
        after = os.fstat(src.fileno())
        if (len(digest) != before.st_size or
                (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) !=
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
            raise ValueError("file changed during audit")
    current = path.lstat()
    if not stat.S_ISREG(current.st_mode) or (current.st_dev, current.st_ino) != (after.st_dev, after.st_ino):
        raise ValueError("file replaced during audit")
    return digest


def _hash_file(root: Path, name: str, digest: str, limit: int) -> None:
    if not isinstance(digest, str) or not SHA256.fullmatch(digest):
        raise ValueError("invalid SHA-256 digest")
    data = _read_stable(root / name, limit)
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("bundle byte hash mismatch: " + name)
    return data


def audit_bundle(bundle_dir: Path, capture_root: Path) -> dict:
    """Verify receipt structure and local bytes; never elevate provenance."""
    bundle_dir, capture_root = Path(bundle_dir), Path(capture_root)
    _private_directory(bundle_dir)
    if capture_root.is_symlink() or not capture_root.is_dir():
        raise ValueError("real capture directory required")
    raw = _read_stable(bundle_dir / NAMES[2], 256 * 1024)
    receipt = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)
    if not isinstance(receipt, dict) or set(receipt) != RECEIPT_KEYS:
        raise ValueError("invalid receipt structure")
    if (type(receipt["schema_version"]) is not int or receipt["schema_version"] != 1
            or receipt["provenance"] != "OPERATOR_SUPPLIED_UNATTESTED"
            or receipt["runtime_authenticated"] is not False
            or receipt["production_qualified"] is not False
            or type(receipt["capture_count"]) is not int or receipt["capture_count"] != 5):
        raise ValueError("unsafe receipt provenance or count")
    correlation = receipt["correlation"]
    if (not isinstance(correlation, dict) or
            set(correlation) != {"run_id", "incident_id", "ticket_id", "session_label"} or
            any(not isinstance(value, str) or not IDENT.fullmatch(value)
                for value in correlation.values())):
        raise ValueError("invalid correlation metadata")
    captures = receipt["captures"]
    if not isinstance(captures, list) or [x.get("service") for x in captures if isinstance(x, dict)] != list(SERVICES):
        raise ValueError("noncanonical capture order")
    # The original verifier checks PNG framing/decoded scanlines, SHA, UTC,
    # source URL and all five distinct services; the receipt may not add claims.
    if verify(capture_root, {"schema_version": 1,
                             "provenance": "OPERATOR_SUPPLIED_UNATTESTED",
                             "captures": captures}) != captures:
        raise ValueError("noncanonical capture receipt")
    video, subtitles = receipt["video"], receipt["subtitles"]
    if (not isinstance(video, dict) or
            set(video) != {"file", "sha256", "duration_seconds", "codec", "resolution"} or
            video["file"] != NAMES[0] or video["codec"] != "h264" or
            video["resolution"] != "1920x1080" or
            type(video["duration_seconds"]) not in (int, float) or
            not math.isfinite(video["duration_seconds"]) or
            not 10 <= video["duration_seconds"] <= 100):
        raise ValueError("invalid video receipt metadata")
    if (not isinstance(subtitles, dict) or
            set(subtitles) != {"file", "sha256"} or subtitles["file"] != NAMES[1]):
        raise ValueError("invalid subtitles receipt metadata")
    # SRT is generated from fixed labels, not operator text. A matching hash
    # alone cannot prevent a forged receipt from laundering sensitive captions.
    duration = video["duration_seconds"]
    scene_seconds = round(duration / len(SERVICES))
    if not 2 <= scene_seconds <= 20 or abs(duration - len(SERVICES) * scene_seconds) > 0.25:
        raise ValueError("video duration is inconsistent with five canonical scenes")
    _hash_file(bundle_dir, NAMES[0], video["sha256"], 512 * 1024 * 1024)
    srt_bytes = _hash_file(bundle_dir, NAMES[1], subtitles["sha256"], 256 * 1024)
    if srt_bytes != canonical_subtitles(captures, scene_seconds).encode("utf-8"):
        raise ValueError("noncanonical subtitles: content or timing mismatch")
    return {"status": "LOCAL_BYTES_VERIFIED_UNATTESTED",
            "capture_count": 5, "video_sha256": video["sha256"],
            "subtitles_sha256": subtitles["sha256"],
            "media_decoded_by_auditor": False,
            "runtime_authenticated": False, "production_qualified": False,
            "live_action_authorized": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--capture-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(audit_bundle(args.bundle_dir, args.capture_root), indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, json.JSONDecodeError) as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
