"""Negative payload admission tests: no transport, no live effects."""
from worker.fs147_stage_handoff import evaluate_handoff


def _inputs():
    obs = {"status": "ACCEPTED", "fingerprint": "a" * 64,
           "run_id": "run-1", "ticket_id": 147, "tenant_id": "tenant-1"}
    base = {"run_id": "run-1", "ticket_id": 147, "tenant_id": "tenant-1",
            "observation_fingerprint": "a" * 64, "status": "PASS", "unknown": False}
    return obs, dict(base, evidence_sufficient=True), dict(base, approved=True), dict(base, allowed_mode="OBSERVE")


def _evaluate(values):
    return evaluate_handoff(*values, run_id="run-1", ticket_id=147, tenant_id="tenant-1")


def test_normal_readonly_handoff_still_deterministic():
    values = _inputs()
    first = _evaluate(values)
    assert first == _evaluate(values)
    assert first["status"] == "READY_FOR_EVIDENCE"
    assert first["dispatch_allowed"] is False


def test_oversized_analyst_reply_fails_closed():
    values = _inputs()
    values[1]["findings"] = "x" * 100_000
    receipt = _evaluate(values)
    assert receipt["status"] == "UNKNOWN"
    assert receipt["reason"] == "HANDOFF_TOO_COMPLEX"
    assert receipt["digest"] is None
    assert receipt["dispatch_allowed"] is False


def test_many_policy_nodes_fail_closed():
    values = _inputs()
    values[3]["extra"] = [{"x": "value"} for _ in range(2050)]
    receipt = _evaluate(values)
    assert receipt["status"] == "UNKNOWN"
    assert receipt["reason"] == "HANDOFF_TOO_COMPLEX"
    assert receipt["digest"] is None
    assert receipt["dispatch_allowed"] is False


def test_large_but_shallow_payload_fails_closed():
    values = _inputs()
    values[1]["findings"] = ["x" * 8000 for _ in range(10)]
    receipt = _evaluate(values)
    assert receipt["status"] == "UNKNOWN"
    assert receipt["reason"] == "HANDOFF_TOO_LARGE"
    assert receipt["digest"] is None
    assert receipt["dispatch_allowed"] is False
