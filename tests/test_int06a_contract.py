"""Offline contracts only: no Temporal connections, DB or network."""
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from worker.int06a_contract import sandbox_mode, validate_manifest
from worker.int06a_registration import registered_activities, acme_no_effect_activity
from temporalio.exceptions import ApplicationError
import asyncio

INTENT = dict(tenant_id="ACME-TEST", scenario_id="ACME-SAN-PAYMENTS", mode="SIMULATION",
    attempt_id="ACME-SIM-TEST-001", idempotency_key="ACME-SIM-TEST-001",
    incident_id="INC-001", run_id="RUN-001", proposal_id="PROP-001",
    ticket_id="SIM-GLPI-001", approval_id="SIM-APP-001", approval_issuer="TWIN_ACME_SIMULATED",
    human_approved=False, execution_allowed=False, effect_allowed=False)

def test_registration_default_and_explicit():
    assert registered_activities([], enabled="0", namespace="default", address="other") == []
    assert registered_activities([], enabled="1", namespace="acme-int06", address="aiops2-temporal:7233") == [acme_no_effect_activity]
    with pytest.raises(ApplicationError, match="sandbox_authorities_unavailable"):
        asyncio.run(acme_no_effect_activity(INTENT))

@pytest.mark.parametrize("flag,namespace,address", [("true","acme-int06","aiops2-temporal:7233"),("1","default","aiops2-temporal:7233"),("1","acme-int06","remote:7233")])
def test_registration_denied(flag, namespace, address):
    with pytest.raises(ValueError):
        registered_activities([], enabled=flag, namespace=namespace, address=address)

@pytest.mark.parametrize("mode", ["LIVE","STORY","REPLAY","SIMULATION","unknown",None])
def test_mode_denied(mode):
    with pytest.raises(ValueError):
        sandbox_mode(mode, INTENT)

def test_mapping_is_contract_only():
    assert sandbox_mode("DEMO", INTENT) == "SIMULATION"

@pytest.mark.parametrize("manifest,readback", [({},None),({"scope":"STORY_OFFLINE"},{}),({"scope":"RUNTIME_SANDBOX","executed_sha":"b"*40},{})])
def test_missing_or_foreign_manifest_denied(manifest, readback):
    with pytest.raises(ValueError):
        validate_manifest(manifest, expected_sha="a"*40, intent=INTENT, independently_read=readback)
