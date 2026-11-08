"""FS147 Temporal replay safety matrix: synthetic, no external I/O.

A positive preflight is a snapshot classification, not a Temporal signal.
"""
from dataclasses import replace

import pytest

from app.core.fs147_temporal_resume import ResumeDecision, ResumeEvidence, classify_resume


def fixture():
    return ResumeEvidence(
        tenant_id='tenant', alert_fingerprint='fp', incident_id='inc',
        run_id='run', evidence_id='ev', ticket_id=147, mode='DEMO',
        workflow_id='wf', workflow_run_id='temporal-run',
        expected_workflow_id='wf', expected_workflow_run_id='temporal-run',
        action_id='inspect', approved_action_id='inspect', policy='ALLOW',
        native_hitl='ACCEPTED', owner_id='worker', lease_owner_id='worker',
        fencing_token=7, observed_fencing_token=7,
        durable_outbox_state='READY', temporal_state='WAITING_FOR_HUMAN',
        authoritative_reads=True, lease_cas_verified=True,
    )


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
