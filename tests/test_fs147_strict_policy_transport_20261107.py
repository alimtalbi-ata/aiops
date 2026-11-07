"""FS147 strict remote Policy transport regression tests; injected calls only."""
from types import SimpleNamespace
import pytest
from worker.fs147_strict_policy_transport import strict_policy_step

REQ = SimpleNamespace(tenant_id="t", actor_id="a", incident_id="i",
                      run_id="r", ticket_id=147, mode="DEMO")
IDS = dict(tenant_id="t", actor_id="a", incident_id="i", run_id="r",
           ticket_id=147, evidence_id="e")
OBS = dict(IDS, evidence_id="e")
ANALYSIS = dict(IDS)
CRITIQUE = dict(IDS, state="PASS")


def call(reply):
    calls = []
    def post(request, evidence_id, payload):
        calls.append((request.run_id, evidence_id, payload))
        return reply
    try:
        return strict_policy_step(REQ, OBS, ANALYSIS, CRITIQUE, post_check=post), calls
    except ValueError:
        assert len(calls) == 1
        raise


def test_attested_simulation_no_effect():
    response, calls = call(dict(IDS, state="PASS", decision="SIMULATE"))
    assert response["decision"] == "SIMULATE"
    assert response["run_id"] == "r"
    assert calls[0][2]["command"] == "OBSERVE"
    assert calls[0][2]["human_approved"] is False


@pytest.mark.parametrize("reply", [
    {"state": "PASS", "decision": "SIMULATE"},
    dict(IDS, run_id="wrong", state="PASS", decision="SIMULATE"),
    dict(IDS, ticket_id=True, state="PASS", decision="SIMULATE"),
    dict(IDS, state="PASS", decision="EXECUTE"),
    dict(IDS, state="RESOLVED", decision="SIMULATE"),
])
def test_missing_mismatched_or_unsafe_remote_attestation_fails_closed(reply):
    with pytest.raises(ValueError, match="POLICY_UNKNOWN"):
        call(reply)


@pytest.mark.parametrize("state", ["BLOCKED", "UNKNOWN"])
def test_remote_refusal_preserved(state):
    response, _ = call(dict(IDS, state=state, decision=None))
    assert response["state"] == state
    assert response["decision"] is None
