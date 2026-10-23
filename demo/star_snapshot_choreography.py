"""Fail-closed snapshot choreography for the synthetic AIOps STAR demo.

This module makes no network calls and never asserts a screenshot was captured.
Actual browser capture is a separate, authorized integration step.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping
from datetime import datetime
from pathlib import PurePosixPath
from urllib.parse import parse_qsl, urlsplit
import re

class ProofState(str, Enum):
    MISSING = "missing"
    SIMULATED = "simulated"
    CAPTURED = "captured"

@dataclass(frozen=True)
class SnapshotCue:
    cue: str
    service: str
    view: str
    required_state: str
    evidence_kind: str

CUES = (
    SnapshotCue("detect", "grafana", "alert_dashboard", "firing", "runtime"),
    SnapshotCue("correlate", "n8n", "ingress_execution", "completed", "runtime"),
    SnapshotCue("enrich", "n8n", "context_execution", "completed", "runtime"),
    SnapshotCue("analyze", "n8n", "analyst_critic_execution", "completed", "runtime"),
    SnapshotCue("ticket", "glpi", "incident_ticket", "open", "runtime"),
    SnapshotCue("approve", "glpi", "hitl_decision", "approved_simulation_only", "runtime"),
    SnapshotCue("simulate", "n8n", "simulation_execution", "completed", "runtime"),
    SnapshotCue("verify", "grafana", "recovery_dashboard", "recovered", "runtime"),
    SnapshotCue("close", "glpi", "incident_followups", "closed", "runtime"),
)
CUE_BY_NAME = {cue.cue: cue for cue in CUES}

# This contract validates only operator-supplied metadata, never a runtime page.
_ALLOWED_QUERY_KEYS = frozenset({"id", "executionId", "orgId", "from", "to", "viewPanel", "var-run_id"})
_SAFE_VALUE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,95}$")

def _validate_provenance_surface(record: Mapping[str, object]) -> None:
    run_id = str(record["run_id"])
    if not _RUN_ID.fullmatch(run_id):
        raise ValueError("unsafe run_id")
    raw_path = str(record["screenshot_path"])
    if ("\\" in raw_path or "%" in raw_path or "//" in raw_path
            or any(c.isspace() or ord(c) < 32 for c in raw_path)
            or ":" in raw_path or not raw_path.endswith(".png")):
        raise ValueError("invalid evidence-relative PNG path")
    parts = raw_path.split("/")
    if (len(parts) < 2 or parts[0] != "evidence"
            or any(part in ("", ".", "..") for part in parts)
            or PurePosixPath(raw_path).is_absolute()):
        raise ValueError("invalid evidence-relative PNG path")
    url = str(record["source_url"])
    if "\\" in url or any(c.isspace() or ord(c) < 32 for c in url):
        raise ValueError("unsafe capture source URL")
    try:
        parsed = urlsplit(url)
        port = parsed.port
        pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
    except ValueError as exc:
        raise ValueError("unsafe capture source URL") from exc
    if (parsed.scheme not in ("http", "https") or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.fragment or (port is not None and port < 1)):
        raise ValueError("unsafe capture source URL")
    keys = [key for key, _ in pairs]
    if (len(keys) != len(set(keys)) or any(key not in _ALLOWED_QUERY_KEYS
            or not _SAFE_VALUE.fullmatch(value) for key, value in pairs)):
        raise ValueError("unsafe capture source query")
    try:
        stamp = datetime.fromisoformat(str(record["captured_at"]).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid capture timestamp") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("capture timestamp must include timezone")


def validate_capture(cue_name: str, record: Mapping[str, object]) -> dict[str, object]:
    """Validate provenance metadata without trusting arbitrary paths or claims."""
    if cue_name not in CUE_BY_NAME:
        raise ValueError("unknown cue")
    cue = CUE_BY_NAME[cue_name]
    if record.get("service") != cue.service or record.get("view") != cue.view:
        raise ValueError("snapshot cue mismatch")
    state = record.get("proof_state", ProofState.MISSING.value)
    if state not in {s.value for s in ProofState}:
        raise ValueError("invalid proof state")
    if state == ProofState.CAPTURED.value:
        required = ("captured_at", "source_url", "sha256", "run_id", "screenshot_path")
        if any(not isinstance(record.get(key), str) or not record[key].strip() for key in required):
            raise ValueError("incomplete real capture evidence")
        digest = record["sha256"]
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError("invalid sha256")
        if not str(record["source_url"]).startswith(("https://", "http://")):
            raise ValueError("invalid capture source")
        _validate_provenance_surface(record)
    elif record.get("claim_real") is True:
        raise ValueError("synthetic or missing asset must not claim real capture")
    return {
        "cue": cue_name,
        "service": cue.service,
        "view": cue.view,
        "required_state": cue.required_state,
        "proof_state": state,
        "metadata_complete": state == ProofState.CAPTURED.value,
        "verified_real_capture": False,  # Metadata cannot authenticate a runtime screenshot.
    }

def build_timeline(records: Mapping[str, Mapping[str, object]]) -> list[dict[str, object]]:
    """Every missing cue is explicitly marked missing, never silently successful."""
    unknown = set(records) - set(CUE_BY_NAME)
    if unknown:
        raise ValueError("unknown cues in timeline")
    return [
        validate_capture(cue.cue, records.get(cue.cue, {
            "service": cue.service, "view": cue.view,
            "proof_state": ProofState.MISSING.value,
        }))
        for cue in CUES
    ]
