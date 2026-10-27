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
    """Read one bounded event file through pinned directory descriptors.

    Require no-follow directory-relative primitives rather than silently
    weakening the trust boundary on platforms that do not provide them.
    """
    if not isinstance(filename, str) or not _NAME.fullmatch(filename):
        raise ValueError("unsafe event-source filename")

    nofollow = getattr(os, "O_NOFOLLOW", None)
    if not isinstance(nofollow, int) or nofollow == 0:
        raise ValueError("safe event-source open unavailable without O_NOFOLLOW")
    directory_flag = getattr(os, "O_DIRECTORY", None)
    if not isinstance(directory_flag, int) or directory_flag == 0:
        raise ValueError("safe directory open unavailable without O_DIRECTORY")
    dir_fd_support = getattr(os, "supports_dir_fd", None)
    if dir_fd_support is None or os.open not in dir_fd_support:
        raise ValueError("safe directory-relative open support unavailable")

    extra_flags = 0
    for name in ("O_CLOEXEC", "O_NONBLOCK", "O_BINARY"):
        value = getattr(os, name, 0)
        if isinstance(value, int):
            extra_flags |= value
    file_flags = os.O_RDONLY | nofollow | extra_flags
    directory_flags = file_flags | directory_flag

    root_fd = None
    events_fd = None
    file_fd = None
    try:
        # Once opened, all child lookups are anchored to these descriptors.
        # O_NOFOLLOW rejects root/events/file symlink final components.
        root_fd = os.open(root, directory_flags)
        if not stat.S_ISDIR(os.fstat(root_fd).st_mode):
            raise ValueError("evidence root must be a directory")

        events_fd = os.open("events", directory_flags, dir_fd=root_fd)
        if not stat.S_ISDIR(os.fstat(events_fd).st_mode):
            raise ValueError("event-source directory must be a directory")

        file_fd = os.open(filename, file_flags, dir_fd=events_fd)
        before = os.fstat(file_fd)
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= _LIMIT:
            raise ValueError("unsafe or oversized event-source file")

        with os.fdopen(file_fd, "rb", closefd=False) as stream:
            data = stream.read(_LIMIT + 1)

        after = os.fstat(file_fd)
        before_state = (
            before.st_dev, before.st_ino, before.st_mode, before.st_size,
            before.st_mtime_ns, before.st_ctime_ns,
        )
        after_state = (
            after.st_dev, after.st_ino, after.st_mode, after.st_size,
            after.st_mtime_ns, after.st_ctime_ns,
        )
        if (before_state != after_state or len(data) != after.st_size
                or len(data) > _LIMIT):
            raise ValueError("event-source changed during read")
        return data
    except ValueError:
        raise
    except OSError as exc:
        raise ValueError("event-source path or symlink cannot be opened safely") from exc
    finally:
        for descriptor in (file_fd, events_fd, root_fd):
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass

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
