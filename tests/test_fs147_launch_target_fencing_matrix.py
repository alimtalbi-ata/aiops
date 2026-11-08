"""FS147 targeted HITL and fencing regression matrix (pure; no external calls)."""
from dataclasses import replace
import pytest

from app.core.fs147_launch_admission import LaunchDecision, LaunchEvidence, classify_launch


def candidate():
    return LaunchEvidence(
        tenant_id="tenant", alert_fingerprint="fingerprint", incident_id="incident",
        run_id="run", evidence_id="evidence", ticket_id=147, mode="DEMO",
        action_id="inspect-action", action_path="/fs-lab/target",
        idempotency_key="fs147:v1:synthetic", policy="ALLOW",
        native_hitl="ACCEPTED", approval_action_id="inspect-action",
        approval_run_id="run", approval_ticket_id=147,
        approval_path="/fs-lab/target", owner_id="worker-a",
        lease_owner_id="worker-a", fencing_token=7,
        observed_fencing_token=7, temporal_state="PENDING",
        authoritative_reads=True, lease_cas_verified=True,
    )


@pytest.mark.parametrize("field,bad", [
    ("approval_ticket_id", 146), ("approval_action_id", "other-action"),
    ("approval_run_id", "other-run"), ("approval_path", "/fs-lab/other"),
    ("lease_owner_id", "worker-b"), ("observed_fencing_token", 8),
])
def test_wrong_target_or_stale_fence_is_denied(field, bad):
    assert classify_launch(replace(candidate(), **{field: bad})) is LaunchDecision.DENIED


@pytest.mark.parametrize("field,bad", [
    ("authoritative_reads", False), ("lease_cas_verified", False),
    ("authoritative_reads", None), ("lease_cas_verified", None),
    ("fencing_token", 0), ("observed_fencing_token", 0),
    ("temporal_state", "RUNNING"), ("temporal_state", "COMPLETED"),
    ("temporal_state", "UNCERTAIN"), ("temporal_state", "DELIVERED"),
])
def test_missing_authority_or_uncertain_replay_is_unknown(field, bad):
    assert classify_launch(replace(candidate(), **{field: bad})) is LaunchDecision.UNKNOWN


@pytest.mark.parametrize("hitl", ["PENDING", "UNKNOWN"])
def test_unresolved_native_hitl_needs_human(hitl):
    assert classify_launch(replace(candidate(), native_hitl=hitl)) is LaunchDecision.NEEDS_HUMAN


@pytest.mark.parametrize("changes", [
    {"mode": "LIVE"}, {"ticket_id": 146},
    {"policy": "DENY"}, {"policy": "STOP_AUTO"},
    {"native_hitl": "REJECTED"},
])
def test_explicit_denials(changes):
    assert classify_launch(replace(candidate(), **changes)) is LaunchDecision.DENIED


def test_positive_only_eligible_and_input_immutable():
    original = candidate()
    before = repr(original)
    assert classify_launch(original) is LaunchDecision.ELIGIBLE_FOR_REVALIDATION
    assert repr(original) == before
