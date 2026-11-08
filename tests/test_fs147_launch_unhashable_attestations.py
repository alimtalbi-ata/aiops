"""Adversarial FS147 launch boundary tests: no adapters, no side effects."""
from dataclasses import replace

import pytest

from app.core.fs147_launch_admission import (
    LaunchDecision, LaunchEvidence, classify_launch,
)


def valid():
    return LaunchEvidence(
        tenant_id="tenant", alert_fingerprint="alert", incident_id="incident",
        run_id="run", evidence_id="evidence", ticket_id=147, mode="DEMO",
        action_id="action", action_path="/fs-lab/example", idempotency_key="key",
        policy="ALLOW", native_hitl="ACCEPTED",
        approval_action_id="action", approval_run_id="run",
        approval_ticket_id=147, approval_path="/fs-lab/example",
        owner_id="worker", lease_owner_id="worker",
        fencing_token=3, observed_fencing_token=3,
        temporal_state="PENDING", authoritative_reads=True,
        lease_cas_verified=True,
    )


@pytest.mark.parametrize("field", ["policy", "native_hitl", "temporal_state"])
@pytest.mark.parametrize("invalid", [[], {}, {"unexpected": "value"}])
def test_unhashable_attestation_is_unknown(field, invalid):
    evidence = replace(valid(), **{field: invalid})
    assert classify_launch(evidence) is LaunchDecision.UNKNOWN


@pytest.mark.parametrize("field", ["policy", "native_hitl", "temporal_state"])
@pytest.mark.parametrize("invalid", [None, 0, True, 3.14])
def test_non_string_attestation_is_unknown(field, invalid):
    assert classify_launch(replace(valid(), **{field: invalid})) is LaunchDecision.UNKNOWN


@pytest.mark.parametrize("policy", ["DENY", "STOP_AUTO"])
def test_policy_denial_takes_precedence_over_bad_hitl(policy):
    evidence = replace(valid(), policy=policy, native_hitl=[])
    assert classify_launch(evidence) is LaunchDecision.DENIED


def test_valid_candidate_is_not_execution_authorization():
    evidence = valid()
    assert classify_launch(evidence) is LaunchDecision.ELIGIBLE_FOR_REVALIDATION
    assert evidence == valid()


def test_missing_authoritative_read_never_becomes_success():
    assert classify_launch(replace(valid(), authoritative_reads=False)) is LaunchDecision.UNKNOWN
