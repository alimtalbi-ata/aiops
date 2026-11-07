"""Pure FS147 resume triage: no GLPI, Temporal, network or host effects."""
from dataclasses import replace
from app.core.fs147_resume_status import (
    ResumeObservation, ResumeStatus, classify_resume,
)


def valid():
    return ResumeObservation(
        mode="DEMO", ticket_id=147, policy="ALLOW", stop_auto=False,
        approval="ACCEPTED", action_bound=True, owner_verified=True,
        fencing_verified=True, temporal_state="WAITING_HUMAN",
        authoritative_read=True,
    )


def test_positive_is_only_revalidation_candidate():
    x = valid()
    assert classify_resume(x) == ResumeStatus.ELIGIBLE_FOR_REVALIDATION
    assert classify_resume(x) == classify_resume(x)
    assert x == valid()


def test_explicit_denials():
    for changes in (
        {"mode": "LIVE"}, {"ticket_id": 146}, {"policy": "DENY"},
        {"policy": "BLOCKED"}, {"stop_auto": True},
        {"approval": "REJECTED"}, {"approval": "EXPIRED"},
        {"action_bound": False}, {"temporal_state": "COMPLETED"},
        {"temporal_state": "CANCELLED"},
    ):
        assert classify_resume(replace(valid(), **changes)) == ResumeStatus.DENIED


def test_missing_unknown_never_becomes_success():
    for changes in (
        {"mode": None}, {"ticket_id": True}, {"policy": None},
        {"stop_auto": None}, {"approval": None},
        {"action_bound": None}, {"owner_verified": False},
        {"fencing_verified": False}, {"authoritative_read": False},
        {"temporal_state": None}, {"temporal_state": "RUNNING"},
    ):
        assert classify_resume(replace(valid(), **changes)) == ResumeStatus.UNKNOWN
    assert classify_resume(None) == ResumeStatus.UNKNOWN


def test_pending_requires_human():
    assert classify_resume(replace(valid(), approval="PENDING")) == ResumeStatus.NEEDS_HUMAN
