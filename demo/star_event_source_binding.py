"""Offline binding of STAR event anchors to actual, untrusted event-log bytes.

Read-only; does not contact Grafana, n8n, GLPI or Debian. A matching SHA256
proves local byte consistency, not that an event log came from a real system.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Mapping, Sequence

from demo.star_event_capture_alignment import _timestamp, verify_event_capture_alignment
from demo.star_snapshot_choreography import CUE_BY_NAME

_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\.json\Z")
_EVENT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}\Z")
_FIELDS = frozenset({
    "schema", "cue", "service", "view", "run_id", "correlation_id",
    "event_ref", "event_at", "source_kind", "observed_state", "source_event_id",
})
_LIMIT = 65536


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    out: dict[str, object] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate event-source JSON key")
        out[key] = value
    return out


def _read_source_bytes(root: Path, filename: str) -> bytes:
    """Open only a regular file in a real events/ directory, without symlinks."""
    if not isinstance(filename, str) or not _NAME.fullmatch(filename):
        raise ValueError("unsafe event-source filename")
    if not root.is_dir() or root.is_symlink():
        raise ValueError("unsafe evidence root")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    dirflags = flags | getattr(os, "O_DIRECTORY", 0)
    directory = root / "events"
    if directory.is_symlink():
        raise ValueError("event-source directory symlink forbidden")
    dir_fd = os.open(directory, dirflags)
    try:
        if not stat.S_ISDIR(os.fstat(dir_fd).st_mode):
            raise ValueError("event-source directory is not a directory")
        fd = os.open(filename, flags | getattr(os, "O_NONBLOCK", 0), dir_fd=dir_fd)
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or not 0 < st.st_size <= _LIMIT:
                raise ValueError("unsafe or oversized event-source file")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                data = stream.read(_LIMIT + 1)
            if len(data) != st.st_size or len(data) > _LIMIT:
                raise ValueError("event-source changed during read")
            return data
        finally:
            os.close(fd)
    finally:
        os.close(dir_fd)


def verify_event_source_binding(
    root: Path,
    expected: Mapping[str, object],
    manifest_names: Sequence[str],
    anchors: Mapping[str, object],
    source_files: Mapping[str, str],
    *,
    max_delay_seconds: int = 120,
    clock_skew_seconds: int = 3,
) -> dict[str, object]:
    """Verify captured PNGs, event windows, and independent source-file bytes.

    Every cue requires a distinct local event-source JSON. Source bytes must
    match the declared SHA and the exact canonical run/event/state. Neither
    the source nor the screenshot is authenticated as a production observation.
    """
    base = verify_event_capture_alignment(
        root, expected, manifest_names, anchors,
        max_delay_seconds=max_delay_seconds, clock_skew_seconds=clock_skew_seconds,
    )
    cues = {entry["cue"] for entry in base["entries"]}
    if not isinstance(source_files, Mapping) or set(source_files) != cues:
        raise ValueError("one event-source file per captured cue required")
    filenames = list(source_files.values())
    if any(not isinstance(name, str) for name in filenames) or len(set(filenames)) != len(filenames):
        raise ValueError("duplicate event-source file")
    hashes: set[str] = set()
    results = []
    for entry in base["entries"]:
        cue_name = entry["cue"]
        cue = CUE_BY_NAME[cue_name]
        anchor = anchors[cue_name]
        data = _read_source_bytes(root, source_files[cue_name])
        digest = hashlib.sha256(data).hexdigest()
        if digest != anchor["source_sha256"] or digest in hashes:
            raise ValueError("event-source SHA mismatch or reuse")
        hashes.add(digest)
        try:
            item = json.loads(data.decode("utf-8"), object_pairs_hook=_unique)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid event-source JSON") from exc
        if not isinstance(item, dict) or set(item) != _FIELDS or item["schema"] != "star-event-source/v1":
            raise ValueError("invalid event-source schema")
        if item["cue"] != cue_name or item["service"] != cue.service or item["view"] != cue.view:
            raise ValueError("event-source application or scene mismatch")
        if item["observed_state"] != cue.required_state:
            raise ValueError("event-source state mismatch")
        if not isinstance(item["source_event_id"], str) or not _EVENT_ID.fullmatch(item["source_event_id"]):
            raise ValueError("invalid event-source event ID")
        for key in ("run_id", "correlation_id", "event_ref", "source_kind"):
            if item[key] != anchor[key]:
                raise ValueError("event-source identity/provenance mismatch")
        if _timestamp(item["event_at"]) != _timestamp(anchor["event_at"]):
            raise ValueError("event-source timestamp mismatch")
        results.append({
            "cue": cue_name, "source_bytes_sha256_verified": True,
            "source_sha256": digest, "event_source_authenticated": False,
            "runtime_authenticated": False, "business_validated": False,
        })
    return {
        "schema": "star-event-source-binding/v1", "run_id": base["run_id"],
        "alignment": base["alignment"], "entries": results,
        "event_source_bytes_verified": True,
        "independent_event_source_authenticated": False,
        "runtime_authenticated": False, "human_approval_authenticated": False,
        "business_validated": False, "live_remediation_authorized": False,
    }
