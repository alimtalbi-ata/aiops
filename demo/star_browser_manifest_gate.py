"""Offline bridge: Chromium capture manifests -> STAR portal storyboard contract.

Pure local integrity checking. Never authenticates runtime, HITL, or business success.
Expected IDs MUST originate independently from canonical ingress, not manifests.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Mapping as MappingABC
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
MAX_MANIFEST_BYTES = 16_384


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject duplicate keys instead of trusting JSON's last-key-wins behavior."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate capture manifest JSON key")
        result[key] = value
    return result

def _reject_json_constant(value: str) -> object:
    """Keep Python's non-standard NaN/Infinity JSON extensions out of manifests."""
    raise ValueError("non-standard JSON constant in capture manifest")


def _read_manifest_bytes(root: Path, name: str) -> bytes:
    """Read a bounded regular manifest from a pinned directory/file descriptor.

    Directory-relative open plus O_NOFOLLOW prevents a final-component symlink
    swap between path validation and read. File metadata and byte count are
    compared before/after; this is local integrity checking, not source auth.
    """
    if not isinstance(root, Path) or root.is_symlink() or not root.is_dir():
        raise ValueError("unsafe evidence root")
    if (not isinstance(name, str) or not _BASENAME.fullmatch(name)
            or not name.endswith(".json")):
        raise ValueError("unsafe evidence filename")
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if (nofollow is None or directory is None
            or os.open not in getattr(os, "supports_dir_fd", set())):
        raise ValueError("safe descriptor-relative manifest reads unavailable")
    common = getattr(os, "O_CLOEXEC", 0)
    try:
        root_fd = os.open(root, os.O_RDONLY | common | directory | nofollow)
    except OSError as exc:
        raise ValueError("unsafe evidence root") from exc
    try:
        try:
            fd = os.open(name, os.O_RDONLY | common | nofollow
                         | getattr(os, "O_NONBLOCK", 0), dir_fd=root_fd)
        except OSError as exc:
            raise ValueError("capture manifest cannot be opened safely") from exc
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode):
                raise ValueError("capture manifest must be a regular file")
            if before.st_size < 0 or before.st_size > MAX_MANIFEST_BYTES:
                raise ValueError("oversized capture manifest")
            data = bytearray()
            while len(data) <= MAX_MANIFEST_BYTES:
                block = os.read(fd, min(65_536, MAX_MANIFEST_BYTES + 1 - len(data)))
                if not block:
                    break
                data.extend(block)
            if len(data) > MAX_MANIFEST_BYTES:
                raise ValueError("oversized capture manifest")
            after = os.fstat(fd)
            before_state = (before.st_dev, before.st_ino, before.st_size,
                            before.st_mtime_ns, before.st_ctime_ns)
            after_state = (after.st_dev, after.st_ino, after.st_size,
                           after.st_mtime_ns, after.st_ctime_ns)
            if before_state != after_state or len(data) != before.st_size:
                raise ValueError("capture manifest changed during read")
            return bytes(data)
        except OSError as exc:
            raise ValueError("capture manifest read failed safely") from exc
        finally:
            try:
                os.close(fd)
            except OSError:
                pass
    finally:
        try:
            os.close(root_fd)
        except OSError:
            pass
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
    if type(require_complete) is not bool:
        raise ValueError("invalid complete-capture mode")
    if not isinstance(root, Path):
        raise ValueError("unsafe evidence root")
    if not isinstance(expected, MappingABC) or set(expected) != {
        "run_id", "correlation_id", "events"
    }:
        raise ValueError("invalid canonical event contract")
    run_id, correlation_id, refs = (
        expected.get("run_id"), expected.get("correlation_id"), expected.get("events")
    )
    if (not isinstance(refs, MappingABC) or not refs
            or any(not isinstance(key, str) for key in refs)
            or set(refs) - set(CUE_BY_NAME)):
        raise ValueError("canonical event references missing or unknown")
    # Validate the independent canonical identities even for an empty/partial
    # capture list, so malformed source data cannot produce a success-shaped report.
    for event_ref in refs.values():
        verify_snapshot_identity(
            {"run_id": run_id, "correlation_id": correlation_id, "event_ref": event_ref},
            {"run_id": run_id, "correlation_id": correlation_id, "event_ref": event_ref},
        )
    if (not isinstance(filenames, (list, tuple)) or len(filenames) > len(CUES)
            or any(not isinstance(name, str) for name in filenames)):
        raise ValueError("invalid manifest filename list")
    if len(set(filenames)) != len(filenames):
        raise ValueError("duplicate or excessive manifest files")
    if root.is_symlink() or not root.is_dir():
        raise ValueError("unsafe evidence root")
    if require_complete and (set(refs) != set(CUE_BY_NAME) or len(filenames) != len(CUES)):
        raise ValueError("complete STAR capture requires all canonical checkpoints")
    entries: dict[str, dict[str, object]] = {}
    validated_captures: list[dict[str, object]] = []
    hashes: set[str] = set()
    for name in filenames:
        manifest_bytes = _read_manifest_bytes(root, name)
        try:
            manifest_text = manifest_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("capture manifest must be UTF-8") from exc
        try:
            item = json.loads(
                manifest_text, object_pairs_hook=_unique_json_object,
                parse_constant=_reject_json_constant,
            )
        except json.JSONDecodeError as exc:
            raise ValueError("invalid capture manifest JSON") from exc
        except RecursionError as exc:
            raise ValueError("capture manifest nesting is excessive") from exc
        if not isinstance(item, dict) or item.get("schema") != "star-browser-evidence/v1":
            raise ValueError("invalid Chromium manifest schema")
        if set(item) - _ALLOWED_FIELDS:
            raise ValueError("unexpected capture metadata fields")
        service = item.get("service")
        if not isinstance(service, str) or service not in _REDACTED_ROUTE_BY_SERVICE:
            raise ValueError("missing or invalid capture service")
        # Both fields are mandatory: absence must not bypass the trust boundary.
        # A valid route from another service is still the WRONG application page.
        if item.get("source_url_redacted") != _REDACTED_ROUTE_BY_SERVICE[service]:
            raise ValueError("missing, unsafe or cross-service capture route")
        if item.get("event_time_alignment") != _TIME_UNVERIFIED:
            raise ValueError("missing or falsely attested event time alignment")
        if any(item.get(k) not in (None, False) for k in _FORBIDDEN):
            raise ValueError("untrusted browser manifest claims authority")
        cue_name = item.get("cue")
        if not isinstance(cue_name, str):
            raise ValueError("invalid or missing STAR cue name")
        cue = CUE_BY_NAME.get(cue_name)
        if cue is None or cue_name in entries or cue_name not in refs:
            raise ValueError("unknown, duplicate or unrequested STAR cue")
        view = item.get("view")
        if not isinstance(view, str) or service != cue.service or view != cue.view:
            raise ValueError("wrong application view")
        verify_snapshot_identity(
            {"run_id": run_id, "correlation_id": correlation_id, "event_ref": refs[cue_name]},
            {"run_id": item.get("run_id"), "correlation_id": item.get("correlation_id"),
             "event_ref": item.get("event_ref")},
        )
        if item.get("expected_state") != cue.required_state or item.get("observed_state") != cue.required_state:
            raise ValueError("observed state differs from STAR cue")
        provenance = item.get("provenance")
        if not isinstance(provenance, str) or provenance not in _ALLOWED_PROVENANCE:
            raise ValueError("unrecognized screenshot provenance")
        expected_transport = (
            "LOCAL_HTML_FIXTURE_NO_HTTP" if provenance == "ISOLATED_TEST_FIXTURE"
            else "READ_ONLY_BROWSER_HTTP_GET"
        )
        if item.get("capture_transport") != expected_transport:
            raise ValueError("provenance and transport contradict")
        if (item.get("anonymization") != "SELECTOR_MASKS_UNREVIEWED"
                or item.get("qualification") != "CAPTURED_UNREVIEWED_NOT_BUSINESS_PROOF"):
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
        captured_value = item.get("captured_at")
        if not isinstance(captured_value, str):
            raise ValueError("invalid capture timestamp")
        try:
            captured = datetime.fromisoformat(captured_value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("invalid capture timestamp") from exc
        if captured.tzinfo is None or captured.utcoffset() is None:
            raise ValueError("capture timestamp lacks timezone")
        entries[cue_name] = {
            "cue": cue_name,
            "status": "simulated" if provenance == "ISOLATED_TEST_FIXTURE" else "integrity_checked",
            "view": cue.view, "sha256": actual, "bytes": size,
            "captured_at": captured.isoformat(),
        }
        if include_manifest_digests:
            # Additional read-consistency marker; does not change replay pins.
            entries[cue_name]["manifest_sha256"] = hashlib.sha256(manifest_bytes).hexdigest()
    ordered = [entries.get(c.cue, {"cue": c.cue, "status": "missing"}) for c in CUES]
    timestamps = [datetime.fromisoformat(e["captured_at"]) for e in ordered if "captured_at" in e]
    if timestamps != sorted(timestamps):
        raise ValueError("capture chronology contradicted")
    capture_set_sha256 = None
    if require_complete:
        # Only after PNG-byte verification, independent identity checks and full
        # nine-cue coverage. This digest is replay consistency, not authentication.
        reconcile_checkpoints(expected, validated_captures)
        binding = {
            "schema": "star-capture-set-binding/v1",
            "run_id": run_id, "correlation_id": correlation_id,
            "events": {cue.cue: refs[cue.cue] for cue in CUES},
            "entries": [{k: v for k, v in entry.items() if k != "manifest_sha256"}
                        for entry in ordered],
        }
        canonical = json.dumps(binding, sort_keys=True, ensure_ascii=True,
                               separators=(",", ":"), allow_nan=False).encode("utf-8")
        capture_set_sha256 = hashlib.sha256(canonical).hexdigest()
    report = {
        "schema": "star-capture-evidence-v1", "run_id": run_id, "entries": ordered,
        "integrity_checked": all(e["status"] == "integrity_checked" for e in ordered),
        "runtime_authenticated": False, "business_validated": False,
        "human_approval_authenticated": False, "live_action_authorized": False,
    }
    if require_complete:
        report["capture_set_sha256"] = capture_set_sha256
    return report

