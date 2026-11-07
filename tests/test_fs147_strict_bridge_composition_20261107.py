"""FS147 strict bridge composition: injected transports, no host access."""
from copy import deepcopy
from datetime import datetime, timezone
import pytest

from worker.fs147_readonly_pipeline import FS147Request
from worker.fs147_service_pipeline import run_fs147

NOW = datetime(2026, 11, 7, 7, 0, tzinfo=timezone.utc)
REQ = FS147Request("tenant", "actor", "incident", "RUN-147")
IDS = dict(tenant_id="tenant", actor_id="actor", incident_id="incident",
           run_id="RUN-147", ticket_id=147)


def observation():
    return dict(IDS, source="fs-lab-bridge-readonly", filesystem="/fs-lab",
                commands=["df", "du", "ls"], read_only=True, evidence_id="E-147",
                collected_at=NOW.isoformat(), used_percent=92,
                command_results={
                    "df": {"exit_code": 0, "stdout": "tmpfs 12M 11M 1M 92% /fs-lab", "stderr": ""},
                    "du": {"exit_code": 0, "stdout": "11264 /fs-lab", "stderr": ""},
                    "ls": {"exit_code": 0, "stdout": "aiops2-demo-fill.bin", "stderr": ""},
                })


def run(reply=None, *, strict_bridge=True, stop_auto=False, claim=True):
    calls = []
    def reserve(key):
        calls.append("claim")
        return claim
    def bridge(payload):
        calls.append("bridge")
        return deepcopy(reply if reply is not None else observation())
    def analyst(request, evidence):
        calls.append("analyst")
        return dict(IDS, evidence_id="E-147", findings=["lab usage 92%"])
    def critic(request, evidence, analysis):
        calls.append("critic")
        return dict(IDS, evidence_id="E-147", state="PASS")
    def policy(request, evidence_id, payload):
        calls.append("policy")
        return dict(IDS, evidence_id="E-147", state="PASS", decision="SIMULATE")
    result = run_fs147(REQ, stop_auto=stop_auto, claim_once=reserve,
                       bridge_fetch=bridge, analyst_call=analyst,
                       critic_call=critic, policy_post=policy,
                       strict_bridge=strict_bridge, strict_policy=True,
                       now=lambda: NOW)
    return result, calls


def test_complete_proof_allows_diagnostic_only():
    result, calls = run()
    assert calls == ["claim", "bridge", "analyst", "critic", "policy"]
    assert result["effect"] == "NO_EFFECT" and result["resolved"] is False


@pytest.mark.parametrize("mutate", [
    lambda x: x.pop("command_results"),
    lambda x: x["command_results"]["du"].update(stdout=""),
    lambda x: x["command_results"]["df"].update(exit_code=1),
    lambda x: x["command_results"]["ls"].update(stderr="permission denied"),
])
def test_missing_proof_blocks_before_analyst(mutate):
    evidence = observation()
    mutate(evidence)
    result, calls = run(evidence)
    assert result["status"] == "BLOCKED" and result["effect"] == "NO_EFFECT"
    assert calls == ["claim", "bridge"]
    assert result["resolved"] is False


def test_stop_auto_and_duplicate_do_not_observe():
    for options, reason in (({"stop_auto": True}, "STOP_AUTO"),
                            ({"claim": False}, "DUPLICATE_RUN")):
        result, calls = run(**options)
        assert result["reason"] == reason and "bridge" not in calls


def test_opt_in_preserves_legacy_transport():
    evidence = observation()
    evidence.pop("command_results")
    result, calls = run(evidence, strict_bridge=False)
    assert result["effect"] == "NO_EFFECT"
    assert calls[-1] == "policy"
