"""Offline regression for strict FS147 identity/launch composition."""
from dataclasses import replace

from app.core.fs147_launch_contract import LaunchSnapshot
from app.core.fs147_launch_identity_gate import IdentityLaunchStatus, classify_identity_launch


def sample():
    return LaunchSnapshot(
        mode="DEMO", tenant_id="tenant", idempotency_key="key",
        alert_fingerprint="fingerprint", incident_id="INC-1", run_id="RUN-1",
        evidence_id="EVID-1", evidence_sha256="a" * 64, glpi_ticket_id=147,
        ticket_exists_verified=True, policy="ALLOW", stop_auto=False,
        hitl="ACCEPTED", hitl_action_bound=True, ownership_verified=True,
        fencing_verified=True, temporal_state="WAITING_HUMAN",
        authoritative_read=True,
    )


def test_valid_identity_only_eligible_for_revalidation():
    x = sample()
    assert classify_identity_launch(x) == IdentityLaunchStatus.ELIGIBLE_FOR_REVALIDATION
    assert classify_identity_launch(x) == classify_identity_launch(x)
    assert x == sample()


def test_malformed_identity_never_eligible():
    for changes in (
        {"evidence_sha256": "not-a-sha"}, {"evidence_sha256": "A" * 64},
        {"tenant_id": "tenant with spaces"}, {"run_id": "RUN/other"},
        {"idempotency_key": "x" * 129}, {"evidence_id": None},
    ):
        assert classify_identity_launch(replace(sample(), **changes)) == IdentityLaunchStatus.UNKNOWN


def test_denied_and_human_states_preserved():
    for changes in ({"mode": "LIVE"}, {"glpi_ticket_id": 146},
                    {"policy": "DENY"}, {"stop_auto": True},
                    {"hitl": "REJECTED"}):
        assert classify_identity_launch(replace(sample(), **changes)) == IdentityLaunchStatus.DENIED
    assert classify_identity_launch(replace(sample(), hitl="PENDING")) == IdentityLaunchStatus.NEEDS_HUMAN


def test_unknown_snapshot_and_missing_authority():
    assert classify_identity_launch(None) == IdentityLaunchStatus.UNKNOWN
    assert classify_identity_launch(replace(sample(), authoritative_read=False)) == IdentityLaunchStatus.UNKNOWN
