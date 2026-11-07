"""FS147 concurrent replay contract (in-memory fake, not a Core durability proof).

A host must implement claim_once atomically across processes and restarts.
These tests exercise Worker behavior when that contract is honored, and fail
closed when the claim service cannot establish ownership.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock

from worker.fs147_readonly_pipeline import FS147Request
from worker.fs147_verified_entrypoint import run_fs147_strict


def test_simultaneous_same_run_only_one_observation():
    request = FS147Request("tenant", "actor", "incident", "run-concurrent")
    start = Barrier(8)
    guard = Lock()
    claimed = set()
    observed = []

    def claim_once(key):
        with guard:
            if key in claimed:
                return False
            claimed.add(key)
            return True

    def bridge_fetch(*args, **kwargs):
        with guard:
            observed.append(1)
        raise TimeoutError("indeterminate bridge result")

    def forbidden(*args, **kwargs):
        raise AssertionError("downstream service must not be called")

    def attempt(_):
        start.wait(timeout=10)
        return run_fs147_strict(
            request, stop_auto=False, claim_once=claim_once,
            bridge_fetch=bridge_fetch, analyst_call=forbidden,
            critic_call=forbidden, policy_post=forbidden,
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(8)))

    assert len(observed) == 1
    assert sum(r["reason"] == "DUPLICATE_RUN" for r in results) == 7
    assert sum(r["reason"] == "UNKNOWN_TIMEOUT" for r in results) == 1
    assert all(r["status"] == "BLOCKED" and r["effect"] == "NO_EFFECT"
               and r["resolved"] is False for r in results)


def test_indeterminate_claim_never_starts_bridge():
    request = FS147Request("tenant", "actor", "incident", "run-claim-unknown")
    calls = []

    def unavailable(_):
        raise TimeoutError("Core claim outcome unknown")

    def forbidden(*args, **kwargs):
        calls.append(1)
        raise AssertionError("service must not run")

    result = run_fs147_strict(
        request, stop_auto=False, claim_once=unavailable,
        bridge_fetch=forbidden, analyst_call=forbidden,
        critic_call=forbidden, policy_post=forbidden,
    )
    assert result["reason"] == "IDEMPOTENCY_UNAVAILABLE"
    assert result["status"] == "BLOCKED"
    assert result["effect"] == "NO_EFFECT"
    assert result["resolved"] is False
    assert calls == []
