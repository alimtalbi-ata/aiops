"""FS.364 read-only admission contract for a persisted Temporal wait.

Never use this predicate as an authorization token. The backend must obtain
all inputs from authenticated, current, independently verified records.
"""
from dataclasses import dataclass
from .fs364_correlation import Link, validate, temporal_resume_allowed


@dataclass(frozen=True)
class ResumeSnapshot:
    link: Link
    observed_fingerprint: str
    observed_incident_id: str
    observed_run_id: str
    observed_evidence_id: str
    observed_ticket_id: int
    observed_mode: str
    persisted_run_state: str
    policy_decision: str
    human_answer_verified: bool
    approval_specific: bool
    authenticated: bool
    acl_ok: bool
    stop_auto: bool


def resume_admissible(snapshot: ResumeSnapshot) -> bool:
    """Fail closed on stale/mismatched identity, terminal refusal or LIVE."""
    try:
        validate(snapshot.link)
    except (ValueError, TypeError, AttributeError):
        return False
    link = snapshot.link
    if (snapshot.observed_fingerprint != link.fingerprint
            or snapshot.observed_incident_id != link.incident_id
            or snapshot.observed_run_id != link.run_id
            or snapshot.observed_evidence_id != link.evidence_id
            or snapshot.observed_ticket_id != 147
            or snapshot.observed_mode != link.mode
            or snapshot.persisted_run_state != "WAITING_HUMAN"):
        return False
    return temporal_resume_allowed(
        mode=link.mode, same_run=True, mode_match=True,
        authenticated=snapshot.authenticated, acl_ok=snapshot.acl_ok,
        stop_auto=snapshot.stop_auto, policy_decision=snapshot.policy_decision,
        human_answer_verified=snapshot.human_answer_verified,
        approval_specific=snapshot.approval_specific,
    )
