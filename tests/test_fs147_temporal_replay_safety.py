"""FS147 Temporal replay safety matrix: synthetic, no external I/O.

A positive preflight is a snapshot classification, not a Temporal signal.
"""
from dataclasses import replace

import pytest

from app.core.fs147_temporal_resume import ResumeDecision, classify_resume
from tests.test_fs147_temporal_resume import fixture


@pytest.mark.parametrize("outbox,temporal", [
    ("READY", "RUNNING"),
    ("READY", "COMPLETED"),
    ("READY", "UNKNOWN"),
    ("DISPATCHING", "WAITING_FOR_HUMAN"),
    ("DELIVERED", "WAITING_FOR_HUMAN"),
    ("ACKNOWLEDGED", "WAITING_FOR_HUMAN"),
    ("UNKNOWN", "WAITING_FOR_HUMAN"),
    ("DISPATCHING", "RUNNING"),
    ("DELIVERED", "COMPLETED"),
])
def test_ambiguous_or_already_dispatched_never_resumes(outbox, temporal):
    snapshot = replace(fixture(), durable_outbox_state=outbox, temporal_state=temporal)
    assert classify_resume(snapshot) is ResumeDecision.UNKNOWN
    assert classify_resume(snapshot) is ResumeDecision.UNKNOWN


@pytest.mark.parametrize("change,expected", [
    ({"mode": "LIVE", "durable_outbox_state": "DISPATCHING"}, ResumeDecision.DENIED),
    ({"ticket_id": 146, "temporal_state": "RUNNING"}, ResumeDecision.DENIED),
    ({"policy": "DENY", "native_hitl": "ACCEPTED"}, ResumeDecision.DENIED),
    ({"native_hitl": "REJECTED", "policy": "ALLOW"}, ResumeDecision.DENIED),
    ({"native_hitl": "PENDING", "durable_outbox_state": "READY"}, ResumeDecision.NEEDS_HUMAN),
    ({"native_hitl": "UNKNOWN"}, ResumeDecision.NEEDS_HUMAN),
    ({"authoritative_reads": None}, ResumeDecision.UNKNOWN),
    ({"lease_cas_verified": 1}, ResumeDecision.UNKNOWN),
    ({"fencing_token": 0}, ResumeDecision.UNKNOWN),
    ({"observed_fencing_token": -1}, ResumeDecision.UNKNOWN),
    ({"expected_workflow_run_id": "different"}, ResumeDecision.DENIED),
    ({"approved_action_id": "different"}, ResumeDecision.DENIED),
])
def test_replay_precedence_and_authority(change, expected):
    assert classify_resume(replace(fixture(), **change)) is expected


def test_eligible_snapshot_does_not_mutate_input():
    snapshot = fixture()
    before = repr(snapshot)
    assert classify_resume(snapshot) is ResumeDecision.ELIGIBLE_FOR_REVALIDATION
    assert repr(snapshot) == before
