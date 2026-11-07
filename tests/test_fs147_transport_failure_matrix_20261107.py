"""FS147 transport failure matrix: injected adapters only, no host or GLPI effects.

These are contract tests, NOT authenticated bridge / Core durability / E2E proof.
"""
import pytest



@pytest.mark.parametrize("failed_stage,exception,expected,calls", [
    ("bridge", ConnectionError("bridge offline"), "SERVICE_UNAVAILABLE",
     ["claim", "bridge"]),
    ("analyst", ConnectionError("analyst offline"), "SERVICE_UNAVAILABLE",
     ["claim", "bridge", "analyst"]),
    ("critic", ConnectionError("critic offline"), "SERVICE_UNAVAILABLE",
     ["claim", "bridge", "analyst", "critic"]),
    ("policy", ConnectionError("policy offline"), "SERVICE_UNAVAILABLE",
     ["claim", "bridge", "analyst", "critic", "policy"]),
    ("bridge", TimeoutError("bridge ambiguous"), "UNKNOWN_TIMEOUT",
     ["claim", "bridge"]),
    ("analyst", TimeoutError("analyst ambiguous"), "UNKNOWN_TIMEOUT",
     ["claim", "bridge", "analyst"]),
    ("critic", TimeoutError("critic ambiguous"), "UNKNOWN_TIMEOUT",
     ["claim", "bridge", "analyst", "critic"]),
    ("policy", TimeoutError("policy ambiguous"), "UNKNOWN_TIMEOUT",
     ["claim", "bridge", "analyst", "critic", "policy"]),
])
def test_transport_failure_consumes_claim_without_replay(
        failed_stage, exception, expected, calls):
    # Use a wrapper at the injected transport boundary; never call a host.
    from worker.fs147_verified_entrypoint import run_fs147_strict
    from tests.test_fs147_strict_freshness_replay_20261107 import (
        NOW, REQ, SCOPE, evidence)
    claimed = set()
    observed = []

    def claim(key):
        observed.append("claim")
        if key in claimed:
            return False
        claimed.add(key)
        return True

    def stage(name, result):
        def invoke(*args):
            observed.append(name)
            if name == failed_stage:
                raise exception
            return result() if callable(result) else result
        return invoke

    def execute():
        return run_fs147_strict(
            REQ, stop_auto=False, claim_once=claim,
            bridge_fetch=stage("bridge", evidence),
            analyst_call=stage("analyst", dict(SCOPE, evidence_id="E-147",
                                               findings=["lab usage observed"])),
            critic_call=stage("critic", dict(SCOPE, evidence_id="E-147",
                                             state="PASS")),
            policy_post=stage("policy", dict(SCOPE, evidence_id="E-147",
                                             state="PASS", decision="SIMULATE")),
            now=lambda: NOW)

    result = execute()
    assert result["status"] == "BLOCKED"
    assert result["reason"] == expected
    assert result["effect"] == "NO_EFFECT"
    assert result["resolved"] is False
    assert observed == calls
    assert execute()["reason"] == "DUPLICATE_RUN"
    assert observed == calls + ["claim"]
    assert len(claimed) == 1
