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
    if not isinstance(known, dict) or any(key not in {"alert_id", "ticket_id", "approval_id", "execution_by_cue"} for key in known):
        raise ValueError("unknown evidence identity")
    per_cue = known.get("execution_by_cue", {})
    if not isinstance(per_cue, dict) or any(k not in {"correlate", "enrich", "analyze", "simulate"} for k in per_cue):
        raise ValueError("invalid per-cue execution map")
    if any(not isinstance(v, str) or not _ID.fullmatch(v) for v in per_cue.values()):
        raise ValueError("invalid n8n execution identity")
    if len(set(per_cue.values())) != len(per_cue):
        raise ValueError("n8n execution identity reused across distinct STAR cues")
    if any(not isinstance(v, str) or not _ID.fullmatch(v) for k,v in known.items() if k != "execution_by_cue"):
        raise ValueError("unsafe evidence identity")
    steps=[]
    for cue in CUES:
        supplied={"run_id":run_id}
        supplied.update({key:known[key] for key in _REQUIRED[cue.cue] if key in known})
        if cue.cue in per_cue:
            supplied["execution_id"] = per_cue[cue.cue]
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
