"""FS147 regression: STOP_AUTO must never become an eligible launch."""
from dataclasses import replace
from app.core.fs147_launch_admission import LaunchEvidence, LaunchDecision, classify_launch


def _valid_snapshot():
    return LaunchEvidence(
        tenant_id="tenant", alert_fingerprint="alert", incident_id="incident",
        run_id="run", evidence_id="evidence", ticket_id=147, mode="DEMO",
        action_id="action", action_path="/fs-lab/target", idempotency_key="key",
        policy="ALLOW", native_hitl="ACCEPTED", approval_action_id="action",
        approval_run_id="run", approval_ticket_id=147,
        approval_path="/fs-lab/target", owner_id="worker",
        lease_owner_id="worker", fencing_token=7, observed_fencing_token=7,
        temporal_state="PENDING", authoritative_reads=True,
        lease_cas_verified=True,
    )


def test_stop_auto_overrides_even_positive_evidence():
    snapshot = replace(_valid_snapshot(), policy="STOP_AUTO")
    assert classify_launch(snapshot) == LaunchDecision.DENIED
    assert classify_launch(snapshot) == LaunchDecision.DENIED


def test_stop_auto_overrides_pending_hitl():
    snapshot = replace(_valid_snapshot(), policy="STOP_AUTO", native_hitl="PENDING")
    assert classify_launch(snapshot) == LaunchDecision.DENIED


def test_unknown_policy_is_not_success():
    assert classify_launch(replace(_valid_snapshot(), policy="UNKNOWN")) == LaunchDecision.UNKNOWN


def test_live_is_denied_regardless_of_policy():
    assert classify_launch(replace(_valid_snapshot(), mode="LIVE", policy="ALLOW")) == LaunchDecision.DENIED


def test_no_mutation_of_frozen_snapshot():
    snapshot = replace(_valid_snapshot(), policy="STOP_AUTO")
    before = repr(snapshot)
    classify_launch(snapshot)
    assert repr(snapshot) == before
