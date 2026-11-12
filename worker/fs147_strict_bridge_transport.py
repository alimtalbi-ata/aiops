"""Opt-in strict bridge proof adapter for FS147; no shell or network access.

Authenticated fetch_observation is provided by the embedding host. Validation
happens before Analyst and does not attest transport authenticity.
"""
from worker.fs147_bridge_adapter import observe_fs147
from worker.fs147_bridge_proof import attest_bridge_measurement


def observe_fs147_with_proof(request, *, fetch_observation):
    response = observe_fs147(request, fetch_observation=fetch_observation)
    attest_bridge_measurement(response)
    return response
