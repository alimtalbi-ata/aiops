"""Synthetic no-I/O FS147 Temporal resume tests."""
from dataclasses import replace

import pytest

from app.core.fs147_temporal_resume import (
    ResumeDecision, ResumeEvidence, classify_resume,
)


def fixture():
    return ResumeEvidence(
        tenant_id="tenant", alert_fingerprint="fp", incident_id="inc",
        run_id="run", evidence_id="ev", ticket_id=147, mode="DEMO",
        workflow_id="wf", workflow_run_id="temporal-run",
        expected_workflow_id="wf", expected_workflow_run_id="temporal-run",
        action_id="inspect", approved_action_id="inspect", policy="ALLOW",
        native_hitl="ACCEPTED", owner_id="worker", lease_owner_id="worker",
        fencing_token=7, observed_fencing_token=7,
        durable_outbox_state="READY", temporal_state="WAITING_FOR_HUMAN",
        authoritative_reads=True, lease_cas_verified=True,
    )


def test_candidate_not_execution():
    value = fixture()
    assert classify_resume(value) == ResumeDecision.ELIGIBLE_FOR_REVALIDATION
    assert classify_resume(value) == ResumeDecision.ELIGIBLE_FOR_REVALIDATION


@pytest.mark.parametrize("change,decision", [
    ({"mode": "LIVE"}, ResumeDecision.DENIED),
    ({"ticket_id": 146}, ResumeDecision.DENIED),
    ({"ticket_id": True}, ResumeDecision.UNKNOWN),
    ({"policy": "DENY"}, ResumeDecision.DENIED),
    ({"policy": "UNKNOWN"}, ResumeDecision.UNKNOWN),
    ({"native_hitl": "REJECTED"}, ResumeDecision.DENIED),
    ({"native_hitl": "PENDING"}, ResumeDecision.NEEDS_HUMAN),
    ({"approved_action_id": "delete"}, ResumeDecision.DENIED),
    ({"expected_workflow_id": "other"}, ResumeDecision.DENIED),
    ({"expected_workflow_run_id": "old"}, ResumeDecision.DENIED),
    ({"lease_owner_id": "stale"}, ResumeDecision.DENIED),
    ({"observed_fencing_token": 6}, ResumeDecision.DENIED),
    ({"fencing_token": True}, ResumeDecision.UNKNOWN),
    ({"authoritative_reads": False}, ResumeDecision.UNKNOWN),
    ({"lease_cas_verified": False}, ResumeDecision.UNKNOWN),
    ({"durable_outbox_state": "DISPATCHING"}, ResumeDecision.UNKNOWN),
    ({"durable_outbox_state": "DELIVERED"}, ResumeDecision.UNKNOWN),
    ({"durable_outbox_state": "UNKNOWN"}, ResumeDecision.UNKNOWN),
    ({"temporal_state": "RUNNING"}, ResumeDecision.UNKNOWN),
    ({"temporal_state": "UNKNOWN"}, ResumeDecision.UNKNOWN),
    ({"run_id": ""}, ResumeDecision.UNKNOWN),
    ({"run_id": "run\\u202e"}, ResumeDecision.UNKNOWN),
])
def test_fail_closed(change, decision):
    assert classify_resume(replace(fixture(), **change)) == decision


def test_wrong_input():
    assert classify_resume(None) == ResumeDecision.UNKNOWN
