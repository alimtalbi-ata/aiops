"""Policy reply correlation regression tests; injected transport, not host E2E."""
import pytest
from worker.fs147_readonly_pipeline import FS147Request
from worker.fs147_policy_adapter import check_fs147_policy

REQ = FS147Request("tenant", "actor", "incident", "RUN-147")
OBS = {"evidence_id": "E-147"}
ANA = {"evidence_id": "E-147"}
CRI = {"evidence_id": "E-147", "state": "PASS"}

@pytest.mark.parametrize("field,bad", [
    ("tenant_id", "other"), ("actor_id", "other"),
    ("incident_id", "other"), ("run_id", "other"),
    ("ticket_id", 146), ("ticket_id", "147"),
    ("evidence_id", "other"),
])
def test_policy_explicit_scope_mismatch_rejected(field, bad):
    def transport(payload):
        assert payload["command"] == "OBSERVE"
        assert payload["human_approved"] is False
        return {"state": "PASS", "decision": "SIMULATE", field: bad}
    with pytest.raises(ValueError, match="correlation mismatch"):
        check_fs147_policy(REQ, OBS, ANA, CRI, post_check=transport)

def test_matching_explicit_scope_does_not_imply_hitl():
    identity = dict(tenant_id="tenant", actor_id="actor", incident_id="incident",
                    run_id="RUN-147", ticket_id=147, evidence_id="E-147")
    def transport(payload):
        assert payload["human_approved"] is False
        return dict(identity, state="BLOCKED", decision="HUMAN_APPROVAL")
    response = check_fs147_policy(REQ, OBS, ANA, CRI, post_check=transport)
    assert response["state"] == "BLOCKED"
    assert response["decision"] == "HUMAN_APPROVAL"
