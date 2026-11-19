"""Offline unit tests; no deployment or network."""
import copy
import hashlib
import json
import pytest
from portal.acme_isolated_remediation_simulator import simulate_remediation_dry_run
from validate_sim01 import validate

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()

@pytest.fixture
def pair():
    journey = dict(schema="aiops.mission-actions.journey.v1", mode="DEMO",
                   runtime_attested=False, live_remediation_authorized=False,
                   incident_id="I", run_id="SIM-1", source_sha256="a"*64)
    request = dict(schema="aiops.demo-remediation-simulation-request.v1",
                   mode="DEMO", tenant_id="acme-demo", incident_id="I",
                   action_id="acme-payments-restart-hypothesis-001",
                   action_kind="SERVICE_RESTART_SIMULATION", policy_decision="SIMULATE_ONLY",
                   before=dict(service="payments", health="DEGRADED", alert_active=True))
    result = dict(schema="aiops.acme-demo-simulation-pipeline.v1", mode="DEMO",
                  incident_id="I", run_id="SIM-1", source_sha256="a"*64,
                  actual_recovery_state="UNKNOWN", runtime_execution_performed=False,
                  glpi_write_performed=False, temporal_execution_performed=False,
                  live_remediation_authorized=False,
                  simulation=simulate_remediation_dry_run(request),
                  evidence_gate=dict(itil_transition_authorized=False, live_remediation_authorized=False))
    return journey, result

def test_valid(pair):
    assert validate(*pair).startswith("PASS")

@pytest.mark.parametrize("field,value", [
    ("run_id", "SIM-2"), ("source_sha256", "b"*64),
    ("actual_recovery_state", "HEALTHY"), ("glpi_write_performed", True),
    ("runtime_execution_performed", True), ("temporal_execution_performed", True),
    ("live_remediation_authorized", True)])
def test_result_rejected(pair, field, value):
    journey, result = copy.deepcopy(pair)
    result[field] = value
    with pytest.raises(ValueError):
        validate(journey, result)

def test_receipt_tampering(pair):
    journey, result = pair
    result["simulation"]["receipt"]["hypothetical_after"]["health"] = "UNKNOWN"
    with pytest.raises(ValueError, match="receipt_digest"):
        validate(journey, result)

def test_rehashed_tampering(pair):
    journey, result = pair
    sim = result["simulation"]
    receipt = sim["receipt"]
    receipt["hypothetical_after"]["health"] = "UNKNOWN"
    receipt["after_sha256"] = digest(receipt["hypothetical_after"])
    sim["receipt_sha256"] = digest(receipt)
    with pytest.raises(ValueError, match="after_state"):
        validate(journey, result)
