"""Offline bridge: Chromium capture manifests -> STAR portal storyboard contract.

Pure local integrity checking. Never authenticates runtime, HITL, or business success.
Expected IDs MUST originate independently from canonical ingress, not manifests.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence

from demo.star_capture_identity_guard import verify_snapshot_identity
from demo.star_png_integrity import inspect_png
from demo.star_snapshot_choreography import CUES, CUE_BY_NAME
from demo.star_checkpoint_reconciliation import reconcile_checkpoints

_BASENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\.(?:json|png)$")
_SHA = re.compile(r"^[a-f0-9]{64}$")
_ALLOWED_PROVENANCE = {"ISOLATED_TEST_FIXTURE", "OPERATOR_BROWSER_UNREVIEWED"}
# Strict schema: unexpected metadata can conceal secrets or forge attestations.
_ALLOWED_FIELDS = frozenset({
    "schema", "cue", "service", "view", "run_id", "correlation_id", "event_ref",
    "expected_state", "observed_state", "captured_at", "sha256", "screenshot_file",
    "provenance", "capture_transport", "anonymization", "qualification",
    "source_url_redacted", "event_time_alignment", "runtime_page_authenticated",
    "business_outcome_verified", "human_approval_authenticated",
})
_REDACTED_ROUTE_BY_SERVICE = {
    "glpi": "{origin}/front/ticket.form.php?{id_redacted}",
    "n8n": "{origin}/{workflow_route_redacted}/executions/{event_ref}",
    "grafana": "{origin}/d/{dashboard_uid}/{slug_redacted}",
}
_TIME_UNVERIFIED = "UNVERIFIED_REQUIRES_EXTERNAL_EVENT_TIMESTAMP"


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject duplicate keys instead of trusting JSON's last-key-wins behavior."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate capture manifest JSON key")
        result[key] = value
    return result
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
                             filenames: Sequence[str], *, require_complete: bool = False,
                             include_manifest_digests: bool = False) -> dict[str, object]:
    """Return a sanitized storyboard-compatible report with no URLs or secrets."""
    if type(include_manifest_digests) is not bool:
        raise ValueError("invalid manifest digest mode")
    run_id, correlation_id, refs = expected.get("run_id"), expected.get("correlation_id"), expected.get("events")
    if not isinstance(refs, dict) or not refs or set(refs) - set(CUE_BY_NAME):
        raise ValueError("canonical event references missing or unknown")
    if not isinstance(filenames, (list, tuple)) or len(filenames) > len(CUES) or len(set(filenames)) != len(filenames):
        raise ValueError("duplicate or excessive manifest files")
    if not root.is_dir() or root.is_symlink():
        raise ValueError("unsafe evidence root")
    if require_complete and (set(refs) != set(CUE_BY_NAME) or len(filenames) != len(CUES)):
        raise ValueError("complete STAR capture requires all canonical checkpoints")
    entries: dict[str, dict[str, object]] = {}
    validated_captures: list[dict[str, object]] = []
    hashes: set[str] = set()
    for name in filenames:
        manifest_file = _file(root, name, ".json")
        if manifest_file.stat().st_size > 16_384:
            raise ValueError("oversized capture manifest")
        # Hash the exact bytes parsed, not a later second read of a mutable path.
        manifest_bytes = manifest_file.read_bytes()
        if len(manifest_bytes) > 16_384:
            raise ValueError("oversized capture manifest")
        item = json.loads(manifest_bytes.decode("utf-8"),
                          object_pairs_hook=_unique_json_object)
        if not isinstance(item, dict) or item.get("schema") != "star-browser-evidence/v1":
            raise ValueError("invalid Chromium manifest schema")
        if set(item) - _ALLOWED_FIELDS:
            raise ValueError("unexpected capture metadata fields")
        # Both fields are mandatory: absence must not bypass the trust boundary.
        # A valid route from another service is still the WRONG application page.
        if item.get("source_url_redacted") != _REDACTED_ROUTE_BY_SERVICE.get(item.get("service")):
            raise ValueError("missing, unsafe or cross-service capture route")
        if item.get("event_time_alignment") != _TIME_UNVERIFIED:
            raise ValueError("missing or falsely attested event time alignment")
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
        if require_complete:
            validated_captures.append({key: item.get(key) for key in (
                "cue", "run_id", "correlation_id", "event_ref", "sha256",
                "provenance", "qualification", "runtime_page_authenticated",
                "business_outcome_verified", "human_approval_authenticated")})
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
        if include_manifest_digests:
            # Additional read-consistency marker for the event-alignment gate.
            # Not included in capture_set_sha256, preserving replay pins.
            entries[cue_name]["manifest_sha256"] = hashlib.sha256(manifest_bytes).hexdigest()
    ordered = [entries.get(c.cue, {"cue": c.cue, "status": "missing"}) for c in CUES]
    timestamps = [datetime.fromisoformat(e["captured_at"]) for e in ordered if "captured_at" in e]
    if timestamps != sorted(timestamps):
        raise ValueError("capture chronology contradicted")
    capture_set_sha256 = None
    if require_complete:
        # Only after PNG-byte verification, independent identity checks and
        # full nine-cue coverage. This binds an offline replay to a fixed
        # capture set; it does NOT authenticate the underlying application.
        reconcile_checkpoints(expected, validated_captures)
        binding = {"schema": "star-capture-set-binding/v1",
                   "run_id": run_id, "correlation_id": correlation_id,
                   "events": {cue.cue: refs[cue.cue] for cue in CUES},
                   "entries": [{k: v for k, v in entry.items() if k != "manifest_sha256"}
                               for entry in ordered]}
        canonical = json.dumps(binding, sort_keys=True, ensure_ascii=True,
                               separators=(",", ":"), allow_nan=False).encode("utf-8")
        capture_set_sha256 = hashlib.sha256(canonical).hexdigest()
    report = {"schema": "star-capture-evidence-v1", "run_id": run_id, "entries": ordered,
            "integrity_checked": all(e["status"] == "integrity_checked" for e in ordered),
            "runtime_authenticated": False, "business_validated": False,
            "human_approval_authenticated": False, "live_action_authorized": False}
    if require_complete:
        report["capture_set_sha256"] = capture_set_sha256
    return report
