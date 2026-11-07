"""Negative contract tests for FS147 Policy attestation; no live calls."""
from types import SimpleNamespace
import pytest
from worker.fs147_policy_attestation import require_policy_attestation

REQ = SimpleNamespace(tenant_id="t", actor_id="a", incident_id="i", run_id="r", ticket_id=147)
BASE = dict(tenant_id="t", actor_id="a", incident_id="i", run_id="r",
            ticket_id=147, evidence_id="e", state="PASS", decision="SIMULATE")


def test_valid_attestation_is_read_only():
    assert require_policy_attestation(BASE, REQ, "e")["decision"] == "SIMULATE"


@pytest.mark.parametrize("field", ["tenant_id", "actor_id", "incident_id",
                                    "run_id", "ticket_id", "evidence_id"])
def test_missing_identity_is_unknown(field):
    response = dict(BASE)
    response.pop(field)
    with pytest.raises(ValueError, match="POLICY_UNKNOWN"):
        require_policy_attestation(response, REQ, "e")


@pytest.mark.parametrize("change", [{"ticket_id": True}, {"ticket_id": 147.0},
                                     {"run_id": "other"}, {"evidence_id": "other"}])
def test_mismatched_identity_is_unknown(change):
    with pytest.raises(ValueError, match="POLICY_UNKNOWN"):
        require_policy_attestation(dict(BASE, **change), REQ, "e")


@pytest.mark.parametrize("state,decision", [("PASS", "EXECUTE"),
                                             ("PASS", "RESOLVED"),
                                             ("INVALID", "SIMULATE")])
def test_unsafe_decision_is_unknown(state, decision):
    with pytest.raises(ValueError, match="POLICY_UNKNOWN"):
        require_policy_attestation(dict(BASE, state=state, decision=decision), REQ, "e")


@pytest.mark.parametrize("state", ["UNKNOWN", "BLOCKED"])
def test_negative_decision_preserved(state):
    assert require_policy_attestation(dict(BASE, state=state, decision=None), REQ, "e")["state"] == state
