"""Offline, fail-closed STAR capture-to-event time audit.

Requires independent, operator-supplied event anchors. Validates existing PNG
integrity via the manifest bridge; never authenticates event logs, browser
sessions, HITL decisions, business resolution or live remediation.
No network calls, runtime access, imports or service modifications.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence
import json
import re

from demo.star_browser_manifest_gate import verify_browser_manifests
from demo.star_capture_identity_guard import verify_snapshot_identity
from demo.star_snapshot_choreography import CUE_BY_NAME

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_ANCHOR_FIELDS = frozenset({"run_id", "correlation_id", "event_ref", "event_at", "source_kind", "source_sha256"})
_PROVENANCE = {
    "ISOLATED_TEST_FIXTURE": "ISOLATED_FIXTURE_EVENT",
    "OPERATOR_BROWSER_UNREVIEWED": "OPERATOR_EVENT_LOG_UNREVIEWED",
}


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    obj: dict[str, object] = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate evidence JSON key")
        obj[key] = value
    return obj


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("invalid event timestamp")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid event timestamp") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("event timestamp requires timezone")
    return result


def _read_manifest(root: Path, name: str) -> dict[str, object]:
    # File name and symlink constraints are also enforced by the bridge.
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\.json", name):
        raise ValueError("unsafe manifest filename")
    path = root / name
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16384:
        raise ValueError("unsafe manifest file")
    item = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    if not isinstance(item, dict):
        raise ValueError("invalid manifest object")
    return item


def verify_event_capture_alignment(
    root: Path,
    expected: Mapping[str, object],
    filenames: Sequence[str],
    anchors: Mapping[str, object],
    *,
    max_delay_seconds: int = 120,
    clock_skew_seconds: int = 3,
) -> dict[str, object]:
    """Compare independent event times to integrity-checked browser captures.

    An anchor's source digest is *declared*, not verified against an event log.
    Results are always UNAUTHENTICATED and cannot be used as HITL approval.
    """
    if (type(max_delay_seconds) is not int or not 1 <= max_delay_seconds <= 3600
            or type(clock_skew_seconds) is not int or not 0 <= clock_skew_seconds <= 10):
        raise ValueError("invalid time tolerance")
    if not isinstance(filenames, (tuple, list)) or not filenames:
        raise ValueError("no capture manifests")
    if not isinstance(anchors, Mapping):
        raise ValueError("independent event anchors required")
    # Validate canonical IDs, service/view, PNG SHA/CRC, duplicate images,
    # manifest schema and monotonic capture order before time checks.
    report = verify_browser_manifests(root, expected, filenames)
    manifests = [_read_manifest(root, name) for name in filenames]
    cues = {item["cue"] for item in manifests}
    if set(anchors) != cues:
        raise ValueError("one independent event anchor per captured cue required")
    canonical = expected.get("events")
    if not isinstance(canonical, Mapping):
        raise ValueError("canonical event references required")
    results: dict[str, dict[str, object]] = {}
    for item in manifests:
        cue = item["cue"]
        anchor = anchors[cue]
        if not isinstance(anchor, Mapping) or set(anchor) != _ANCHOR_FIELDS:
            raise ValueError("invalid independent event anchor schema")
        if cue not in CUE_BY_NAME:
            raise ValueError("unknown STAR cue")
        verify_snapshot_identity(
            {"run_id": expected.get("run_id"), "correlation_id": expected.get("correlation_id"),
             "event_ref": canonical[cue]},
            {"run_id": anchor["run_id"], "correlation_id": anchor["correlation_id"],
             "event_ref": anchor["event_ref"]},
        )
        if anchor["source_kind"] != _PROVENANCE.get(item["provenance"]):
            raise ValueError("anchor provenance contradicts capture provenance")
        digest = anchor["source_sha256"]
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise ValueError("invalid independent event source digest")
        event_at = _timestamp(anchor["event_at"])
        captured_at = _timestamp(item["captured_at"])
        lag = (captured_at - event_at).total_seconds()
        if not -clock_skew_seconds <= lag <= max_delay_seconds:
            raise ValueError("capture outside independently declared event window")
        results[cue] = {
            "cue": cue,
            "time_window": "CONSISTENT_UNAUTHENTICATED",
            "lag_seconds": round(lag, 3),
            "provenance": "SYNTHETIC" if item["provenance"] == "ISOLATED_TEST_FIXTURE" else "OPERATOR_UNREVIEWED",
            "event_source_digest_verified": False,
            "runtime_authenticated": False,
            "business_validated": False,
        }
    return {
        "schema": "star-event-capture-alignment/v1",
        "run_id": report["run_id"],
        "entries": [results[cue.cue] for cue in CUE_BY_NAME.values() if cue.cue in results],
        "alignment": "CONSISTENT_UNAUTHENTICATED",
        "independent_event_source_authenticated": False,
        "runtime_authenticated": False,
        "human_approval_authenticated": False,
        "business_validated": False,
        "live_remediation_authorized": False,
    }
