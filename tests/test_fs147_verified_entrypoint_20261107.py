"""Contract tests: strict FS147 entry point cannot silently downgrade."""
from unittest.mock import patch
from worker.fs147_verified_entrypoint import run_fs147_strict


def test_strict_entrypoint_forwards_both_gates():
    sentinel = object()
    with patch("worker.fs147_verified_entrypoint.run_fs147", return_value=sentinel) as call:
        result = run_fs147_strict(
            sentinel, stop_auto=True, claim_once=sentinel,
            bridge_fetch=sentinel, analyst_call=sentinel,
            critic_call=sentinel, policy_post=sentinel,
        )
    assert result is sentinel
    assert call.call_args.kwargs["strict_bridge"] is True
    assert call.call_args.kwargs["strict_policy"] is True
    assert call.call_args.kwargs["stop_auto"] is True


def test_strict_entrypoint_stop_auto_never_calls_services():
    from worker.fs147_readonly_pipeline import FS147Request
    calls = []
    def forbidden(*args, **kwargs):
        calls.append(1)
        raise AssertionError("service invoked during STOP_AUTO")
    request = FS147Request("tenant", "actor", "incident", "run")
    result = run_fs147_strict(
        request, stop_auto=True, claim_once=forbidden,
        bridge_fetch=forbidden, analyst_call=forbidden,
        critic_call=forbidden, policy_post=forbidden,
    )
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "STOP_AUTO"
    assert result["effect"] == "NO_EFFECT"
    assert result["resolved"] is False
    assert not calls
