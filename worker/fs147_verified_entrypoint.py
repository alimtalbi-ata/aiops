"""FS147 fail-closed entry point for host integration.

This entry point requires both evidence and Policy attestation gates. It does
not assert that injected transports are authenticated or that Core is durable.
The host must prove those properties independently before E2E qualification.
"""
from worker.fs147_service_pipeline import run_fs147


def run_fs147_strict(request, *, stop_auto, claim_once, bridge_fetch,
                     analyst_call, critic_call, policy_post, now=None):
    """No compatibility fallback for a new FS147 host integration."""
    return run_fs147(
        request,
        stop_auto=stop_auto,
        claim_once=claim_once,
        bridge_fetch=bridge_fetch,
        analyst_call=analyst_call,
        critic_call=critic_call,
        policy_post=policy_post,
        now=now,
        strict_bridge=True,
        strict_policy=True,
    )
