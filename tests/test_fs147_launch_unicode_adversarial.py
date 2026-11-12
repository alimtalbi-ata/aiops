"""Regression: launch identity must share binding-key Unicode safety rules.

Offline, synthetic, no GLPI/Temporal/DB calls.
"""
from dataclasses import replace

import pytest

from app.core.fs147_launch_admission import LaunchDecision, LaunchEvidence, classify_launch


def admissible():
    return LaunchEvidence(
        tenant_id="tenant", alert_fingerprint="alert", incident_id="incident",
        run_id="run", evidence_id="evidence", ticket_id=147, mode="DEMO",
        action_id="inspect", action_path="/fs-lab", idempotency_key="fs147:v1:test",
        policy="ALLOW", native_hitl="ACCEPTED",
        approval_action_id="inspect", approval_run_id="run",
        approval_ticket_id=147, approval_path="/fs-lab",
        owner_id="worker", lease_owner_id="worker", fencing_token=3,
        observed_fencing_token=3, temporal_state="PENDING",
        authoritative_reads=True, lease_cas_verified=True,
    )


@pytest.mark.parametrize("field", [
    "tenant_id", "alert_fingerprint", "incident_id", "run_id",
    "evidence_id", "action_id", "action_path", "idempotency_key",
    "owner_id", "lease_owner_id", "approval_action_id",
    "approval_run_id", "approval_path",
])
@pytest.mark.parametrize("bad", ["e\u0301", "abc\u202e", "abc\u200b", "abc\ud800"])
def test_invalid_unicode_is_unknown(field, bad):
    value = replace(admissible(), **{field: bad})
    assert classify_launch(value) == LaunchDecision.UNKNOWN


def test_matching_nfc_does_not_override_policy():
    value = replace(admissible(), tenant_id="é", policy="STOP_AUTO")
    assert classify_launch(value) == LaunchDecision.DENIED


def test_complete_snapshot_only_eligible_for_revalidation():
    value = admissible()
    assert classify_launch(value) == LaunchDecision.ELIGIBLE_FOR_REVALIDATION
    assert value.temporal_state == "PENDING"


def test_no_mutation_of_input():
    value = admissible()
    before = dict(vars(value))
    classify_launch(value)
    assert vars(value) == before
