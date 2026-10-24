"""Plan required evidence identifiers per STAR cue without inventing identities.

Offline specification only: it never promotes a planned capture to runtime proof.
"""
from __future__ import annotations
import re
from demo.star_snapshot_choreography import CUES

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$")
_REQUIRED = {
    "detect": ("run_id", "alert_id"),
    "correlate": ("run_id", "execution_id"),
    "enrich": ("run_id", "execution_id"),
    "analyze": ("run_id", "execution_id"),
    "ticket": ("run_id", "ticket_id"),
    "approve": ("run_id", "ticket_id", "approval_id"),
    "simulate": ("run_id", "execution_id"),
    "verify": ("run_id", "alert_id"),
    "close": ("run_id", "ticket_id"),
}

def plan_capture_identity(run_id: str, known: dict | None = None) -> dict:
    if not isinstance(run_id, str) or not _ID.fullmatch(run_id):
        raise ValueError("invalid run_id")
    known = {} if known is None else known
    if not isinstance(known, dict) or any(key not in {"alert_id", "execution_id", "ticket_id", "approval_id"} for key in known):
        raise ValueError("unknown evidence identity")
    if any(not isinstance(value, str) or not _ID.fullmatch(value) for value in known.values()):
        raise ValueError("unsafe evidence identity")
    steps=[]
    for cue in CUES:
        supplied={"run_id":run_id}
        supplied.update({key:known[key] for key in _REQUIRED[cue.cue] if key in known})
        missing=[key for key in _REQUIRED[cue.cue] if key not in supplied]
        steps.append({
            "cue": cue.cue, "application": cue.service, "expected_view": cue.view,
            "required_identifiers":list(_REQUIRED[cue.cue]),
            "supplied_identifiers":supplied,
            "missing_identifiers":missing,
            "capture_ready_for_attempt":not missing,
            "authenticated_runtime_proof":False,
            "live_action_authorized":False,
        })
    return {
        "schema":"star-capture-identity-plan-v1", "run_id":run_id,
        "steps":steps, "capture_attempt_ready_count":sum(s["capture_ready_for_attempt"] for s in steps),
        "runtime_proof_count":0, "read_only":True,
    }
