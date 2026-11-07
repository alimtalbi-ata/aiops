"""Pure negative matrix: no DB, GLPI, host, or Temporal I/O."""
from dataclasses import replace
import pytest
from app.core.fs147_launch_admission import LaunchEvidence, LaunchDecision, classify_launch


def fixture():
    return LaunchEvidence(
        tenant_id="demo", alert_fingerprint="alert-92", incident_id="inc-1",
        run_id="run-1", evidence_id="ev-1", ticket_id=147, mode="DEMO",
        action_id="inspect", action_path="/fs-lab", idempotency_key="k1",
        policy="ALLOW", native_hitl="ACCEPTED", approval_action_id="inspect",
        approval_run_id="run-1", approval_ticket_id=147, approval_path="/fs-lab",
        owner_id="worker-1", lease_owner_id="worker-1", fencing_token=7,
        observed_fencing_token=7, temporal_state="PENDING",
        authoritative_reads=True, lease_cas_verified=True,
    )


def test_valid_is_not_execution_permission():
    sample = fixture()
    assert classify_launch(sample) == LaunchDecision.ELIGIBLE_FOR_REVALIDATION
    assert classify_launch(sample) == classify_launch(sample)


@pytest.mark.parametrize("changes,decision", [
    ({"mode": "LIVE"}, LaunchDecision.DENIED),
    ({"ticket_id": 146}, LaunchDecision.DENIED),
    ({"policy": "DENY"}, LaunchDecision.DENIED),
    ({"native_hitl": "REJECTED"}, LaunchDecision.DENIED),
    ({"native_hitl": "PENDING"}, LaunchDecision.NEEDS_HUMAN),
    ({"native_hitl": "UNKNOWN"}, LaunchDecision.NEEDS_HUMAN),
    ({"policy": "UNKNOWN"}, LaunchDecision.UNKNOWN),
    ({"approval_ticket_id": 146}, LaunchDecision.DENIED),
    ({"approval_run_id": "other"}, LaunchDecision.DENIED),
    ({"approval_action_id": "delete"}, LaunchDecision.DENIED),
    ({"approval_path": "/other"}, LaunchDecision.DENIED),
    ({"lease_owner_id": "worker-2"}, LaunchDecision.DENIED),
    ({"observed_fencing_token": 6}, LaunchDecision.DENIED),
    ({"fencing_token": True}, LaunchDecision.UNKNOWN),
    ({"authoritative_reads": False}, LaunchDecision.UNKNOWN),
    ({"lease_cas_verified": False}, LaunchDecision.UNKNOWN),
    ({"temporal_state": "UNCERTAIN"}, LaunchDecision.UNKNOWN),
    ({"temporal_state": "DELIVERED"}, LaunchDecision.UNKNOWN),
    ({"temporal_state": "DISPATCHING"}, LaunchDecision.UNKNOWN),
    ({"temporal_state": "UNKNOWN"}, LaunchDecision.UNKNOWN),
    ({"run_id": ""}, LaunchDecision.UNKNOWN),
    ({"alert_fingerprint": "bad\nkey"}, LaunchDecision.UNKNOWN),
    ({"ticket_id": None}, LaunchDecision.UNKNOWN),
])
def test_fail_closed(changes, decision):
    assert classify_launch(replace(fixture(), **changes)) == decision


def test_invalid_payload():
    assert classify_launch(None) == LaunchDecision.UNKNOWN
