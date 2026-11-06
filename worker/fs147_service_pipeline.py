"""Composition of FS147 read-only adapters; no network fallback or mutation.

The embedding application MUST supply authenticated transports and an atomic,
durable Core claim. This module never asserts that host services were reached.
"""
from functools import partial
from worker.fs147_readonly_pipeline import execute
from worker.fs147_bridge_adapter import observe_fs147
from worker.fs147_policy_adapter import check_fs147_policy


def run_fs147(request, *, stop_auto, claim_once, bridge_fetch,
              analyst_call, critic_call, policy_post, now=None):
    """Injected functions must be backed by real authorized services.

    Analyst and Critic must return scoped evidence-bound responses.
    No SAN, ticket mutation, remediation or synthetic observation is used.
    """
    options = dict(
        stop_auto=stop_auto,
        claim_once=claim_once,
        observe=partial(observe_fs147, fetch_observation=bridge_fetch),
        analyst=analyst_call,
        critic=critic_call,
        policy=partial(check_fs147_policy, post_check=policy_post),
    )
    if now is not None:
        options["now"] = now
    return execute(request, **options)
