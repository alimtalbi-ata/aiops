from types import SimpleNamespace
import pytest
from worker.fs147_bridge_adapter import observe_fs147

REQ = SimpleNamespace(tenant_id="t", actor_id="a", incident_id="i",
                      run_id="RUN-147", ticket_id=147, mode="DEMO")

def valid(payload):
    return {**payload, "source": "fs-lab-bridge-readonly",
            "read_only": True, "evidence_id": "EVD-147",
            "collected_at": "2026-11-06T09:00:00Z", "used_percent": 92.0}

def test_payload_and_provenance():
    calls = []
    def fetch(payload):
        calls.append(payload)
        return valid(payload)
    result = observe_fs147(REQ, fetch_observation=fetch)
    assert calls[0]["commands"] == ["df", "du", "ls"]
    assert result["run_id"] == "RUN-147"
    assert result["evidence_id"] == "EVD-147"

@pytest.mark.parametrize("field,value", [
    ("run_id", "other"), ("ticket_id", 146), ("actor_id", "other"),
    ("tenant_id", "other"), ("source", "san"),
    ("filesystem", "/san"), ("commands", ["df", "rm"]),
    ("read_only", False), ("evidence_id", ""), ("evidence_id", None)])
def test_rejects_bad_bridge_response(field, value):
    with pytest.raises(ValueError):
        observe_fs147(REQ, fetch_observation=lambda p: {**valid(p), field: value})

def test_missing_bridge_response():
    with pytest.raises(ValueError):
        observe_fs147(REQ, fetch_observation=lambda _: None)

def test_live_never_calls_bridge():
    live = SimpleNamespace(**{**vars(REQ), "mode": "LIVE"})
    def forbidden(_):
        pytest.fail("bridge called")
    with pytest.raises(ValueError):
        observe_fs147(live, fetch_observation=forbidden)

@pytest.mark.parametrize("field,value", [
    ("ticket_id", True),
    ("ticket_id", 147.0),
    ("ticket_id", "147"),
    ("run_id", None),
])
def test_bridge_rejects_coerced_identity_without_downstream_trust(field, value):
    with pytest.raises(ValueError, match="bridge identity mismatch"):
        observe_fs147(REQ, fetch_observation=lambda p: {**valid(p), field: value})
