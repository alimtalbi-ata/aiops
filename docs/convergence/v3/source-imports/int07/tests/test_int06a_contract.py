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

from copy import deepcopy
from worker.int06a_contract import IDENTITY, STAGES, digest, validate_postcheck
from worker.acme_simulated_hitl import simulate_no_effect
from test_worker_acme_simulated_hitl import fixtures, NOW, INTENT as FIXTURE_INTENT

def manifest_fixture():
    docs = fixtures()
    async def read(component, path):
        return deepcopy(docs[component])
    receipt = asyncio.run(simulate_no_effect(FIXTURE_INTENT, get=read, now=NOW))
    identity = {k: FIXTURE_INTENT[k] for k in IDENTITY}
    rows = [dict(identity=identity.copy(), stage=stage, status="PASS", version=i+1,
                 sequence=i+1, source="CORE", observed_at="2026-11-18T12:00:00Z")
            for i, stage in enumerate(STAGES)]
    terminal = dict(identity=identity.copy(), source="CORE", status="RESOLVED",
                    version=99, sequence=99, observed_at="2026-11-18T12:01:00Z")
    m = dict(scope="RUNTIME_SANDBOX", executed_sha="a"*40, runtime_attested=False,
             identity=identity.copy(), images={k:"sha256:"+"b"*64 for k in
              ("core","twin","policy","worker","evidence","postgres","temporal","temporal_postgres")},
             worker_receipt=receipt, history_sha256="c"*64, transitions=rows, terminal=terminal)
    readback = dict(identity=identity.copy(), scope=m["scope"], executed_sha=m["executed_sha"],
                    images=deepcopy(m["images"]), worker_receipt_sha256=receipt["receipt_sha256"],
                    history_sha256=m["history_sha256"], transitions_sha256=digest(rows),
                    critic_decision="ALLOW", twin_state="QUALIFIED", policy_decision="SIMULATE",
                    hitl_valid=True, external_effect_count=0, postcheck_verified=True,
                    terminal=deepcopy(terminal), terminal_readback_sha256=digest(terminal))
    return m, readback

def test_positive_fixture_does_not_authorize_runtime():
    m, r = manifest_fixture()
    assert validate_manifest(m, expected_sha="a"*40, intent=FIXTURE_INTENT, independently_read=r) == {
        "qualification":"CONTRACT_ONLY", "runtime_attested":False, "resolution_authorized":False}
    assert validate_postcheck(intent=FIXTURE_INTENT, independently_read=r)["finish_authorized"] is False

@pytest.mark.parametrize("field,value", [
    ("critic_decision","DENY"), ("twin_state","UNKNOWN"), ("hitl_valid",False),
    ("policy_decision","DENY"), ("external_effect_count",1), ("postcheck_verified",False),
    ("terminal",None), ("history_sha256","d"*64), ("executed_sha","d"*40)])
def test_independent_negative(field,value):
    m,r = manifest_fixture()
    r[field] = value
    with pytest.raises(ValueError):
        validate_manifest(m, expected_sha="a"*40, intent=FIXTURE_INTENT, independently_read=r)

@pytest.mark.parametrize("field,value", [("status","FAIL"),("status","BLOCKED"),("version",1),
    ("sequence",1),("sequence",True),("stage","OTHER"),("observed_at","2026-11-17T12:00:00Z"),
    ("identity",{"run_id":"FOREIGN"})])
def test_transition_negative_even_with_matching_digest(field,value):
    m,r = manifest_fixture()
    m["transitions"][1][field] = value
    r["transitions_sha256"] = digest(m["transitions"])
    with pytest.raises(ValueError):
        validate_manifest(m, expected_sha="a"*40, intent=FIXTURE_INTENT, independently_read=r)

def test_altered_worker_receipt():
    m,r = manifest_fixture()
    m["worker_receipt"]["glpi_write"] = True
    with pytest.raises(ValueError):
        validate_manifest(m, expected_sha="a"*40, intent=FIXTURE_INTENT, independently_read=r)
