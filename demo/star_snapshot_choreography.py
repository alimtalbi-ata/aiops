"""Fail-closed snapshot choreography for the synthetic AIOps STAR demo.

This module makes no network calls and never asserts a screenshot was captured.
Actual browser capture is a separate, authorized integration step.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

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
        if not str(record["screenshot_path"]).startswith("evidence/"):
            raise ValueError("capture path outside evidence directory")
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
