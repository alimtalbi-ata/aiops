"""FS147 ambiguous Core claim acknowledgement must never be treated as duplicate proof.

Contract tests only: no authenticated Core/bridge transport or Debian E2E.
"""
import pytest

from worker.fs147_readonly_pipeline import FS147Request
from worker.fs147_verified_entrypoint import run_fs147_strict


@pytest.mark.parametrize("ack, expected", [
    (False, "DUPLICATE_RUN"),
    (None, "IDEMPOTENCY_UNAVAILABLE"),
    ("UNKNOWN", "IDEMPOTENCY_UNAVAILABLE"),
    (0, "IDEMPOTENCY_UNAVAILABLE"),
    (1, "IDEMPOTENCY_UNAVAILABLE"),
    ({}, "IDEMPOTENCY_UNAVAILABLE"),
])
def test_core_claim_ack_is_exact_boolean_and_never_calls_bridge(ack, expected):
    seen = []
    request = FS147Request("tenant", "actor", "incident", "RUN-147-ACK")

    def claim_once(key):
        seen.append(("claim", key))
        return ack

    def forbidden(*args, **kwargs):
        seen.append(("forbidden", None))
        raise AssertionError("no downstream service after unproven claim")

    def invoke():
        return run_fs147_strict(
            request, stop_auto=False, claim_once=claim_once,
            bridge_fetch=forbidden, analyst_call=forbidden,
            critic_call=forbidden, policy_post=forbidden,
        )

    first = invoke()
    second = invoke()
    for result in (first, second):
        assert result["reason"] == expected
        assert result["status"] == "BLOCKED"
        assert result["effect"] == "NO_EFFECT"
        assert result["resolved"] is False
    assert len(seen) == 2
    assert seen[0][0] == seen[1][0] == "claim"
    assert seen[0][1] == seen[1][1]


def test_core_claim_timeout_after_commit_is_unknown_not_retry_permission():
    seen = []

    def claim_once(key):
        seen.append(key)
        raise TimeoutError("Core may have committed before response was lost")

    def forbidden(*args, **kwargs):
        raise AssertionError("bridge and services must remain untouched")

    result = run_fs147_strict(
        FS147Request("tenant", "actor", "incident", "RUN-147-LOST-ACK"),
        stop_auto=False, claim_once=claim_once,
        bridge_fetch=forbidden, analyst_call=forbidden,
        critic_call=forbidden, policy_post=forbidden,
    )
    assert result["reason"] == "IDEMPOTENCY_UNAVAILABLE"
    assert result["effect"] == "NO_EFFECT"
    assert result["resolved"] is False
    assert len(seen) == 1
