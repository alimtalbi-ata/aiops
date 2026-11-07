"""FS147 scope validation regression: malformed identities must not claim or call services."""
import pytest
from worker.fs147_readonly_pipeline import FS147Request, execute


@pytest.mark.parametrize("field,value", [
    ("tenant_id", 1),
    ("tenant_id", True),
    ("tenant_id", "  "),
    ("actor_id", []),
    ("actor_id", " "),
    ("incident_id", {"id": "i"}),
    ("incident_id", "\t"),
    ("run_id", 123),
    ("run_id", False),
    ("run_id", "   "),
    ("ticket_id", True),
    ("ticket_id", "147"),
    ("ticket_id", 146),
    ("mode", "LIVE"),
])
def test_malformed_scope_never_claims_or_contacts_remote(field, value):
    values = dict(tenant_id="tenant", actor_id="actor", incident_id="incident",
                  run_id="run", ticket_id=147, mode="DEMO")
    values[field] = value
    def forbidden(*args, **kwargs):
        pytest.fail("malformed scope reached durable claim or remote callback")
    result = execute(FS147Request(**values), stop_auto=False, claim_once=forbidden,
                     observe=forbidden, analyst=forbidden, critic=forbidden,
                     policy=forbidden)
    assert result == {"status": "BLOCKED", "effect": "NO_EFFECT",
                      "reason": "INVALID_SCOPE", "steps": [], "resolved": False}


def test_stop_auto_precedes_scope_and_claim():
    def forbidden(*args, **kwargs):
        pytest.fail("STOP_AUTO must prevent all callbacks")
    result = execute(FS147Request("tenant", "actor", "incident", "run"),
                     stop_auto=True, claim_once=forbidden, observe=forbidden,
                     analyst=forbidden, critic=forbidden, policy=forbidden)
    assert result["reason"] == "STOP_AUTO"
    assert result["effect"] == "NO_EFFECT"
