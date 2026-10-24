"""Fail-closed offline gate for a replay pinned to an independent capture-set SHA.

This validates PNG bytes and identity through the existing manifest gate. It
cannot authenticate a runtime application, user session, or business outcome.
"""
from __future__ import annotations

import hmac
import re
from pathlib import Path
from typing import Mapping, Sequence

from demo.star_browser_manifest_gate import verify_browser_manifests

_SHA256 = re.compile(r"[a-f0-9]{64}\Z")


def verify_pinned_replay_captures(
    root: Path,
    canonical: Mapping[str, object],
    filenames: Sequence[str],
    pinned_sha256: str,
    *,
    allow_synthetic_fixture: bool = False,
) -> dict[str, object]:
    """Refuse incomplete, unpinned, mixed-source or altered replay capture sets.

    pinned_sha256 MUST come from a separately retained, trusted replay record;
    deriving it from the same manifest set defeats the independent pin.
    No network or write operations occur here.
    """
    if not isinstance(pinned_sha256, str) or not _SHA256.fullmatch(pinned_sha256):
        raise ValueError("invalid independently pinned capture-set SHA-256")
    if type(allow_synthetic_fixture) is not bool:
        raise ValueError("invalid fixture authorization")
    report = verify_browser_manifests(root, canonical, filenames, require_complete=True)
    digest = report.get("capture_set_sha256")
    if not isinstance(digest, str) or not hmac.compare_digest(digest, pinned_sha256):
        raise ValueError("capture set differs from pinned replay evidence")
    entries = report.get("entries")
    if not isinstance(entries, list) or len(entries) != 9:
        raise ValueError("incomplete replay capture set")
    statuses = {entry.get("status") for entry in entries if isinstance(entry, dict)}
    if len(statuses) != 1 or not statuses <= {"simulated", "integrity_checked"}:
        raise ValueError("mixed or unknown capture provenance")
    source = next(iter(statuses))
    if source == "simulated" and not allow_synthetic_fixture:
        raise ValueError("synthetic fixture not authorized for this replay")
    return {
        "schema": "star-pinned-replay-captures/v1",
        "run_id": report["run_id"],
        "capture_set_sha256": digest,
        "provenance": "ISOLATED_TEST_FIXTURE" if source == "simulated" else "OPERATOR_BROWSER_UNREVIEWED",
        "replay_integrity_checked": True,
        "runtime_authenticated": False,
        "business_validated": False,
        "human_approval_authenticated": False,
        "live_action_authorized": False,
    }
