"""Composition of FS147 read-only adapters; no network fallback or mutation.

The embedding application MUST supply authenticated transports and an atomic,
durable Core claim. This module never asserts that host services were reached.
"""
from functools import partial
from worker.fs147_readonly_pipeline import execute
from worker.fs147_bridge_adapter import observe_fs147
from worker.fs147_strict_bridge_transport import observe_fs147_with_proof
from worker.fs147_policy_adapter import check_fs147_policy
from worker.fs147_strict_policy_transport import strict_policy_step


def run_fs147(request, *, stop_auto, claim_once, bridge_fetch,
              analyst_call, critic_call, policy_post, now=None, strict_policy=False, strict_bridge=False):
    """Injected functions must be backed by real authorized services.

    Analyst and Critic must return scoped evidence-bound responses.
    No SAN, ticket mutation, remediation or synthetic observation is used.
    """
    policy_step = (partial(strict_policy_step, post_check=policy_post)
                   if strict_policy else partial(check_fs147_policy, post_check=policy_post))
    options = dict(
        stop_auto=stop_auto,
        claim_once=claim_once,
        observe=partial(observe_fs147_with_proof if strict_bridge else observe_fs147,
                        fetch_observation=bridge_fetch),
        analyst=analyst_call,
        critic=critic_call,
        policy=policy_step,
    )
    if now is not None:
        options["now"] = now
    return execute(request, **options)
