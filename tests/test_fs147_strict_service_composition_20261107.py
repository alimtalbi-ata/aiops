"""FS147 strict Policy composition tests; all dependencies injected, no host calls."""
from datetime import datetime, timezone
from worker.fs147_readonly_pipeline import FS147Request
from worker.fs147_service_pipeline import run_fs147

NOW = datetime(2026, 11, 7, 4, 0, tzinfo=timezone.utc)
REQ = FS147Request("tenant", "actor", "incident", "RUN-147")
IDS = dict(tenant_id="tenant", actor_id="actor", incident_id="incident",
           run_id="RUN-147", ticket_id=147)


def execute(reply, *, stop_auto=False, claim=True):
    calls = []
    def reserve(key):
        calls.append("claim")
        return claim
    def bridge(payload):
        calls.append("bridge")
        return dict(IDS, source="fs-lab-bridge-readonly",
                    filesystem="/fs-lab", commands=["df", "du", "ls"],
                    read_only=True, evidence_id="E-147",
                    collected_at=NOW.isoformat(), used_percent=92)
    def analyst(request, observation):
        calls.append("analyst")
        return dict(IDS, evidence_id="E-147", findings=["lab usage 92%"])
    def critic(request, observation, analysis):
        calls.append("critic")
        return dict(IDS, evidence_id="E-147", state="PASS")
    def policy(request, evidence_id, payload):
        calls.append("policy")
        assert request.run_id == "RUN-147" and evidence_id == "E-147"
        assert payload["command"] == "OBSERVE" and payload["human_approved"] is False
        return reply
    result = run_fs147(REQ, stop_auto=stop_auto, claim_once=reserve,
                       bridge_fetch=bridge, analyst_call=analyst,
                       critic_call=critic, policy_post=policy,
                       strict_policy=True, now=lambda: NOW)
    return result, calls


def test_attested_simulation_has_no_effect():
    result, calls = execute(dict(IDS, evidence_id="E-147",
                                 state="PASS", decision="SIMULATE"))
    assert calls == ["claim", "bridge", "analyst", "critic", "policy"]
    assert result["status"] == "NO_EFFECT" and result["resolved"] is False


def test_missing_remote_attestation_is_blocked():
    result, calls = execute({"state": "PASS", "decision": "SIMULATE"})
    assert result["status"] == "BLOCKED"
    assert result["effect"] == "NO_EFFECT" and result["resolved"] is False
    assert calls[-1] == "policy"


def test_wrong_run_or_unsafe_decision_is_blocked():
    for reply in (
        dict(IDS, run_id="OTHER", evidence_id="E-147",
             state="PASS", decision="SIMULATE"),
        dict(IDS, evidence_id="E-147", state="PASS", decision="EXECUTE"),
    ):
        result, _ = execute(reply)
        assert result["status"] == "BLOCKED" and result["resolved"] is False


def test_refusal_and_unknown_never_resolve():
    for state in ("BLOCKED", "UNKNOWN"):
        result, _ = execute(dict(IDS, evidence_id="E-147",
                                 state=state, decision=None))
        assert result["status"] == "BLOCKED"
        assert result["reason"] == "POLICY_REFUSED"
        assert result["effect"] == "NO_EFFECT"


def test_stop_and_duplicate_never_contact_bridge():
    for kwargs, reason in (({"stop_auto": True}, "STOP_AUTO"),
                           ({"claim": False}, "DUPLICATE_RUN")):
        result, calls = execute({}, **kwargs)
        assert result["reason"] == reason
        assert "bridge" not in calls and "policy" not in calls
