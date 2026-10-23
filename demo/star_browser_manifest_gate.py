"""Offline bridge: Chromium capture manifests -> STAR portal storyboard contract.

Pure local integrity checking. Never authenticates runtime, HITL, or business success.
Expected IDs MUST originate independently from canonical ingress, not manifests.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence

from demo.star_capture_identity_guard import verify_snapshot_identity
from demo.star_png_integrity import inspect_png
from demo.star_snapshot_choreography import CUES, CUE_BY_NAME

_BASENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\.(?:json|png)$")
_SHA = re.compile(r"^[a-f0-9]{64}$")
_ALLOWED_PROVENANCE = {"ISOLATED_TEST_FIXTURE", "OPERATOR_BROWSER_UNREVIEWED"}
_FORBIDDEN = {"runtime_authenticated", "runtime_page_authenticated", "business_validated",
              "business_outcome_verified", "human_approval_authenticated", "live_action_authorized",
              "remediation_executed", "release_promotable", "verified_real_capture", "claim_real"}


def _file(root: Path, name: str, extension: str) -> Path:
    if not isinstance(name, str) or not _BASENAME.fullmatch(name) or not name.endswith(extension):
        raise ValueError("unsafe evidence filename")
    path = root / name
    if path.is_symlink() or not path.is_file() or path.resolve(strict=True).parent != root.resolve(strict=True):
        raise ValueError("evidence path escaped or missing")
    return path


def verify_browser_manifests(root: Path, expected: Mapping[str, object],
                             filenames: Sequence[str]) -> dict[str, object]:
    """Return a sanitized storyboard-compatible report with no URLs or secrets."""
    run_id, correlation_id, refs = expected.get("run_id"), expected.get("correlation_id"), expected.get("events")
    if not isinstance(refs, dict) or not refs or set(refs) - set(CUE_BY_NAME):
        raise ValueError("canonical event references missing or unknown")
    if not isinstance(filenames, (list, tuple)) or len(filenames) > len(CUES) or len(set(filenames)) != len(filenames):
        raise ValueError("duplicate or excessive manifest files")
    if not root.is_dir() or root.is_symlink():
        raise ValueError("unsafe evidence root")
    entries: dict[str, dict[str, object]] = {}
    hashes: set[str] = set()
    for name in filenames:
        manifest_file = _file(root, name, ".json")
        if manifest_file.stat().st_size > 16_384:
            raise ValueError("oversized capture manifest")
        item = json.loads(manifest_file.read_text(encoding="utf-8"))
        if not isinstance(item, dict) or item.get("schema") != "star-browser-evidence/v1":
            raise ValueError("invalid Chromium manifest schema")
        if any(item.get(k) not in (None, False) for k in _FORBIDDEN):
            raise ValueError("untrusted browser manifest claims authority")
        cue_name = item.get("cue")
        cue = CUE_BY_NAME.get(cue_name)
        if cue is None or cue_name in entries or cue_name not in refs:
            raise ValueError("unknown, duplicate or unrequested STAR cue")
        if item.get("service") != cue.service or item.get("view") != cue.view:
            raise ValueError("wrong application view")
        verify_snapshot_identity(
            {"run_id": run_id, "correlation_id": correlation_id, "event_ref": refs[cue_name]},
            {"run_id": item.get("run_id"), "correlation_id": item.get("correlation_id"),
             "event_ref": item.get("event_ref")},
        )
        if item.get("expected_state") != cue.required_state or item.get("observed_state") != cue.required_state:
            raise ValueError("observed state differs from STAR cue")
        provenance = item.get("provenance")
        if provenance not in _ALLOWED_PROVENANCE:
            raise ValueError("unrecognized screenshot provenance")
        if item.get("capture_transport") != ("LOCAL_HTML_FIXTURE_NO_HTTP" if provenance == "ISOLATED_TEST_FIXTURE" else "READ_ONLY_BROWSER_HTTP_GET"):
            raise ValueError("provenance and transport contradict")
        if item.get("anonymization") != "SELECTOR_MASKS_UNREVIEWED" or item.get("qualification") != "CAPTURED_UNREVIEWED_NOT_BUSINESS_PROOF":
            raise ValueError("unsupported anonymization/qualification contract")
        digest = item.get("sha256")
        if not isinstance(digest, str) or not _SHA.fullmatch(digest):
            raise ValueError("invalid capture digest")
        png = _file(root, item.get("screenshot_file"), ".png")
        actual, size = inspect_png(png)
        if actual != digest or actual in hashes:
            raise ValueError("screenshot hash mismatch or reuse")
        hashes.add(actual)
        try:
            captured = datetime.fromisoformat(item["captured_at"].replace("Z", "+00:00"))
        except (ValueError, KeyError, AttributeError) as exc:
            raise ValueError("invalid capture timestamp") from exc
        if captured.tzinfo is None or captured.utcoffset() is None:
            raise ValueError("capture timestamp lacks timezone")
        entries[cue_name] = {"cue": cue_name,
                             "status": "simulated" if provenance == "ISOLATED_TEST_FIXTURE" else "integrity_checked",
                             "view": cue.view, "sha256": actual, "bytes": size,
                             "captured_at": captured.isoformat()}
    ordered = [entries.get(c.cue, {"cue": c.cue, "status": "missing"}) for c in CUES]
    timestamps = [datetime.fromisoformat(e["captured_at"]) for e in ordered if "captured_at" in e]
    if timestamps != sorted(timestamps):
        raise ValueError("capture chronology contradicted")
    return {"schema": "star-capture-evidence-v1", "run_id": run_id, "entries": ordered,
            "integrity_checked": all(e["status"] == "integrity_checked" for e in ordered),
            "runtime_authenticated": False, "business_validated": False,
            "human_approval_authenticated": False, "live_action_authorized": False}
