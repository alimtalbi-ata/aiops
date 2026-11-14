"""The DEMO simulator must be deterministic, pure and explicitly non-operational."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.acme_isolated_remediation_simulator import (
    simulate_remediation_dry_run, verify_simulation_receipt,
)


def request():
    return {
        "schema": "aiops.demo-remediation-simulation-request.v1",
        "mode": "DEMO", "tenant_id": "acme-demo",
        "incident_id": "SAN-P1", "action_id": "simulation-01",
        "action_kind": "SERVICE_RESTART_SIMULATION",
        "policy_decision": "SIMULATE_ONLY",
        "before": {"service": "payments", "health": "DEGRADED",
                   "alert_active": True},
    }


def test_hypothetical_state_transition_and_verifiable_receipt():
    original = request()
    snapshot = copy.deepcopy(original)
    first = simulate_remediation_dry_run(original)
    assert first == simulate_remediation_dry_run(original)
    assert original == snapshot
    receipt = first["receipt"]
    assert receipt["before"] == original["before"]
    assert receipt["hypothetical_after"] == {
        "service": "payments", "health": "HEALTHY", "alert_active": False}
    assert receipt["simulation_result"] == "HYPOTHETICAL_ONLY"
    for flag in ("runtime_execution_verified", "independent_postcheck_verified",
                 "temporal_execution_verified", "itil_transition_authorized",
                 "live_remediation_authorized"):
        assert receipt[flag] is False
    assert verify_simulation_receipt(original, first) is True


def test_noop_does_not_forge_recovery():
    value = request()
    value["action_kind"] = "NOOP_OBSERVATION"
    result = simulate_remediation_dry_run(value)["receipt"]
    assert result["before_sha256"] == result["after_sha256"]
    assert result["hypothetical_after"]["health"] == "DEGRADED"


def test_forged_after_state_or_receipt_digest_detected():
    value = request()
    result = simulate_remediation_dry_run(value)
    result["receipt"]["hypothetical_after"]["health"] = "DEGRADED"
    assert verify_simulation_receipt(value, result) is False
    result = simulate_remediation_dry_run(value)
    result["receipt_sha256"] = "0" * 64
    assert verify_simulation_receipt(value, result) is False


@pytest.mark.parametrize("field,value", [
    ("mode", "LIVE"), ("action_kind", "RUN_SHELL"),
    ("policy_decision", "ALLOW_LIVE"), ("tenant_id", ""),
    ("incident_id", "../bad"), ("action_id", None),
])
def test_forbidden_or_invalid_request_rejected(field, value):
    obj = request()
    obj[field] = value
    with pytest.raises(ValueError):
        simulate_remediation_dry_run(obj)


def test_extra_authorization_flag_and_invalid_state_rejected():
    obj = request()
    obj["approved"] = True
    with pytest.raises(ValueError):
        simulate_remediation_dry_run(obj)
    obj = request()
    obj["before"]["alert_active"] = 1
    with pytest.raises(ValueError):
        simulate_remediation_dry_run(obj)


@pytest.mark.parametrize("field,value", [
    ("tenant_id", "ténant"), ("incident_id", "SAN-Ｐ１"),
    ("action_id", "action\u200bhidden"),
])
def test_unicode_identity_spoofing_rejected(field, value):
    obj = request()
    obj[field] = value
    with pytest.raises(ValueError, match="invalid_simulation_identity"):
        simulate_remediation_dry_run(obj)


@pytest.mark.parametrize("field,value", [
    ("health", []), ("health", {}), ("health", 1),
    ("service", "payménts"), ("service", "payments\nINJECTED"),
])
def test_malformed_before_state_fails_with_value_error(field, value):
    obj = request()
    obj["before"][field] = value
    with pytest.raises(ValueError, match="invalid_before_state"):
        simulate_remediation_dry_run(obj)
    assert verify_simulation_receipt(obj, {}) is False
