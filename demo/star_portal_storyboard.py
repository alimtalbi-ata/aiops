"""Pure STAR portal timeline adapter: integrity status is not business proof.

No HTTP calls, no external links emitted, no modifications to the deployed portal.
"""
from __future__ import annotations

from collections.abc import Mapping
from demo.star_snapshot_choreography import CUES

_ALLOWED = {"missing", "simulated", "integrity_checked"}
_LABELS = {
    "missing": "Capture indisponible",
    "simulated": "Illustration fictive — non issue du runtime",
    "integrity_checked": "Fichier PNG contrôlé — origine runtime non authentifiée",
}

def storyboard(report: Mapping[str, object], scenario: str) -> dict[str, object]:
    if scenario not in {"SAN_FABRIC_P1", "PAYMENTS_P2"}:
        raise ValueError("unknown demo scenario")
    if report.get("schema") != "star-capture-evidence-v1":
        raise ValueError("unknown evidence schema")
    if any(report.get(k) is True for k in (
        "runtime_authenticated", "business_validated",
        "human_approval_authenticated", "live_action_authorized",
    )):
        raise ValueError("unexpected authority claimed in evidence report")
    entries = report.get("entries")
    if not isinstance(entries, list) or len(entries) != len(CUES):
        raise ValueError("incomplete or duplicated cue list")
    frames = []
    for cue, entry in zip(CUES, entries):
        if not isinstance(entry, dict) or entry.get("cue") != cue.cue:
            raise ValueError("out-of-order cue or missing cue")
        status = entry.get("status")
        if status not in _ALLOWED:
            raise ValueError("unrecognized capture status")
        if status == "integrity_checked" and (
            entry.get("view") != cue.view or
            not isinstance(entry.get("sha256"), str) or
            len(entry["sha256"]) != 64
        ):
            raise ValueError("incomplete integrity metadata")
        frames.append({
            "step": cue.cue,
            "application": cue.service,
            "expected_view": cue.view,
            "expected_state": cue.required_state,
            "capture_status": status,
            "caption": _LABELS[status],
            "runtime_verified": False,
            "action_allowed": False,
        })
    return {
        "schema": "star-portal-storyboard-v1",
        "scenario": scenario,
        "frames": frames,
        "no_live_actions": True,
        "portal_integration_qualified": False,
    }
