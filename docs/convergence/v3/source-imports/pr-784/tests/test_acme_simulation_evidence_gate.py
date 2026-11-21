"""Simulated improvement and cryptographic consistency never prove recovery."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal.acme_isolated_remediation_simulator import simulate_remediation_dry_run
from portal.acme_simulation_evidence_gate import assess_simulation_evidence_gate as _assess_simulation_evidence_gate


def assess_simulation_evidence_gate(request, simulation, evidence):
    return _assess_simulation_evidence_gate(
        request, simulation, evidence, expected_source_sha256="a" * 64,
        expected_incident_id="SAN-P1")


def sample():
    request = {
        "schema": "aiops.demo-remediation-simulation-request.v1",
        "mode": "DEMO", "tenant_id": "acme-demo", "incident_id": "SAN-P1",
        "action_id": "sim-01", "action_kind": "SERVICE_RESTART_SIMULATION",
        "policy_decision": "SIMULATE_ONLY",
        "before": {"service": "payments", "health": "DEGRADED", "alert_active": True},
    }
    evidence = {
        "schema": "aiops.synthetic-evidence-joint-qualification.v1",
        "mode": "DEMO", "expected_tenant_id": "acme-demo",
        "source_sha256": "a" * 64, "checkpoints": [],
        "integrity_consistent_unattested_count": 0,
        "independently_attested_count": 0, "overall_qualification": "UNKNOWN",
        "evidence_accepted": False, "itil_transition_authorized": False,
        "live_remediation_authorized": False,
    }
    return request, simulate_remediation_dry_run(request), evidence


def test_valid_simulation_without_evidence_still_unknown():
    request, simulation, evidence = sample()
    result = assess_simulation_evidence_gate(request, simulation, evidence)
    assert result["simulation_receipt_verified"] is True
    assert result["actual_recovery_state"] == "UNKNOWN"
    assert result["independent_runtime_postcheck_verified"] is False
    assert result["itil_transition_authorized"] is False
    assert result["live_remediation_authorized"] is False


def test_consistent_unattested_evidence_still_no_go():
    request, simulation, evidence = sample()
    evidence["checkpoints"] = [{
        "checkpoint": "verify", "digest_state": "DIGEST_MATCH_UNATTESTED",
        "source_receipt_state": "MAC_VALID_SOURCE_KEY_UNATTESTED",
        "integrity_consistent_unattested": True,
        "runtime_observation_independently_verified": False,
        "tenant_actor_authorized": False, "itil_transition_authorized": False,
    }]
    evidence["integrity_consistent_unattested_count"] = 1
    result = assess_simulation_evidence_gate(request, simulation, evidence)
    assert result["evidence_integrity_consistent_unattested_count"] == 1
    assert result["actual_recovery_state"] == "UNKNOWN"


@pytest.mark.parametrize("field,value", [
    ("expected_tenant_id", "other-tenant"), ("overall_qualification", "PASS"),
    ("independently_attested_count", 1), ("evidence_accepted", True),
    ("itil_transition_authorized", True), ("live_remediation_authorized", True),
])
def test_forged_evidence_rejected(field, value):
    request, simulation, evidence = sample()
    evidence[field] = value
    with pytest.raises(ValueError):
        assess_simulation_evidence_gate(request, simulation, evidence)


def test_tampered_simulation_and_forged_checkpoint_rejected():
    request, simulation, evidence = sample()
    altered = copy.deepcopy(simulation)
    altered["receipt"]["hypothetical_after"]["health"] = "DEGRADED"
    with pytest.raises(ValueError, match="simulation_receipt_not_verified"):
        assess_simulation_evidence_gate(request, altered, evidence)
    evidence["checkpoints"] = [{
        "checkpoint": "verify", "digest_state": "DIGEST_MATCH_UNATTESTED",
        "source_receipt_state": "MAC_VALID_SOURCE_KEY_UNATTESTED",
        "integrity_consistent_unattested": True,
        "runtime_observation_independently_verified": True,
        "tenant_actor_authorized": False, "itil_transition_authorized": False,
    }]
    evidence["integrity_consistent_unattested_count"] = 1
    with pytest.raises(ValueError, match="forged_evidence_row"):
        assess_simulation_evidence_gate(request, simulation, evidence)


def test_forged_count_rejected():
    request, simulation, evidence = sample()
    evidence["integrity_consistent_unattested_count"] = 1
    with pytest.raises(ValueError, match="forged_evidence_count"):
        assess_simulation_evidence_gate(request, simulation, evidence)


def test_foreign_incident_evidence_digest_rejected():
    request, simulation, evidence = sample()
    evidence["source_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="evidence_scope_or_safety_mismatch"):
        assess_simulation_evidence_gate(request, simulation, evidence)


def test_expected_digest_must_be_independently_supplied():
    request, simulation, evidence = sample()
    with pytest.raises(TypeError):
        _assess_simulation_evidence_gate(request, simulation, evidence)
    with pytest.raises(ValueError, match="trusted_expected_source_sha256_required"):
        _assess_simulation_evidence_gate(
            request, simulation, evidence, expected_source_sha256="invalid",
            expected_incident_id="SAN-P1")


def test_simulation_for_different_incident_rejected_even_same_tenant():
    request, simulation, evidence = sample()
    with pytest.raises(ValueError, match="simulation_incident_scope_mismatch"):
        _assess_simulation_evidence_gate(
            request, simulation, evidence, expected_source_sha256="a" * 64,
            expected_incident_id="ANOTHER-P1")


def test_expected_incident_id_required_from_trusted_context():
    request, simulation, evidence = sample()
    with pytest.raises(TypeError):
        _assess_simulation_evidence_gate(
            request, simulation, evidence, expected_source_sha256="a" * 64)
    with pytest.raises(ValueError, match="trusted_expected_incident_required"):
        _assess_simulation_evidence_gate(
            request, simulation, evidence, expected_source_sha256="a" * 64,
            expected_incident_id="../other")


@pytest.mark.parametrize("checkpoint,digest_state,receipt_state", [
    ("not-a-real-stage", "DIGEST_MATCH_UNATTESTED", "MAC_VALID_SOURCE_KEY_UNATTESTED"),
    ("verify", "PASS", "MAC_VALID_SOURCE_KEY_UNATTESTED"),
    ("verify", "DIGEST_MATCH_UNATTESTED", "RUNTIME_ATTESTED"),
])
def test_unknown_checkpoint_or_forged_integrity_state_rejected(
        checkpoint, digest_state, receipt_state):
    request, simulation, evidence = sample()
    evidence["checkpoints"] = [{
        "checkpoint": checkpoint, "digest_state": digest_state,
        "source_receipt_state": receipt_state,
        "integrity_consistent_unattested": (
            digest_state == "DIGEST_MATCH_UNATTESTED"
            and receipt_state == "MAC_VALID_SOURCE_KEY_UNATTESTED"),
        "runtime_observation_independently_verified": False,
        "tenant_actor_authorized": False, "itil_transition_authorized": False,
    }]
    evidence["integrity_consistent_unattested_count"] = int(
        evidence["checkpoints"][0]["integrity_consistent_unattested"])
    with pytest.raises(ValueError):
        assess_simulation_evidence_gate(request, simulation, evidence)
