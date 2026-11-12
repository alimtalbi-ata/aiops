"""FS147: Policy contradictory negative-state decisions fail closed; stub-only."""
from types import SimpleNamespace

import pytest

from worker.fs147_policy_attestation import require_policy_attestation

REQUEST = SimpleNamespace(tenant_id="t", actor_id="a", incident_id="i",
                          run_id="r", ticket_id=147)
BASE = dict(tenant_id="t", actor_id="a", incident_id="i", run_id="r",
            ticket_id=147, evidence_id="e")


@pytest.mark.parametrize("state", ["BLOCKED", "UNKNOWN"])
@pytest.mark.parametrize("decision", ["EXECUTE", "RESOLVED", "APPROVE", "SIMULATE"])
def test_negative_state_rejects_conflicting_decision(state, decision):
    with pytest.raises(ValueError, match="POLICY_UNKNOWN"):
        require_policy_attestation(dict(BASE, state=state, decision=decision),
                                   REQUEST, "e")


@pytest.mark.parametrize("state,decision", [("BLOCKED", None), ("UNKNOWN", None),
                                             ("BLOCKED", "BLOCK"), ("UNKNOWN", "REJECT")])
def test_negative_state_preserves_safe_decision(state, decision):
    reply = require_policy_attestation(dict(BASE, state=state, decision=decision),
                                       REQUEST, "e")
    assert reply["state"] == state


def test_positive_requires_simulation_only():
    assert require_policy_attestation(dict(BASE, state="PASS", decision="SIMULATE"),
                                      REQUEST, "e")["decision"] == "SIMULATE"
