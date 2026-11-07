"""FS147: negative-only launch matrix, no host or external effects.

These checks protect the pure classifier against truthy strings and mixed
tenant/run/evidence identifiers. CI success does not attest GLPI or Temporal.
"""
from dataclasses import replace

from app.core.fs147_launch_contract import LaunchSnapshot
from app.core.fs147_launch_identity_gate import (
    IdentityLaunchStatus as Status, classify_identity_launch,
)


def baseline():
    return LaunchSnapshot(
        mode="DEMO", tenant_id="tenant", idempotency_key="key",
        alert_fingerprint="alert", incident_id="INC-1", run_id="RUN-1",
        evidence_id="EVID-1", evidence_sha256="a" * 64,
        glpi_ticket_id=147, ticket_exists_verified=True,
        policy="ALLOW", stop_auto=False, hitl="ACCEPTED",
        hitl_action_bound=True, ownership_verified=True,
        fencing_verified=True, temporal_state="WAITING_HUMAN",
        authoritative_read=True,
    )


def test_boolean_attestations_are_not_truthy_strings():
    for field in ("ticket_exists_verified", "stop_auto", "hitl_action_bound",
                  "ownership_verified", "fencing_verified", "authoritative_read"):
        for value in ("true", 1, None):
            candidate = replace(baseline(), **{field: value})
            assert classify_identity_launch(candidate) == Status.UNKNOWN


def test_missing_authoritative_evidence_never_eligible():
    for field in ("ticket_exists_verified", "ownership_verified",
                  "fencing_verified", "authoritative_read"):
        assert classify_identity_launch(replace(baseline(), **{field: False})) == Status.UNKNOWN


def test_native_hitl_and_temporal_negative_states():
    for state in ("REJECTED", "EXPIRED"):
        assert classify_identity_launch(replace(baseline(), hitl=state)) == Status.DENIED
    for state in ("CANCELLED", "COMPLETED"):
        assert classify_identity_launch(replace(baseline(), temporal_state=state)) == Status.DENIED
    assert classify_identity_launch(replace(baseline(), hitl_action_bound=False)) == Status.DENIED
    assert classify_identity_launch(replace(baseline(), hitl="PENDING")) == Status.NEEDS_HUMAN


def test_unknown_policy_and_temporal_states_never_eligible():
    assert classify_identity_launch(replace(baseline(), policy="UNAVAILABLE")) == Status.UNKNOWN
    assert classify_identity_launch(replace(baseline(), temporal_state="RUNNING")) == Status.UNKNOWN
    assert classify_identity_launch(replace(baseline(), hitl="UNKNOWN")) == Status.UNKNOWN


def test_cross_ticket_and_live_always_denied():
    for candidate in (replace(baseline(), glpi_ticket_id=146),
                      replace(baseline(), mode="LIVE"),
                      replace(baseline(), stop_auto=True),
                      replace(baseline(), policy="BLOCKED")):
        assert classify_identity_launch(candidate) == Status.DENIED
