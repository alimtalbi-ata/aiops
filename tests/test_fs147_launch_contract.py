"""FS147 launch contract regression tests; all in-memory and side-effect free."""
from dataclasses import replace

from app.core.fs147_launch_contract import LaunchSnapshot, LaunchStatus, classify_launch


def valid():
    return LaunchSnapshot(
        mode="DEMO", tenant_id="tenant", idempotency_key="key",
        alert_fingerprint="alert", incident_id="INC-1", run_id="RUN-1",
        evidence_id="EV-1", evidence_sha256="a" * 64, glpi_ticket_id=147,
        ticket_exists_verified=True, policy="ALLOW", stop_auto=False,
        hitl="ACCEPTED", hitl_action_bound=True, ownership_verified=True,
        fencing_verified=True, temporal_state="WAITING_HUMAN",
        authoritative_read=True,
    )


def test_repeat_is_pure_and_only_candidate():
    original = valid()
    for _ in range(20):
        assert classify_launch(original) == LaunchStatus.ELIGIBLE_FOR_REVALIDATION
    assert original == valid()


def test_explicit_denials():
    for change in (
        {"mode": "LIVE"}, {"glpi_ticket_id": 146}, {"policy": "DENY"},
        {"policy": "BLOCKED"}, {"stop_auto": True}, {"hitl": "REJECTED"},
        {"hitl": "EXPIRED"}, {"hitl_action_bound": False},
        {"temporal_state": "COMPLETED"}, {"temporal_state": "CANCELLED"},
    ):
        assert classify_launch(replace(valid(), **change)) == LaunchStatus.DENIED


def test_unknown_missing_or_unverified():
    for change in (
        {"tenant_id": ""}, {"idempotency_key": None}, {"alert_fingerprint": ""},
        {"incident_id": ""}, {"run_id": ""}, {"evidence_id": ""},
        {"evidence_sha256": ""}, {"glpi_ticket_id": True},
        {"ticket_exists_verified": False}, {"ownership_verified": False},
        {"fencing_verified": False}, {"authoritative_read": False},
        {"policy": "UNKNOWN"}, {"mode": "OTHER"}, {"hitl": "UNKNOWN"},
        {"temporal_state": "RUNNING"}, {"stop_auto": None},
    ):
        assert classify_launch(replace(valid(), **change)) == LaunchStatus.UNKNOWN
    assert classify_launch(None) == LaunchStatus.UNKNOWN


def test_pending_requires_human():
    assert classify_launch(replace(valid(), hitl="PENDING")) == LaunchStatus.NEEDS_HUMAN
